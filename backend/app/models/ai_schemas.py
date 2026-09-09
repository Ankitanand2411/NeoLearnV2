"""
Structured-output schemas for every LLM call in NeoLearn.

These Pydantic models are handed to LangChain's `with_structured_output`, which
turns them into a Groq tool-call schema. The model is forced to "call" the tool
with arguments that match the schema, and LangChain parses + validates the
arguments back into an instance of the class.

Why this replaces regex JSON extraction:
  * the model cannot wrap the answer in prose or markdown fences
  * missing / extra / wrongly-typed keys fail validation instead of silently
    producing a half-filled dict
  * business rules (score in [0, 1], exactly 4 options, correct answer must be
    one of the options) are enforced here, once, instead of in every caller
"""

from pydantic import BaseModel, Field, field_validator, model_validator


class JudgeVerdict(BaseModel):
    """Output of the LLM-as-Judge that grades a Socratic transcript."""

    score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Mastery score from 0.0 (no understanding) to 1.0 (complete mastery).",
    )
    understood: list[str] = Field(
        default_factory=list,
        description="Concepts the student correctly explained or demonstrated.",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Specific misconceptions, gaps or errors the student showed.",
    )
    reasoning: str = Field(
        ..., min_length=1,
        description="Short qualitative summary justifying the score.",
    )


class GeneratedQuestion(BaseModel):
    """One multiple-choice question produced by the quiz generator."""

    question: str = Field(..., min_length=5, description="The question text.")
    options: list[str] = Field(
        ..., min_length=4, max_length=4,
        description="Exactly four distinct answer options.",
    )
    correct_answer: str = Field(
        ..., description="Must be exactly equal to one of the options.",
    )

    @field_validator("options")
    @classmethod
    def options_must_be_distinct(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("options must not be empty strings")
        if len(set(o.lower() for o in cleaned)) != len(cleaned):
            raise ValueError("options must be distinct")
        return cleaned

    @model_validator(mode="after")
    def correct_answer_must_be_an_option(self) -> "GeneratedQuestion":
        self.correct_answer = self.correct_answer.strip()
        if self.correct_answer not in self.options:
            # Tolerate case-only mismatches by snapping to the matching option.
            lowered = {o.lower(): o for o in self.options}
            match = lowered.get(self.correct_answer.lower())
            if match is None:
                raise ValueError("correct_answer must match one of the options exactly")
            self.correct_answer = match
        return self


class AnswerVerdict(BaseModel):
    """Grading of a single free-text / MCQ answer."""

    score: float = Field(..., ge=0.0, le=1.0)
    feedback: str = Field(..., min_length=1, description="Concise explanation of the grade.")
    correction: str = Field(..., min_length=1, description="What the correct answer is and why.")
    is_correct: bool
