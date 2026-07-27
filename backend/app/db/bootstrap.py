from app.db.base import Base
from app.db.models import (
    Asset,
    AssetComponent,
    IntelRawEvent,
    MatchResult,
    Vulnerability,
    VulnerabilitySource,
)
from app.db.session import engine


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
