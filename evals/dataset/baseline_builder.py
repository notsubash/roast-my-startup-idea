"""Synthetic baseline outputs for CI regression and Tier 2 grader input."""

from __future__ import annotations

from typing import Any

from evals.dataset.loader import load_golden_ideas


def _verdict(judge: str, label: str, score: int, roast: str, concern: str) -> dict[str, Any]:
    return {
        "judge": judge,
        "verdict": label,
        "score": score,
        "roast": roast,
        "key_concern": concern,
    }


def _debate_messages(
    round_templates: dict[int, dict[str, str]],
    *,
    rounds: int = 2,
) -> list[dict[str, Any]]:
    judges = ["vc", "engineer", "pm", "customer", "competitor"]
    messages: list[dict[str, Any]] = []
    for round_num in range(1, rounds + 1):
        templates = round_templates.get(round_num, round_templates[1])
        for judge in judges:
            messages.append(
                {
                    "speaker": judge,
                    "round": round_num,
                    "content": templates[judge],
                }
            )
    return messages


SMARTPATCH_DEBATE = {
    1: {
        "vc": "The VC judge notes market risk, and the engineer is right about calibration accuracy limits.",
        "engineer": "Technically the colorimetric path cannot deliver quantitative electrolyte readouts the PM highlighted.",
        "pm": "The customer judge is correct about friction, but the competitor can bundle a similar NFC feature quickly.",
        "customer": "I would not pay unless calibration is proven; the engineer raised the core accuracy concern.",
        "competitor": "We could replicate the NFC readout in one sprint; the VC judge is right that moat is weak.",
    },
    2: {
        "vc": "Even if accuracy improves, CAC in athlete consumables keeps unit economics tight versus the PM's positioning concern.",
        "engineer": "Calibration at scale remains the blocker the customer judge keeps raising in this debate.",
        "pm": "The competitor judge confirms bundling risk, so our ICP must narrow to elite teams first.",
        "customer": "Show me side-by-side accuracy data or I stay with cheaper alternatives, as the VC noted on pricing.",
        "competitor": "The engineer is underestimating how fast incumbents can ship a checkbox hydration feature.",
    },
}

METRICS_STRONG_DEBATE = {
    1: {
        "vc": "The retention numbers are real, but the engineer judge is right that fifty-state EVV integration is the scaling bottleneck.",
        "engineer": "Medicaid EVV APIs differ by state; the PM is correct that uptime alone does not prove integration breadth.",
        "pm": "The customer judge highlights payroll switching pain, which is why our ICP must stay home-health first.",
        "customer": "I would switch if month-one audit risk drops, but the competitor judge notes ADP can bundle compliance modules.",
        "competitor": "We can add EVV compliance to our payroll suite; the VC judge underestimates how sticky incumbent workflows are.",
    },
    2: {
        "vc": "Even with $2.1M ARR, expansion beyond home-health could dilute the wedge the PM keeps warning about.",
        "engineer": "State-by-state EVV rule changes remain the reliability risk the customer judge raised in round one.",
        "pm": "The competitor judge confirms bundling pressure, so sequencing expansion is more important than top-line growth.",
        "customer": "Show me payroll migration ROI in ninety days or we stay put, as the engineer noted on switching costs.",
        "competitor": "The VC judge ignores that our compliance add-on ships to existing payroll customers with zero migration.",
    },
}

COMPLIANCE_COPILOT_DEBATE = {
    1: {
        "vc": "Hospital budgets exist, but the customer judge is right that compliance VPs will not trust AI audit evidence yet.",
        "engineer": "HIPAA mapping is feasible; the PM judge correctly notes buyer urgency spikes only before Joint Commission surveys.",
        "pm": "The competitor judge warns incumbents can add copilot features, which matches the VC concern on sales-cycle length.",
        "customer": "I will not buy until accuracy is proven in our EHR environment; the engineer raised integration reliability.",
        "competitor": "We can ship a copilot checkbox in a quarter if demand appears; the VC judge overstates our delivery risk.",
    },
    2: {
        "vc": "Pilot traction helps, but the customer judge still needs live proof before budget moves, as the engineer emphasized.",
        "engineer": "EHR write-back reliability at scale remains the blocker the PM and customer judges both flagged.",
        "pm": "Survey timing drives urgency, but the competitor judge confirms suite vendors can bundle similar workflow mapping.",
        "customer": "Named compliance buyers and LOIs matter, yet the engineer judge is right that trust takes a full audit cycle.",
        "competitor": "The VC judge ignores that our installed base already owns the workflow data this startup needs to integrate.",
    },
}


