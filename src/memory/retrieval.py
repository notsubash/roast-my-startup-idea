from memory.models import IdeaRecord
from memory.store import IdeaStore


def records_for_memory(
    store: IdeaStore,
    user_id: str,
    query_text: str,
    *,
    limit: int = 3,
) -> list[IdeaRecord]:
    """Return semantically similar past ideas when available, else most recent."""
    if store.semantic_search_enabled:
        similar = store.list_similar(user_id, query_text, limit=limit)
        if similar:
            return similar
    return store.list_recent(user_id, limit=limit)
