from config import PROJECT_ROOT
from memory.models import IdeaRecord

LOCAL_USER = "local"
LOCAL_USER_ID_PATH = PROJECT_ROOT / "data" / "local_user_id"


def get_local_user_id(idea_store=None) -> str:
    """Return a stable local user id that persists across Streamlit sessions."""
    if (
        not LOCAL_USER_ID_PATH.exists()
        or LOCAL_USER_ID_PATH.read_text(encoding="utf-8").strip() != LOCAL_USER
    ):
        LOCAL_USER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_USER_ID_PATH.write_text(LOCAL_USER, encoding="utf-8")

    if idea_store is not None:
        _migrate_records_to_local_user(idea_store, LOCAL_USER)

    return LOCAL_USER


def _migrate_records_to_local_user(idea_store, user_id: str) -> None:
    rows = idea_store._conn.execute(
        "SELECT id, payload FROM ideas WHERE user_id != ?",
        (user_id,),
    ).fetchall()
    for _, payload in rows:
        record = IdeaRecord.model_validate_json(payload)
        idea_store.save(record.model_copy(update={"user_id": user_id}))
