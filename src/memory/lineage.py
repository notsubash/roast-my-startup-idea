from judges.schemas import Verdict
from memory.models import IdeaRecord

_VERDICT_RANK = {"FAIL": 0, "CONDITIONAL": 1, "PASS": 2}
# ponytail: show latest two in sidebar; full chain still available via expander.
SIDEBAR_VERSION_TAIL = 2


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


def _verdict_rank(label) -> int:
    if hasattr(label, "value"):
        label = label.value
    return _VERDICT_RANK.get(str(label), 0)


def _addressed_status(prior: Verdict, current: Verdict) -> str:
    # ponytail: score/verdict/concern heuristics only; LLM diff is the upgrade path.
    if current.score > prior.score:
        return "Likely addressed"
    if current.score < prior.score:
        return "Still open"
    if prior.key_concern.strip().lower() == current.key_concern.strip().lower():
        return "Still open"
    if _verdict_rank(current.verdict) > _verdict_rank(prior.verdict):
        return "Likely addressed"
    return "Concern shifted"


def concern_addressed_status(prior: Verdict, current: Verdict) -> str:
    return _addressed_status(prior, current)


def recommended_fix_status(prior: Verdict, current: Verdict) -> str | None:
    if not (prior.recommended_fix or "").strip():
        return None
    return _addressed_status(prior, current)


def fix_status_label(status: str) -> str:
    if status == "Concern shifted":
        return "Status unclear"
    return status


def sidebar_lineage_versions(
    lineage: list[IdeaRecord],
) -> tuple[list[IdeaRecord], list[IdeaRecord]]:
    """Return (visible tail, hidden older versions) for sidebar rendering."""
    if len(lineage) <= SIDEBAR_VERSION_TAIL:
        return lineage, []
    return lineage[-SIDEBAR_VERSION_TAIL:], lineage[:-SIDEBAR_VERSION_TAIL]
