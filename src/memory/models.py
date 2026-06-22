from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from judges.schemas import RoastPanel


class IdeaRecord(BaseModel):
    """A persisted startup idea run, including optional appeal outcome."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    idea_text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    roast_panel: RoastPanel
    debate_result: dict
    appeal_text: str | None = None
    revised_panel: RoastPanel | None = None
    revised_synthesis: str | None = None
