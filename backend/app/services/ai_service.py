"""
NeoLearn AI Service
────────────────────
All LangChain + Groq LLM calls live here.

Architecture:
  build_tutor_messages   → persona + curriculum + mentor passages for one tutor turn (graph node streams it)
  evaluate_understanding → ChatGroq structured output, acting as LLM-as-Judge
  generate_question      → ChatGroq structured output for IRT-targeted MCQ generation
  evaluate_answer        → ChatGroq structured output for answer scoring

Every non-streaming call goes through `_invoke_structured`, which:
  1. binds a Pydantic schema to the model via `with_structured_output`
     (Groq tool-calling under the hood), so the model returns arguments that
     LangChain validates against the schema instead of free text we regex;
  2. retries once with a "repair" message describing the validation error;
  3. raises `AIServiceError` if it still fails, so the API layer can return an
     honest 503 instead of persisting a made-up fallback score.

The retrieval step (`get_topic_context`) pulls the curriculum row from Supabase
and injects it into the system prompt before every LLM call. The persona layer
(persona_registry.py) wraps that context with the historical mentor's voice.
"""

from typing import TypeVar

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_supabase
from app.models.ai_schemas import AnswerVerdict, GeneratedQuestion, JudgeVerdict
from app.services import mentor_rag
from app.services.persona_registry import build_persona_system_prompt, get_persona
from app.services.telemetry import telemetry, timer, usage_from_message

log = structlog.get_logger()

GROQ_MODEL = "llama-3.1-8b-instant"

# "function_calling" = Groq tool use. Works on every Groq chat model, including
# llama-3.1-8b-instant. "json_schema" is stricter but only supported on a subset
# of models, so we keep it opt-in.
STRUCTURED_METHOD = "function_calling"
STRUCTURED_ATTEMPTS = 2

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class AIServiceError(RuntimeError):
    """Raised when the LLM could not produce a valid structured result."""


# ─── LLM factories ────────────────────────────────────────────────────────────

def _make_llm(temperature: float = 0.7) -> ChatGroq:
    """Create a configured ChatGroq instance via LangChain."""
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=temperature,
    )


def _structured_llm(schema: type[SchemaT], temperature: float):
    """
    Return a runnable whose `.ainvoke(messages)` yields an instance of `schema`.

    Kept as a separate seam so tests can swap in a fake model without touching
    the retry logic below.
    """
    # include_raw=True returns {"raw": AIMessage, "parsed": schema | None, "parsing_error": ...}
    # so token usage on the raw message survives parsing.
    return _make_llm(temperature).with_structured_output(schema, method=STRUCTURED_METHOD, include_raw=True)


def _unpack_structured(result, schema: type[SchemaT]) -> tuple[SchemaT, dict]:
    """Accept both include_raw dicts and bare results (tests / other methods)."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "reported": False}
    if isinstance(result, dict) and "raw" in result and "parsed" in result:
        usage = usage_from_message(result["raw"])
        if result.get("parsing_error") is not None:
            raise ValueError(f"structured output did not match schema: {result['parsing_error']}")
        result = result["parsed"]
        if result is None:
            raise ValueError("structured output was empty")
    if not isinstance(result, schema):
        result = schema.model_validate(result)
    return result, usage


async def _invoke_structured(
    schema: type[SchemaT],
    messages: list[BaseMessage],
    temperature: float,
    *,
    purpose: str,
    attempts: int = STRUCTURED_ATTEMPTS,
) -> SchemaT:
    """
    Call the model with a bound schema, retrying once with a repair hint.

    Any exception from the model call or from schema validation counts as a
    failed attempt. After `attempts` failures we raise AIServiceError so the
    caller decides what an honest failure looks like (HTTP 503), rather than
    this layer inventing a plausible-looking result.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            runnable = _structured_llm(schema, temperature)
            with timer() as t:
                raw = await runnable.ainvoke(messages)
            result, usage = _unpack_structured(raw, schema)
            telemetry.record_llm_call(purpose=purpose, model=GROQ_MODEL, usage=usage, latency_ms=t.ms)
            if attempt > 1:
                log.info("structured_output_repaired", purpose=purpose, attempt=attempt)
            return result
        except Exception as e:  # noqa: BLE001 — any failure means "retry or give up"
            last_error = e
            telemetry.record_llm_call(
                purpose=purpose, model=GROQ_MODEL,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "reported": False},
                latency_ms=0.0, error=True,
            )
            log.warning(
                "structured_output_attempt_failed",
                purpose=purpose,
                attempt=attempt,
                error=str(e)[:300],
            )
            if attempt < attempts:
                messages = messages + [
                    HumanMessage(
                        content=(
                            "Your previous output did not match the required schema. "
                            f"Validation error: {str(e)[:300]}. "
                            "Respond again, matching the schema exactly."
                        )
                    )
                ]
    raise AIServiceError(f"{purpose} failed after {attempts} attempts: {last_error}")


