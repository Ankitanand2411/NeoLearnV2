"""
State carried through one learning session.

LangGraph passes this dict to every node and merges each node's returned
partial dict back into it. Keys annotated with `operator.add` are *reducers*:
a node returns the new items and LangGraph appends them, so two nodes can never
overwrite each other's messages. Every other key is replaced by the last writer.

`questions` holds the full generated questions INCLUDING `correct_answer`. This
list never leaves the server; the API serialises questions through
`public_question()` which strips the key. That is the whole point of moving the
quiz state machine server-side: the client can no longer read the answer key
out of its own memory.
"""

import operator
from typing import Annotated, Any, TypedDict

from app.services.telemetry import add_usage

QUIZ_LENGTH = 5
MIN_STUDENT_TURNS = 3

PHASE_TUTOR = "tutor"
PHASE_QUIZ = "quiz"
PHASE_DONE = "done"


class SessionState(TypedDict, total=False):
    # identity
    user_id: str
    topic_id: str
    topic: str
    persona_id: str | None
    past_memory: str | None

    # learning estimates
    mastery: float
    theta: float
    theta_sd: float

    # phase machine
    phase: str
    student_turns: int
    messages: Annotated[list[dict[str, Any]], operator.add]

    # judge
    verdict: dict[str, Any] | None

    # quiz (server-only answer keys live here)
    questions: Annotated[list[dict[str, Any]], operator.add]
    answers: Annotated[list[dict[str, Any]], operator.add]
    quiz_index: int

    # the value the client supplied to resume the last interrupt
    resume: dict[str, Any] | None

    # LLM usage accumulated over the session (tokens, calls, estimated cost)
    usage: Annotated[dict[str, Any], add_usage]

    # set by `finish`: badges awarded and completed-topic count
    completion: dict[str, Any] | None


def public_question(question: dict[str, Any]) -> dict[str, Any]:
    """The client-facing view of a question: everything except the answer key."""
    return {k: v for k, v in question.items() if k != "correct_answer"}
