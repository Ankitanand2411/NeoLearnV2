"""
Drive the LangGraph session directly: start, resume through interrupts, and
inspect checkpointed state. No HTTP, no network.
"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.graph import build_graph
from app.graph.state import MIN_STUDENT_TURNS, PHASE_DONE, PHASE_QUIZ, PHASE_TUTOR, QUIZ_LENGTH
from app.services.ai_service import AIServiceError
from app.services.mastery_service import mastery_to_theta, select_difficulty
from tests.session_fakes import OPTIONS, install_fakes

CFG = {"configurable": {"thread_id": "user-1:sess-1"}}
START_STATE = {
    "user_id": "user-1", "topic_id": "topic-1", "topic": "Special Relativity", "persona_id": "einstein",
    "mastery": 0.5, "messages": [], "questions": [], "answers": [],
}


def interrupt_of(snapshot):
    return next((i.value for t in snapshot.tasks for i in t.interrupts), None)


@pytest.fixture
def saver():
    return InMemorySaver()


@pytest.fixture
def graph(saver):
    return build_graph(saver)


async def start(graph):
    await graph.ainvoke(START_STATE, CFG)
    return await graph.aget_state(CFG)


async def chat(graph, n):
    for i in range(n):
        await graph.ainvoke(Command(resume={"message": f"student message {i + 1}"}), CFG)
    return await graph.aget_state(CFG)


# ─── Tutoring phase ───────────────────────────────────────────────────────────

async def test_start_pauses_for_the_student(graph, monkeypatch):
    fakes = install_fakes(monkeypatch)
    snap = await start(graph)

    assert snap.next == ("await_student",)
    assert interrupt_of(snap) == {"type": "student_turn", "student_turns": 0, "can_evaluate": False}
    assert snap.values["phase"] == PHASE_TUTOR
    assert snap.values["theta"] == pytest.approx(mastery_to_theta(0.5))
    assert snap.values["past_memory"] == fakes.memory          # loaded once at init


async def test_each_turn_appends_user_and_assistant_messages(graph, monkeypatch):
    install_fakes(monkeypatch)
    await start(graph)
    snap = await chat(graph, 2)

    msgs = snap.values["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == "student message 1"
    assert "fast train" in msgs[1]["content"]
    assert snap.values["student_turns"] == 2
    assert interrupt_of(snap)["can_evaluate"] is False


async def test_evaluate_is_refused_before_min_turns(graph, monkeypatch):
    fakes = install_fakes(monkeypatch)
    await start(graph)
    await chat(graph, MIN_STUDENT_TURNS - 1)
    await graph.ainvoke(Command(resume={"action": "evaluate"}), CFG)   # guard routes back

    snap = await graph.aget_state(CFG)
    assert snap.values["phase"] == PHASE_TUTOR
    assert snap.next == ("await_student",)
    assert fakes.evaluations == []


async def test_blank_message_does_not_consume_a_turn(graph, monkeypatch):
    install_fakes(monkeypatch)
    await start(graph)
    await graph.ainvoke(Command(resume={"message": "   "}), CFG)
    snap = await graph.aget_state(CFG)
    assert snap.values["student_turns"] == 0
    assert snap.values["messages"] == []


# ─── Judge → quiz ─────────────────────────────────────────────────────────────

async def test_evaluate_runs_judge_persists_and_serves_first_question(graph, monkeypatch):
    fakes = install_fakes(monkeypatch)
    await start(graph)
    await chat(graph, MIN_STUDENT_TURNS)
    await graph.ainvoke(Command(resume={"action": "evaluate"}), CFG)

    snap = await graph.aget_state(CFG)
    v = snap.values
    assert v["phase"] == PHASE_QUIZ
    assert v["verdict"]["score"] == 0.7 and v["verdict"]["gaps"] == ["simultaneity"]
    assert v["mastery"] == 0.7
    assert v["theta"] == pytest.approx(mastery_to_theta(0.7))
    assert fakes.evaluations == [{"user_id": "user-1", "topic_id": "topic-1", "score": 0.7, "turns": 2 * MIN_STUDENT_TURNS}]

    intr = interrupt_of(snap)
    assert intr["type"] == "question" and intr["index"] == 0 and intr["total"] == QUIZ_LENGTH
    assert "correct_answer" not in intr["question"]                    # the invariant
    assert intr["question"]["options"] == OPTIONS
    expected_label, expected_b = select_difficulty(v["theta"])
    assert intr["question"]["difficulty"] == expected_label
    assert intr["question"]["difficulty_param"] == expected_b
    assert v["questions"][0]["correct_answer"] == OPTIONS[0]            # key stays server-side


async def test_judge_failure_leaves_session_resumable(graph, monkeypatch):
    install_fakes(monkeypatch, judge_error=AIServiceError("groq down"))
    await start(graph)
    await chat(graph, MIN_STUDENT_TURNS)

    with pytest.raises(AIServiceError):
        await graph.ainvoke(Command(resume={"action": "evaluate"}), CFG)

    snap = await graph.aget_state(CFG)
    assert snap.values["phase"] == PHASE_TUTOR                           # nothing advanced
    # The checkpoint recorded that await_student finished; the graph is parked
    # *before* the failed node, not at a new interrupt...
    assert snap.next == ("judge",)
    assert not [i for t in snap.tasks for i in t.interrupts]

    await graph.ainvoke(None, CFG)                                       # ...so retry = continue
    assert (await graph.aget_state(CFG)).values["phase"] == PHASE_QUIZ


# ─── Quiz loop ────────────────────────────────────────────────────────────────

async def test_five_answers_complete_the_session(graph, monkeypatch):
    fakes = install_fakes(monkeypatch)
    await start(graph)
    await chat(graph, MIN_STUDENT_TURNS)
    await graph.ainvoke(Command(resume={"action": "evaluate"}), CFG)
    theta_before = (await graph.aget_state(CFG)).values["theta"]

    pattern = [True, True, False, True, True]
    for i, correct in enumerate(pattern):
        answer = OPTIONS[0] if correct else OPTIONS[1]
        await graph.ainvoke(Command(resume={"answer": answer}), CFG)
        snap = await graph.aget_state(CFG)
        last = snap.values["answers"][-1]
        assert last["index"] == i and last["is_correct"] is correct
        assert last["correct_answer"] == OPTIONS[0]                      # revealed only after grading
        if i < QUIZ_LENGTH - 1:
            assert interrupt_of(snap)["index"] == i + 1
            assert "correct_answer" not in interrupt_of(snap)["question"]

    v = snap.values
    assert v["phase"] == PHASE_DONE and snap.next == ()
    assert v["quiz_index"] == QUIZ_LENGTH
    assert len(v["questions"]) == QUIZ_LENGTH
    assert v["theta"] > theta_before                                     # 4/5 correct → ability rose
    assert 0.0 < v["theta_sd"] < 1.0
    assert fakes.quiz_answers == pattern


async def test_wrong_answers_lower_theta(graph, monkeypatch):
    install_fakes(monkeypatch)
    await start(graph)
    await chat(graph, MIN_STUDENT_TURNS)
    await graph.ainvoke(Command(resume={"action": "evaluate"}), CFG)
    t0 = (await graph.aget_state(CFG)).values["theta"]
    await graph.ainvoke(Command(resume={"answer": OPTIONS[2]}), CFG)
    assert (await graph.aget_state(CFG)).values["theta"] < t0


# ─── Durability ───────────────────────────────────────────────────────────────

async def test_session_survives_process_restart(saver, monkeypatch):
    """A new graph instance over the same checkpointer resumes mid-quiz."""
    install_fakes(monkeypatch)
    first = build_graph(saver)
    await first.ainvoke(START_STATE, CFG)
    for i in range(MIN_STUDENT_TURNS):
        await first.ainvoke(Command(resume={"message": f"m{i}"}), CFG)
    await first.ainvoke(Command(resume={"action": "evaluate"}), CFG)
    await first.ainvoke(Command(resume={"answer": OPTIONS[0]}), CFG)

    second = build_graph(saver)                                          # "after redeploy"
    snap = await second.aget_state(CFG)
    assert snap.values["phase"] == PHASE_QUIZ
    assert snap.values["quiz_index"] == 1
    assert interrupt_of(snap)["index"] == 1

    await second.ainvoke(Command(resume={"answer": OPTIONS[0]}), CFG)
    assert (await second.aget_state(CFG)).values["quiz_index"] == 2


async def test_threads_are_isolated(graph, monkeypatch):
    install_fakes(monkeypatch)
    await start(graph)
    other = {"configurable": {"thread_id": "user-2:sess-9"}}
    assert (await graph.aget_state(other)).values == {}
