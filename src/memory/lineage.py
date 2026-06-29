from judges.schemas import Verdict
from memory.models import IdeaRecord

_VERDICT_RANK = {"FAIL": 0, "CONDITIONAL": 1, "PASS": 2}


def lineage_root_id(record: IdeaRecord, by_id: dict[str, IdeaRecord]) -> str:
    current = record
    seen = {current.id}
    while current.parent_id and current.parent_id in by_id:
        parent = by_id[current.parent_id]
        if parent.id in seen:
            break
        seen.add(parent.id)
        current = parent
    return current.id


def group_by_lineage(records: list[IdeaRecord]) -> list[list[IdeaRecord]]:
    if not records:
        return []
    by_id = {record.id: record for record in records}
    groups: dict[str, list[IdeaRecord]] = {}
    for record in records:
        root = lineage_root_id(record, by_id)
        groups.setdefault(root, []).append(record)
    grouped = [sorted(group, key=lambda item: item.version) for group in groups.values()]
    grouped.sort(key=lambda group: max(item.created_at for item in group), reverse=True)
    return grouped


def concern_addressed_status(prior: Verdict, current: Verdict) -> str:
    # ponytail: score/verdict/concern heuristics only; LLM diff is the Phase 3 upgrade path.
    if current.score > prior.score:
        return "Likely addressed"
    if current.score < prior.score:
        return "Still open"
    if prior.key_concern.strip().lower() == current.key_concern.strip().lower():
        return "Still open"
    prior_rank = _VERDICT_RANK.get(prior.verdict.value, 0)
    current_rank = _VERDICT_RANK.get(current.verdict.value, 0)
    if current_rank > prior_rank:
        return "Likely addressed"
    return "Concern shifted"
