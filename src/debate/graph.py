from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from debate.nodes import make_moderator_node, make_revote_node, make_speaker_node
from debate.router import JUDGE_ORDER, advance_round, route_next_speaker
from debate.state import DebateState
from observability.metrics import RunMetricsCollector


def build_debate_graph(
    model: Any,
    metrics: RunMetricsCollector | None = None,
    abort_check: Callable[[], str | None] | None = None,
):
    graph = StateGraph(DebateState)

    for judge in JUDGE_ORDER:
        graph.add_node(judge, make_speaker_node(judge, model, metrics=metrics))

    graph.add_node("advance_round", advance_round)
    graph.add_node("revote", make_revote_node(model, metrics=metrics, abort_check=abort_check))
    graph.add_node("moderator", make_moderator_node(model, metrics=metrics))

    route_map = {
        **{judge: judge for judge in JUDGE_ORDER},
        "advance_round": "advance_round",
        "revote": "revote",
        "moderator": "moderator",
    }

    for judge in JUDGE_ORDER:
        graph.add_conditional_edges(judge, route_next_speaker, route_map)

    graph.add_edge("advance_round", JUDGE_ORDER[0])
    graph.add_edge("revote", "moderator")
    graph.add_edge("moderator", END)

    graph.set_entry_point(JUDGE_ORDER[0])

    return graph.compile()
