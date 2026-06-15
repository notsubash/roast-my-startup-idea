from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator

class VerdictLabel(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CONDITIONAL = "CONDITIONAL"

class judgeLabel(str, Enum):
    VC = "vc"
    ENGINEER = "engineer"
    PM = "pm"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"

class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: judgeLabel
    verdict: VerdictLabel
    roast: str = Field(min_length=20, max_length=1200, description="A sharp, 1-3 sentence critique of the startup idea")
    score:int = Field(ge=1, le=10, description="A score between 1 and 10 based on the quality of the critique")
    key_concern: str = Field(min_length=5, max_length=800, description="The #1 issue with the startup idea")

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
