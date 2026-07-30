"""
NeoLearn AI Service
────────────────────
All LangChain + Groq LLM calls live here.

Architecture:
  stream_tutor_response  → ChatGroq (astream) with persona-fused system prompt
  evaluate_understanding → ChatGroq (ainvoke) acting as LLM-as-Judge
  generate_question      → ChatGroq (ainvoke) for IRT-targeted MCQ generation
  evaluate_answer        → ChatGroq (ainvoke) for answer scoring

The RAG retrieval (`get_topic_context`) pulls curriculum data from Supabase
and injects it into the LangChain system prompt before every LLM call.
The persona layer (from persona_registry.py) wraps the RAG context with
the historical mentor's voice and teaching style.
"""

import json
import re
import structlog
from app.core.config import settings
from app.core.database import get_supabase
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.services.persona_registry import build_persona_system_prompt, get_persona

log = structlog.get_logger()

GROQ_MODEL = "llama-3.1-8b-instant"


# ─── Utility ──────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Safely extract JSON object from LLM output that may contain prose."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {text[:200]}")
    return json.loads(match.group())


def _make_llm(temperature: float = 0.7) -> ChatGroq:
    """Create a configured ChatGroq instance via LangChain."""
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=temperature,
    )


# ─── RAG Retrieval ────────────────────────────────────────────────────────────

def get_topic_context(topic_name: str) -> dict:
    """
    RAG Step: Retrieve topic curriculum data from Supabase.

    This grounds the LLM in the official course material,
    preventing hallucination and keeping the mentor on-topic.
    """
    try:
        supabase_client = get_supabase()
        response = (
            supabase_client.table("topics")
            .select("*")
            .ilike("title", f"%{topic_name}%")
            .execute()
        )
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


# ─── Streaming Socratic Chat ───────────────────────────────────────────────────

async def stream_tutor_response(
    message: str,
    topic: str,
    mastery: float,
    history: list,
    persona_id: str | None = None,
    past_memory: str | None = None,
):
    """
    Async generator: streams Socratic AI tutor tokens via LangChain + ChatGroq.

    Pipeline:
    1. RAG retrieval from Supabase (topic curriculum)
    2. Persona resolution (from persona_registry or topic's mentor_id)
    3. Fused system prompt build (persona voice + RAG context + mastery level)
    4. LangChain message chain construction
    5. ChatGroq astream — yields SSE tokens to frontend
    """
    # Step 1: RAG
    rag_context = get_topic_context(topic)

    # Step 2: Resolve persona — caller can override, else use topic's default mentor
    resolved_persona_id = persona_id or rag_context.get("mentor_id") or "feynman"

    log.info(
        "stream_chat_start",
        topic=topic,
        persona=resolved_persona_id,
        mastery=round(mastery, 3),
    )

    # Step 3: Build fused system prompt (persona + RAG + mastery)
    system_prompt = build_persona_system_prompt(
        persona_id=resolved_persona_id,
        topic=topic,
        rag_context=rag_context,
        mastery=mastery,
        past_memory=past_memory,
    )

    # Step 4: Construct LangChain message list
    messages = [SystemMessage(content=system_prompt)]
    for msg in history[-8:]:   # last 4 turns (8 messages)
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=message))

    # Step 5: Stream via ChatGroq
    try:
        llm = _make_llm(temperature=0.7)
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        log.error("langchain_stream_failed", error=str(e))
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


# ─── LLM-as-Judge Evaluation ──────────────────────────────────────────────────

