from typing import Any

from langgraph.graph import END, StateGraph

from debate.nodes import make_moderator_node, make_speaker_node
from debate.router import JUDGE_ORDER, advance_round, route_next_speaker
from debate.state import DebateState


def build_debate_graph(model: Any):
    graph = StateGraph(DebateState)

    for judge in JUDGE_ORDER:
        graph.add_node(judge, make_speaker_node(judge, model))

    graph.add_node("advance_round", advance_round)
    graph.add_node("moderator", make_moderator_node(model))

    route_map = {
        **{judge: judge for judge in JUDGE_ORDER},
        "advance_round": "advance_round",
        "moderator": "moderator",
    }

    for judge in JUDGE_ORDER:
        graph.add_conditional_edges(judge, route_next_speaker, route_map)

    graph.add_edge("advance_round", JUDGE_ORDER[0])
    graph.add_edge("moderator", END)

    graph.set_entry_point(JUDGE_ORDER[0])

    return graph.compile()
