"""Lens uniqueness checks shared by eval scorers and runtime retries."""

from __future__ import annotations

from typing import Any

from judges.schemas import Verdict
from verification.invariants import _verdict_fields, is_generic_evidence, normalize_sentence

DERIVED_HINT_PREFIX = "Provide concrete evidence that addresses:"

JUDGE_ROLE_NAMES = {
    "vc": "VC",
    "engineer": "Engineer",
    "pm": "PM",
    "customer": "Customer",
    "competitor": "Competitor",
}

# ponytail: Jaccard on word tokens catches near-paraphrase; upgrade path is embedding similarity.
LENS_SIMILARITY_THRESHOLD = 0.85
MAX_GENERIC_EVIDENCE_RATE = 0.4


def coaching_hint(verdict: Verdict | dict[str, Any]) -> str:
    fields = _verdict_fields(verdict)
    evidence = (fields.get("evidence_to_change_verdict") or "").strip()
    if evidence:
        return evidence
    return f"{DERIVED_HINT_PREFIX} {fields['key_concern'].strip()}"


def _token_set(text: str) -> set[str]:
    return set(normalize_sentence(text).split())


def sentence_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return overlap / union if union else 0.0


def _judge_id(verdict: Verdict | dict[str, Any]) -> str:
    return _verdict_fields(verdict)["judge"]


def find_overlapping_judge_pairs(
    verdicts: list[Verdict | dict[str, Any]],
    *,
    field: str,
    threshold: float = LENS_SIMILARITY_THRESHOLD,
) -> list[tuple[str, str, float]]:
    """Return judge pairs whose field text collides (exact or high token overlap)."""
    pairs: list[tuple[str, str, float]] = []
    items: list[tuple[str, str]] = []

    for verdict in verdicts:
        fields = _verdict_fields(verdict)
        text = (fields.get(field) or "").strip()
        if not text:
            continue
        judge = fields["judge"]
        normalized = normalize_sentence(text)
        items.append((judge, normalized))

    for index, (left_judge, left_text) in enumerate(items):
        for right_judge, right_text in items[index + 1 :]:
            if left_text == right_text:
                pairs.append((left_judge, right_judge, 1.0))
                continue
            similarity = sentence_similarity(left_text, right_text)
            if similarity >= threshold:
                pairs.append((left_judge, right_judge, round(similarity, 3)))
    return pairs


def find_duplicate_evidence_judges(verdicts: list[Verdict | dict[str, Any]]) -> set[str]:
    """Judges whose normalized evidence ask collides with another panel member."""
    duplicate_judges: set[str] = set()
    seen: dict[str, str] = {}

    for verdict in verdicts:
        normalized = normalize_sentence(coaching_hint(verdict))
        if not normalized:
            continue
        judge = _judge_id(verdict)
        prior = seen.get(normalized)
        if prior is not None:
            duplicate_judges.add(judge)
            duplicate_judges.add(prior)
        else:
            seen[normalized] = judge

    for left_judge, right_judge, _similarity in find_overlapping_judge_pairs(
        verdicts, field="evidence_to_change_verdict"
    ):
        duplicate_judges.add(left_judge)
        duplicate_judges.add(right_judge)

    return duplicate_judges


def assess_lens_uniqueness(
    verdicts: list[Verdict | dict[str, Any]],
    *,
    max_generic_rate: float = MAX_GENERIC_EVIDENCE_RATE,
    similarity_threshold: float = LENS_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Score panel lens separation for eval gates and runtime retries."""
    if not verdicts:
        return {
            "lens_legacy": True,
            "lens_uniqueness_passed": True,
            "lens_duplicate_evidence_judges": [],
            "lens_overlapping_concern_pairs": [],
            "lens_overlapping_evidence_pairs": [],
            "lens_generic_evidence_count": 0,
            "lens_generic_evidence_rate": 0.0,
        }

    has_evidence_fields = all(
        (_verdict_fields(verdict).get("evidence_to_change_verdict") or "").strip()
        for verdict in verdicts
    )
    if not has_evidence_fields:
        return {
            "lens_legacy": True,
            "lens_uniqueness_passed": True,
            "lens_duplicate_evidence_judges": [],
            "lens_overlapping_concern_pairs": [],
            "lens_overlapping_evidence_pairs": [],
            "lens_generic_evidence_count": 0,
            "lens_generic_evidence_rate": 0.0,
        }

    duplicate_judges = sorted(find_duplicate_evidence_judges(verdicts))
    concern_pairs = find_overlapping_judge_pairs(
        verdicts, field="key_concern", threshold=similarity_threshold
    )
    evidence_pairs = find_overlapping_judge_pairs(
        verdicts, field="evidence_to_change_verdict", threshold=similarity_threshold
    )

    generic_count = 0
    for verdict in verdicts:
        evidence = (_verdict_fields(verdict).get("evidence_to_change_verdict") or "").strip()
        if evidence and is_generic_evidence(evidence):
            generic_count += 1

    generic_rate = generic_count / len(verdicts)
    passed = (
        not duplicate_judges
        and not concern_pairs
        and not evidence_pairs
        and generic_rate <= max_generic_rate
    )

    return {
        "lens_legacy": False,
        "lens_uniqueness_passed": passed,
        "lens_duplicate_evidence_judges": duplicate_judges,
        "lens_overlapping_concern_pairs": [
            {"left": left, "right": right, "similarity": similarity}
            for left, right, similarity in concern_pairs
        ],
        "lens_overlapping_evidence_pairs": [
            {"left": left, "right": right, "similarity": similarity}
            for left, right, similarity in evidence_pairs
        ],
        "lens_generic_evidence_count": generic_count,
        "lens_generic_evidence_rate": round(generic_rate, 3),
    }