def build_smartpatch_baseline() -> dict[str, Any]:
    idea = next(item for item in load_golden_ideas() if item.id == "smartpatch")
    verdicts = [
        _verdict(
            "vc",
            "FAIL",
            2,
            "The market is niche and CAC for athlete consumables will compress margins before you reach venture scale.",
            "Market size and moat are too weak for venture returns.",
        ),
        _verdict(
            "engineer",
            "FAIL",
            3,
            "Colorimetric microfluidics cannot provide quantitative electrolyte concentration at clinical accuracy without per-user calibration.",
            "Colorimetric calibration accuracy is unproven for quantitative readouts.",
        ),
        _verdict(
            "pm",
            "CONDITIONAL",
            4,
            "Athlete hydration is real pain, but the product claim overshoots what the patch can measure in the field.",
            "Product positioning overclaims measurement precision.",
        ),
        _verdict(
            "customer",
            "FAIL",
            2,
            "I would not pay $10 per patch when my sports drink and scale already tell me enough.",
            "Willingness to pay is weak versus cheap alternatives.",
        ),
        _verdict(
            "competitor",
            "FAIL",
            2,
            "We can add NFC hydration readout as a bundled feature in a quarter if traction appears.",
            "Incumbents can replicate the feature quickly.",
        ),
    ]
    synthesis = (
        "The panel agrees the colorimetric calibration gap is the core issue: the patch cannot support "
        "quantitative electrolyte claims at clinical accuracy. Market size, moat, and customer willingness "
        "to pay remain weak, while competitors can copy the NFC approach."
    )
    roast_panel = {"verdicts": verdicts}
    original_scores = [v["score"] for v in verdicts]
    return {
        "idea_id": idea.id,
        "idea_text": idea.idea_text,
        "tags": idea.tags,
        "judge_attempts": [
            {"judge": judge, "success": True} for judge in [v["judge"] for v in verdicts]
        ],
        "roast_panel": roast_panel,
        "debate_result": {
            "debate_messages": _debate_messages(SMARTPATCH_DEBATE, rounds=2),
            "final_synthesis": synthesis,
        },
        "appeal_weak": {
            "appeal_text": idea.appeal_cases.weak if idea.appeal_cases else "",
            "revised_panel": {"verdicts": verdicts},
            "revised_synthesis": synthesis,
            "seconds": 1.0,
        },
        "appeal_strong": {
            "appeal_text": idea.appeal_cases.strong if idea.appeal_cases else "",
            "revised_panel": {
                "verdicts": [
                    _verdict(
                        v["judge"],
                        "CONDITIONAL" if v["judge"] in {"vc", "engineer", "pm"} else v["verdict"],
                        min(
                            10,
                            v["score"]
                            + (2 if v["judge"] in {"vc", "engineer", "pm", "customer"} else 1),
                        ),
                        v["roast"]
                        + " The new validation data partially addresses calibration risk.",
                        v["key_concern"],
                    )
                    for v in verdicts
                ]
            },
            "revised_synthesis": synthesis
            + " Signed LOIs and validation studies improve the case but execution risk remains.",
            "seconds": 1.2,
        },
        "timings": {"roast_seconds": 12.0, "debate_seconds": 24.0, "total_seconds": 40.0},
        "_meta": {"expected_original_scores": original_scores},
    }


