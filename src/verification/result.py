"""Shared verification result types."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Check:
    code: str
    message: str
    blocking: bool = True


@dataclass
class VerificationResult:
    checks: list[Check] = field(default_factory=list)

    @property
    def failed(self) -> list[Check]:
        return [check for check in self.checks if check.blocking]

    @property
    def warnings(self) -> list[Check]:
        return [check for check in self.checks if not check.blocking]

    @property
    def ok(self) -> bool:
        return not self.failed

    def first_failure(self) -> Check | None:
        return self.failed[0] if self.failed else None