async def evaluate_understanding(
    topic: str,
    history: list,
    persona_id: str | None = None,
) -> dict:
    """
    LLM-as-Judge: analyze the full Socratic dialogue transcript.

    The judge is RAG-grounded using the same curriculum context as the tutor.
    It outputs a strict JSON schema: score, understood[], gaps[], reasoning.
    The persona_id is used to contextualise the judge's expectations.
    """
    rag_context = get_topic_context(topic)
    resolved_persona_id = persona_id or rag_context.get("mentor_id") or "feynman"
    persona = get_persona(resolved_persona_id)
    mentor_name = persona["name"] if persona else "the AI tutor"

    transcript = ""
    for msg in history:
        role = "Student" if msg["role"] == "user" else mentor_name
        transcript += f"{role}: {msg['content']}\n"

    system_prompt = (
        "You are an expert Educational Assessor and LLM-as-Judge.\n"
        "You are evaluating a Socratic tutoring session conducted by a historical mentor persona.\n\n"
        f"--- Session Context ---\n"
        f"Topic: {topic}\n"
        f"Mentor Persona: {mentor_name}\n"
        f"Official Lesson Explanation (RAG): {rag_context.get('explanation', 'Standard foundations.')}\n"
        f"Key Target Takeaway (RAG): {rag_context.get('key_takeaway', 'Conceptual mastery.')}\n"
        "----------------------\n\n"
        "Analyze the STUDENT's contributions only. Identify:\n"
        "1. Concepts the student correctly explained or demonstrated understanding of.\n"
        "2. Misconceptions, gaps, or errors the student showed.\n"
        "3. A mastery score (0.0 to 1.0) based on accuracy, depth, and self-correction.\n\n"
        "You MUST respond ONLY with a valid JSON object matching exactly this schema:\n"
        "{\n"
        "  \"score\": 0.75,\n"
        "  \"understood\": [\"list of concepts correctly understood\"],\n"
        "  \"gaps\": [\"list of specific gaps or misconceptions\"],\n"
        "  \"reasoning\": \"A short qualitative summary of the evaluation.\"\n"
        "}\n"
        "No prose, no markdown, no extra keys."
    )

    try:
        llm = _make_llm(temperature=0.1)
        resp = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this transcript:\n\n{transcript}"),
        ])
        result = _extract_json(resp.content.strip())
        log.info("llm_judge_complete", topic=topic, score=result.get("score"))
        return result
    except Exception as e:
        log.error("llm_judge_failed", error=str(e))
        return {
            "score": 0.5,
            "understood": ["Conversation completed"],
            "gaps": ["Structured assessment unavailable"],
            "reasoning": f"Fallback evaluation: {str(e)}",
        }


# ─── Adaptive Quiz Generation ─────────────────────────────────────────────────

async def generate_question(
    topic: str,
    difficulty: str,
    gaps: list | None = None,
    persona_id: str | None = None,
) -> dict:
    """
    Generate an IRT-targeted MCQ question.

    If a persona_id is provided, the question is framed in the mentor's voice
    (e.g., a Feynman-style question asks for mechanism, not formula).
    Gaps from the LLM-as-Judge are injected to target specific weaknesses.
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
        "Generate ONE multiple-choice question in the style of this mentor.\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        "  question: string\n"
        "  options: array of exactly 4 strings\n"
        "  correct_answer: string (must exactly match one of the options)\n"
        "No explanation, no markdown, just the raw JSON object."
    )

    try:
        llm = _make_llm(temperature=0.7)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        result = _extract_json(resp.content.strip())
        log.info("question_generated", topic=topic, difficulty=difficulty, persona=persona_id)
        return result
    except Exception as e:
        log.error("question_generation_failed", error=str(e))
        return {
            "question": f"Which of the following best describes a core concept of {topic}?",
            "options": [
                "The foundational principle",
                "An unrelated concept",
                "A common misconception",
                "A surface-level observation",
            ],
            "correct_answer": "The foundational principle",
        }


# ─── Answer Evaluation ────────────────────────────────────────────────────────

async def evaluate_answer(
    topic: str,
    question: str,
    answer: str,
    correct_answer: str,
) -> dict:
    """
    Score a student's quiz answer. Returns score, feedback, correction, is_correct.
    Exact match short-circuits the LLM call.
    """
    if answer.strip().lower() == correct_answer.strip().lower():
        return {
            "score": 1.0,
            "feedback": "Correct.",
            "correction": "No correction needed.",
            "is_correct": True,
        }

    prompt = (
        f"Topic: {topic}\n"
        f"Question: {question}\n"
        f"Correct Answer: {correct_answer}\n"
        f"Student Answer: {answer}\n\n"
        "Evaluate the student's answer. Return ONLY valid JSON:\n"
        "  score: float 0.0-1.0\n"
        "  feedback: string (concise, explain why)\n"
        "  correction: string (what the correct answer is and why)\n"
        "  is_correct: boolean\n"
        "No markdown, no prose, just the JSON object."
    )

    try:
        llm = _make_llm(temperature=0.2)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        result = _extract_json(resp.content.strip())
        result.setdefault("is_correct", result.get("score", 0) >= 0.7)
        log.info("answer_evaluated", topic=topic)
        return result
    except Exception as e:
        log.error("answer_eval_failed", error=str(e))
        return {
            "score": 0.0,
            "feedback": f"Evaluation failed: {str(e)}",
            "correction": correct_answer,
            "is_correct": False,
        }
