from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROAST_MAX_LENGTH = 1000
KEY_CONCERN_MAX_LENGTH = 400
RECOMMENDED_FIX_MAX_LENGTH = 400
EVIDENCE_MAX_LENGTH = 400
ACTIONABLE_SENTENCE_MIN_LENGTH = 10


class VerdictLabel(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    CONDITIONAL = "CONDITIONAL"


class judgeLabel(StrEnum):
    VC = "vc"
    ENGINEER = "engineer"
    PM = "pm"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: judgeLabel
    verdict: VerdictLabel
    roast: str = Field(
        min_length=20,
        max_length=ROAST_MAX_LENGTH,
        description="A sharp plain-prose critique in 1-3 paragraphs. No JSON, bullet points, or markdown formatting — just sentences.",
    )
    score: int = Field(
        ge=1, le=10, description="A score between 1 and 10 based on the quality of the critique"
    )
    key_concern: str = Field(
        min_length=5,
        max_length=KEY_CONCERN_MAX_LENGTH,
        description="The single biggest issue with this idea, stated as one clear sentence.",
    )
    recommended_fix: str | None = Field(
        default=None,
        min_length=ACTIONABLE_SENTENCE_MIN_LENGTH,
        max_length=RECOMMENDED_FIX_MAX_LENGTH,
        description="One concrete action the founder should take next, as a single plain sentence.",
    )
    evidence_to_change_verdict: str | None = Field(
        default=None,
        min_length=ACTIONABLE_SENTENCE_MIN_LENGTH,
        max_length=EVIDENCE_MAX_LENGTH,
        description="One specific piece of evidence that would change this judge's score.",
    )

    @field_validator("roast", mode="before")
    @classmethod
    def coerce_roast_length(cls, value):
        if isinstance(value, str) and len(value) > ROAST_MAX_LENGTH:
            return value[: ROAST_MAX_LENGTH - 3].rstrip() + "..."
        return value

    @field_validator("key_concern", mode="before")
    @classmethod
    def coerce_key_concern_length(cls, value):
        if isinstance(value, str) and len(value) > KEY_CONCERN_MAX_LENGTH:
            return value[: KEY_CONCERN_MAX_LENGTH - 3].rstrip() + "..."
        return value

    @field_validator("recommended_fix", mode="before")
    @classmethod
    def coerce_recommended_fix_length(cls, value):
        if isinstance(value, str) and len(value) > RECOMMENDED_FIX_MAX_LENGTH:
            return value[: RECOMMENDED_FIX_MAX_LENGTH - 3].rstrip() + "..."
        return value

    @field_validator("evidence_to_change_verdict", mode="before")
    @classmethod
    def coerce_evidence_length(cls, value):
        if isinstance(value, str) and len(value) > EVIDENCE_MAX_LENGTH:
            return value[: EVIDENCE_MAX_LENGTH - 3].rstrip() + "..."
        return value


class RoastPanel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict]

    @field_validator("verdicts")
    @classmethod
    def must_include_all_judges(cls, verdicts: list[Verdict]) -> list[Verdict]:
        expected = {judge.value for judge in judgeLabel}
        actual = {verdict.judge.value for verdict in verdicts}

        missing = expected - actual
        extra = actual - expected

        if missing or extra or len(verdicts) != len(expected):
            raise ValueError(
                f"Expected exactly one verdict from each judge. "
                f"Missing={missing}, extra={extra}, count={len(verdicts)}, expected={expected}"
            )

        return verdicts


class RoastDebateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict]
    final_synthesis: str = Field(
        min_length=20,
        max_length=5000,
        description="The final moderator synthesis after the judge debate.",
    )

    @field_validator("verdicts")
    @classmethod
    def must_include_all_judges(cls, verdicts: list[Verdict]) -> list[Verdict]:
        return RoastPanel(verdicts=verdicts).verdicts