# ─── Retrieval ────────────────────────────────────────────────────────────────

def get_topic_context(topic_name: str, topic_id: str | None = None) -> dict:
    """
    Retrieve the curriculum row for a topic from Supabase.

    Selects by primary key when `topic_id` is known (the session always has it).
    The title `ILIKE` match is only a fallback for callers without an id: it is
    ambiguous ("Relativity" matches several topics) and should not be relied on.
    """
    try:
        supabase_client = get_supabase()
        query = supabase_client.table("topics").select("*")
        query = query.eq("id", topic_id) if topic_id else query.ilike("title", f"%{topic_name}%")
        response = query.limit(1).execute()
        if response.data:
            topic_data = response.data[0]
            return {
                "description": topic_data.get("description", ""),
                "explanation": topic_data.get("explanation", ""),
                "key_takeaway": topic_data.get("key_takeaway", ""),
                "mentor_id": topic_data.get("mentor_id", ""),
                "id": topic_data.get("id", ""),
            }
    except Exception as e:
        log.error("rag_retrieval_failed", topic=topic_name, error=str(e))

    return {
        "description": "No course description available.",
        "explanation": "Teach the standard foundations of this topic.",
        "key_takeaway": "Deep conceptual understanding.",
        "mentor_id": "",
        "id": "",
    }


# ─── Tutor turn ───────────────────────────────────────────────────────────────

async def build_tutor_messages(
    message: str,
    topic: str,
    mastery: float,
    history: list,
    persona_id: str | None = None,
    past_memory: str | None = None,
    topic_id: str | None = None,
) -> tuple[list[BaseMessage], str]:
    """
    Assemble the LangChain message list for one tutor turn.

    Used by the session graph's tutor node. Two retrieval steps feed the prompt:
    the curriculum row (deterministic anchor) and the mentor's own passages
    (semantic/hybrid, optional). Returns (messages, resolved_persona_id).
    """
    rag_context = get_topic_context(topic, topic_id)
    resolved_persona_id = persona_id or rag_context.get("mentor_id") or "feynman"
    passages = await mentor_rag.retrieve_passages(resolved_persona_id, f"{topic}. {message}")
    system_prompt = build_persona_system_prompt(
        persona_id=resolved_persona_id,
        topic=topic,
        rag_context=rag_context,
        mastery=mastery,
        past_memory=past_memory,
        passages=passages,
    )
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for msg in history[-8:]:  # last 4 turns (8 messages)
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=message))
    return messages, resolved_persona_id


# ─── LLM-as-Judge Evaluation ──────────────────────────────────────────────────

