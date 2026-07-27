from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, require_current_user
from app.db.base import Base
from app.db.models import User
from app.main import app
from app.services.auth import hash_password


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    try:
        with TestingSessionLocal() as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def authenticated_user(db_session: Session) -> User:
    user = User(
        id="test-admin-user",
        username="test-admin",
        display_name="Test Admin",
        password_hash=hash_password("test-password"),
        is_superuser=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def anonymous_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(
    db_session: Session,
    authenticated_user: User,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_require_current_user() -> User:
        return authenticated_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_current_user] = override_require_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
