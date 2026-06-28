"""Frontend-safe API request and response models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RunStatus = Literal["created", "running", "completed", "failed", "cancelled"]
IDEA_MAX_LENGTH = 8000


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea: str = Field(
        min_length=10,
        max_length=IDEA_MAX_LENGTH,
        description="The startup idea to roast.",
    )
    target_customer: str | None = None
    pricing: str | None = None
    traction: str | None = None
    competitors: list[str] = Field(default_factory=list)
    model_runtime: Literal["local", "deepseek"] = "deepseek"
    execution_flow: Literal["deterministic", "deepagents"] = "deterministic"
    max_debate_rounds: int = Field(default=3, ge=1, le=5)
    enable_web_search: bool = False

    @model_validator(mode="after")
    def reject_unsupported_execution_flow(self) -> "CreateRunRequest":
        if self.execution_flow == "deepagents":
            raise ValueError(
                "execution_flow 'deepagents' is not supported by the streaming API yet; "
                "use 'deterministic'."
            )
        return self


class RunCreatedResponse(BaseModel):
    run_id: str
    status: Literal["created"] = "created"


class RunStatusResponse(BaseModel):
    run_id: str
    status: RunStatus
    idea: str
    idea_preview: str
    created_at: datetime


class ApiEventEnvelope(BaseModel):
    type: str
    run_id: str
    sequence: int = Field(ge=0)
    payload: dict[str, Any]
    created_at: datetime