async def evaluate_understanding(
    topic: str,
    history: list,
    persona_id: str | None = None,
    topic_id: str | None = None,
) -> JudgeVerdict:
    """
    LLM-as-Judge: analyse the full Socratic dialogue transcript.

    Grounded in the same curriculum row as the tutor. Returns a validated
    JudgeVerdict (score in [0, 1], understood[], gaps[], reasoning).
    Raises AIServiceError if the model cannot produce a valid verdict.
    """
    rag_context = get_topic_context(topic, topic_id)
    resolved_persona_id = persona_id or rag_context.get("mentor_id") or "feynman"
    persona = get_persona(resolved_persona_id)
    mentor_name = persona["name"] if persona else "the AI tutor"

    transcript = "".join(
        f"{'Student' if msg['role'] == 'user' else mentor_name}: {msg['content']}\n"
        for msg in history
    )

    system_prompt = (
        "You are an expert Educational Assessor acting as an LLM-as-Judge.\n"
        "You are evaluating a Socratic tutoring session conducted by a historical mentor persona.\n\n"
        "--- Session Context ---\n"
        f"Topic: {topic}\n"
        f"Mentor Persona: {mentor_name}\n"
        f"Official Lesson Explanation: {rag_context.get('explanation', 'Standard foundations.')}\n"
        f"Key Target Takeaway: {rag_context.get('key_takeaway', 'Conceptual mastery.')}\n"
        "----------------------\n\n"
        "Analyse the STUDENT's contributions only. Identify:\n"
        "1. Concepts the student correctly explained or demonstrated understanding of.\n"
        "2. Misconceptions, gaps, or errors the student showed.\n"
        "3. A mastery score from 0.0 to 1.0 based on accuracy, depth, and self-correction.\n"
        "Be strict: vague agreement with the mentor is not understanding."
    )

    verdict = await _invoke_structured(
        JudgeVerdict,
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyse this transcript:\n\n{transcript}"),
        ],
        temperature=0.1,
        purpose="llm_judge",
    )
    log.info("llm_judge_complete", topic=topic, score=verdict.score, gaps=len(verdict.gaps))
    return verdict


# ─── Adaptive Quiz Generation ─────────────────────────────────────────────────

async def generate_question(
    topic: str,
    difficulty: str,
    gaps: list | None = None,
    persona_id: str | None = None,
) -> GeneratedQuestion:
    """
    Generate an IRT-targeted MCQ.

    Gaps from the judge are injected so the question targets diagnosed
    weaknesses; the persona shapes the framing. Returns a validated
    GeneratedQuestion (4 distinct options, correct_answer ∈ options).
    Raises AIServiceError if the model cannot produce a valid question.
    """
    gap_hint = (
        f" Specifically test the student's understanding of these diagnosed gaps: {', '.join(gaps)}."
        if gaps else ""
    )

    persona = get_persona(persona_id or "feynman")
    persona_name = persona["name"] if persona else "an expert educator"
    probe_style = persona["probe_style"] if persona else "Ask a precise conceptual question."

    prompt = (
        f"You are generating a quiz question as {persona_name}.\n"
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}\n"
        f"{gap_hint}\n\n"
        f"Question framing guidance: {probe_style}\n\n"
        "Generate ONE multiple-choice question in the style of this mentor with exactly four "
        "distinct options and one correct answer that exactly matches one of the options."
    )

    question = await _invoke_structured(
        GeneratedQuestion,
        [HumanMessage(content=prompt)],
        temperature=0.7,
        purpose="question_generation",
    )
    log.info("question_generated", topic=topic, difficulty=difficulty, persona=persona_id)
    return question


# ─── Answer Evaluation ────────────────────────────────────────────────────────

async def evaluate_answer(
    topic: str,
    question: str,
    answer: str,
    correct_answer: str,
) -> AnswerVerdict:
    """
    Grade a student's quiz answer. Exact match short-circuits the LLM call.
    Raises AIServiceError if the model cannot produce a valid verdict.
    """
    if answer.strip().lower() == correct_answer.strip().lower():
        return AnswerVerdict(
            score=1.0,
            feedback="Correct.",
            correction="No correction needed.",
            is_correct=True,
        )

    prompt = (
        f"Topic: {topic}\n"
        f"Question: {question}\n"
        f"Correct Answer: {correct_answer}\n"
        f"Student Answer: {answer}\n\n"
        "Grade the student's answer. Give a score from 0.0 to 1.0, concise feedback "
        "explaining why, a correction stating the right answer and why, and whether "
        "the answer counts as correct."
    )

    verdict = await _invoke_structured(
        AnswerVerdict,
        [HumanMessage(content=prompt)],
        temperature=0.2,
        purpose="answer_evaluation",
    )
    log.info("answer_evaluated", topic=topic, is_correct=verdict.is_correct)
    return verdict