def build_metrics_strong_baseline() -> dict[str, Any]:
    idea = next(item for item in load_golden_ideas() if item.id == "metrics_strong")
    verdicts = [
        _verdict(
            "vc",
            "PASS",
            8,
            "Home-health payroll with $2.1M ARR and 140% NRR shows venture-scale retention in a regulated market wedge.",
            "Regulatory complexity is also a moat once embedded.",
        ),
        _verdict(
            "engineer",
            "PASS",
            7,
            "EVV compliance integrations are operationally hard; your uptime SLA suggests reliable production architecture.",
            "Integration breadth across states remains engineering heavy.",
        ),
        _verdict(
            "pm",
            "PASS",
            8,
            "Clear ICP in home-health agencies with Medicaid EVV pain is focused and measurable.",
            "Expansion beyond core ICP needs disciplined sequencing.",
        ),
        _verdict(
            "customer",
            "CONDITIONAL",
            6,
            "Agencies will pay if audit risk drops in month one, but switching payroll vendors is still painful.",
            "Switching costs slow rollout even with strong ROI.",
        ),
        _verdict(
            "competitor",
            "CONDITIONAL",
            5,
            "Incumbent payroll vendors can add compliance modules, though your retention suggests sticky workflows and competition is not immediate.",
            "Incumbents can bundle compliance over time.",
        ),
    ]
    synthesis = (
        "Strong metrics and retention support a PASS-leaning view. Regulatory complexity and integration "
        "breadth remain engineering and compliance risks, while competitor bundling and payroll switching "
        "friction keep expansion beyond the core ICP conditional."
    )
    return {
        "idea_id": idea.id,
        "idea_text": idea.idea_text,
        "tags": idea.tags,
        "judge_attempts": [{"judge": v["judge"], "success": True} for v in verdicts],
        "roast_panel": {"verdicts": verdicts},
        "debate_result": {
            "debate_messages": _debate_messages(METRICS_STRONG_DEBATE, rounds=2),
            "final_synthesis": synthesis,
        },
        "timings": {"roast_seconds": 10.0, "debate_seconds": 20.0, "total_seconds": 32.0},
    }


def build_compliance_copilot_baseline() -> dict[str, Any]:
    idea = next(item for item in load_golden_ideas() if item.id == "compliance_copilot")
    verdicts = [
        _verdict(
            "vc",
            "CONDITIONAL",
            5,
            "Hospital compliance spend is large, but enterprise sales cycles and trust requirements slow venture velocity.",
            "Long hospital sales cycles delay scale.",
        ),
        _verdict(
            "engineer",
            "CONDITIONAL",
            5,
            "Mapping workflows to HIPAA controls is feasible, but EHR integration reliability is the hard part.",
            "EHR integration reliability is unproven at scale.",
        ),
        _verdict(
            "pm",
            "CONDITIONAL",
            6,
            "Audit prep pain is acute, yet buyer urgency depends on upcoming survey timing.",
            "Buyer urgency varies with survey schedules.",
        ),
        _verdict(
            "customer",
            "FAIL",
            3,
            "Compliance VPs will not trust AI audit evidence without proven accuracy in their environment.",
            "Trust and proof in live hospital workflows are missing.",
        ),
        _verdict(
            "competitor",
            "FAIL",
            3,
            "Incumbent compliance suites can add copilot features once you validate demand.",
            "Incumbents can add similar copilot modules.",
        ),
    ]
    synthesis = (
        "Hospital compliance is a real budget line, but trust, integration reliability, and long sales cycles "
        "keep this conditional until pilots convert. Buyer urgency varies with survey schedules, and incumbents "
        "can add copilot modules if traction appears."
    )
    strong_verdicts = [
        _verdict(
            v["judge"],
            "CONDITIONAL" if v["score"] < 7 else v["verdict"],
            min(10, v["score"] + 2),
            v["roast"] + " LOIs and named compliance buyers reduce demand uncertainty.",
            v["key_concern"],
        )
        for v in verdicts
    ]
    return {
        "idea_id": idea.id,
        "idea_text": idea.idea_text,
        "tags": idea.tags,
        "judge_attempts": [{"judge": v["judge"], "success": True} for v in verdicts],
        "roast_panel": {"verdicts": verdicts},
        "debate_result": {
            "debate_messages": _debate_messages(COMPLIANCE_COPILOT_DEBATE, rounds=2),
            "final_synthesis": synthesis,
        },
        "appeal_weak": {
            "appeal_text": idea.appeal_cases.weak if idea.appeal_cases else "",
            "revised_panel": {"verdicts": verdicts},
            "revised_synthesis": synthesis,
            "seconds": 1.0,
        },
        "appeal_strong": {
            "appeal_text": idea.appeal_cases.strong if idea.appeal_cases else "",
            "revised_panel": {"verdicts": strong_verdicts},
            "revised_synthesis": synthesis + " Pilots and LOIs materially improve demand proof.",
            "seconds": 1.1,
        },
        "timings": {"roast_seconds": 11.0, "debate_seconds": 22.0, "total_seconds": 36.0},
    }


BASELINE_BUILDERS = {
    "smartpatch": build_smartpatch_baseline,
    "metrics_strong": build_metrics_strong_baseline,
    "compliance_copilot": build_compliance_copilot_baseline,
}
