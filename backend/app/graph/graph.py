"""
The session graph.

    START → init → await_student ⇄ tutor_reply
                        │ (evaluate, ≥3 turns)
                        ▼
                      judge → quiz_generate → await_answer → grade_answer
                                    ▲                              │
                                    └──────── (index < 5) ─────────┘
                                                                   │ (index == 5)
                                                                   ▼
                                                                 finish → END

`await_student` and `await_answer` are the human-in-the-loop points: they call
interrupt(), the graph checkpoints, and the API returns to the client. With a
Postgres checkpointer the session survives refreshes, redeploys and cold
starts; the thread id is `<user_id>:<session_id>`, so a user can only ever
resume their own threads.
"""

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import SessionState


def build_graph(checkpointer):
    g = StateGraph(SessionState)

    g.add_node("init", nodes.init)
    g.add_node("await_student", nodes.await_student)
    g.add_node("tutor_reply", nodes.tutor_reply)
    g.add_node("judge", nodes.judge)
    g.add_node("quiz_generate", nodes.quiz_generate)
    g.add_node("await_answer", nodes.await_answer)
    g.add_node("grade_answer", nodes.grade_answer)
    g.add_node("finish", nodes.finish)

    g.add_edge(START, "init")
    g.add_edge("init", "await_student")
    g.add_conditional_edges(
        "await_student",
        nodes.route_after_student,
        {"tutor_reply": "tutor_reply", "judge": "judge", "await_student": "await_student"},
    )
    g.add_edge("tutor_reply", "await_student")
    g.add_edge("judge", "quiz_generate")
    g.add_edge("quiz_generate", "await_answer")
    g.add_edge("await_answer", "grade_answer")
    g.add_conditional_edges(
        "grade_answer",
        nodes.route_after_grade,
        {"quiz_generate": "quiz_generate", "finish": "finish"},
    )
    g.add_edge("finish", END)

    return g.compile(checkpointer=checkpointer)
