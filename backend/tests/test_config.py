from app.core.config import Settings


def test_watchvuln_monitor_limit_accepts_empty_env_value(monkeypatch) -> None:
    monkeypatch.setenv("VULNFLANKER_WATCHVULN_MONITOR_LIMIT", "")

    settings = Settings(_env_file=None)

    assert settings.watchvuln_monitor_limit is None


def test_watchvuln_monitor_limit_accepts_integer_env_value(monkeypatch) -> None:
    monkeypatch.setenv("VULNFLANKER_WATCHVULN_MONITOR_LIMIT", "25")

    settings = Settings(_env_file=None)

    assert settings.watchvuln_monitor_limit == 25


def test_cisa_kev_monitor_limit_accepts_empty_env_value(monkeypatch) -> None:
    monkeypatch.setenv("VULNFLANKER_CISA_KEV_MONITOR_LIMIT", "")

    settings = Settings(_env_file=None)

    assert settings.cisa_kev_monitor_limit is None
