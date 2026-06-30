"""Appeal coaching hints derived from panel verdicts.

Keep in sync with web/src/lib/appeal/coaching.ts (client-side fallback).

"""

from dataclasses import dataclass
from typing import Literal

from config import JUDGE_ORDER
from judges.schemas import RoastPanel, Verdict, VerdictLabel
from verification.invariants import is_generic_evidence, normalize_sentence
from verification.lens import DERIVED_HINT_PREFIX, coaching_hint, find_duplicate_evidence_judges

_APPEAL_PRIORITY = {
    VerdictLabel.FAIL: 0,
    VerdictLabel.CONDITIONAL: 1,
    VerdictLabel.PASS: 2,
}

AppealHintQuality = Literal["precise", "derived", "generic", "duplicate"]


def is_derived_coaching_hint(hint: str) -> bool:

    return hint.strip().startswith(DERIVED_HINT_PREFIX)


def is_degenerate_evidence_asks(verdicts: list[Verdict]) -> bool:

    asks = [
        normalize_sentence(appeal_coaching_hint(verdict))
        for verdict in verdicts
        if appeal_coaching_hint(verdict).strip()
    ]

    if len(asks) < 2:
        return False

    first = asks[0]

    return all(ask == first for ask in asks[1:])


def _hint_quality(
    verdict: Verdict,
    *,
    duplicate_judges: set[str],
) -> AppealHintQuality:

    judge = verdict.judge.value

    if judge in duplicate_judges:
        return "duplicate"

    evidence = (verdict.evidence_to_change_verdict or "").strip()

    if not evidence:
        return "derived"

    if is_generic_evidence(evidence):
        return "generic"

    return "precise"


def appeal_coaching_hint(verdict: Verdict) -> str:
    return coaching_hint(verdict)


def appeal_coaching_verdicts(panel: RoastPanel) -> list[Verdict]:

    return sorted(
        panel.verdicts,
        key=lambda verdict: (_APPEAL_PRIORITY.get(verdict.verdict, 99), verdict.judge.value),
    )


@dataclass(frozen=True)
class AppealCoachingItem:
    judge: str

    hint: str

    verdict: str

    score: int

    quality: AppealHintQuality


def assess_appeal_coaching(panel: RoastPanel) -> dict:
    """Flag weak or duplicated evidence asks so coaching stays trustworthy."""

    ordered = appeal_coaching_verdicts(panel)
    duplicate_judges = find_duplicate_evidence_judges(ordered)

    items = [
        AppealCoachingItem(
            judge=verdict.judge.value,
            hint=appeal_coaching_hint(verdict),
            verdict=verdict.verdict.value,
            score=verdict.score,
            quality=_hint_quality(verdict, duplicate_judges=duplicate_judges),
        )
        for verdict in ordered
    ]

    degenerate_asks = is_degenerate_evidence_asks(ordered) if ordered else False

    reasons: list[str] = []

    if degenerate_asks:
        reasons.append("Judges returned near-identical evidence asks.")

    elif duplicate_judges:
        reasons.append("Some judges asked for the same proof.")

    elif any(item.quality == "generic" for item in items):
        generic_count = sum(1 for item in items if item.quality == "generic")

        reasons.append(
            f"{generic_count} evidence ask{'s' if generic_count != 1 else ''} "
            "look generic — treat them as directional, not precise targets."
        )

    return {
        "degraded": bool(reasons),
        "reasons": reasons,
        "items": items,
        "degenerate_asks": degenerate_asks,
    }


def appeal_score_movement(baseline: RoastPanel, revised: RoastPanel) -> dict[str, int]:
    """Score movement summary for appeal evals."""

    originals = {verdict.judge.value: verdict for verdict in baseline.verdicts}

    positive_moves = 0

    net_delta = 0

    for revised_verdict in revised.verdicts:
        original = originals.get(revised_verdict.judge.value)

        if original is None:
            continue

        delta = revised_verdict.score - original.score

        net_delta += delta

        if delta > 0:
            positive_moves += 1

    return {
        "positive_moves": positive_moves,
        "net_delta": net_delta,
    }


def normalize_target_judges(judges: list[str] | None) -> tuple[str, ...]:
    """Keep only known judge ids, in panel order."""

    if not judges:
        return ()

    allowed = set(JUDGE_ORDER)

    return tuple(judge for judge in JUDGE_ORDER if judge in allowed and judge in judges)


def appeal_evidence_outcome(original: Verdict, revised: Verdict) -> str:
    """Whether the original evidence ask was satisfied by the appeal."""

    delta = revised.score - original.score

    if delta > 0:
        return "Evidence met"

    if delta < 0:
        return "Not met"

    if original.verdict == VerdictLabel.PASS:
        return "Already passing"

    return "Not met"


@dataclass(frozen=True)
class AppealJudgeOutcome:
    judge: str

    evidence_ask: str

    outcome: str

    targeted: bool

    score_delta: int


def appeal_judge_outcomes(
    baseline: RoastPanel,
    revised: RoastPanel,
    target_judges: tuple[str, ...] = (),
) -> list[AppealJudgeOutcome]:
    """Per-judge evidence ask, founder targeting, and post-appeal outcome."""

    originals = {verdict.judge.value: verdict for verdict in baseline.verdicts}

    outcomes: list[AppealJudgeOutcome] = []

    for revised_verdict in revised.verdicts:
        judge = revised_verdict.judge.value

        original = originals.get(judge)

        if original is None:
            continue

        delta = revised_verdict.score - original.score

        outcomes.append(
            AppealJudgeOutcome(
                judge=judge,
                evidence_ask=appeal_coaching_hint(original),
                outcome=appeal_evidence_outcome(original, revised_verdict),
                targeted=judge in target_judges,
                score_delta=delta,
            )
        )

    return outcomes
