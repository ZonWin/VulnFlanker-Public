from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class VerificationContext:
    asset_id: str
    task_id: str
    parameters: dict = field(default_factory=dict)


@dataclass(slots=True)
class VerificationResult:
    status: str
    summary: str
    evidence: list[dict] = field(default_factory=list)


class VerificationPlugin(ABC):
    plugin_id: str
    version: str
    capability_level: str = "read-only"

    @abstractmethod
    def execute(self, context: VerificationContext) -> VerificationResult:
        """Run a controlled verification check and return structured evidence."""

