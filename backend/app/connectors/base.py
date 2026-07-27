from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class RawIntelRecord:
    source_name: str
    external_id: str
    title: str
    payload: dict
    fetched_at: datetime
    references: list[str] = field(default_factory=list)
    event_type: str = "vulnerability"
    source_url: str | None = None


class VulnerabilitySourceConnector(ABC):
    source_name: str

    @abstractmethod
    def fetch(self, **kwargs) -> list[RawIntelRecord]:
        """Fetch raw vulnerability records from a single source."""
