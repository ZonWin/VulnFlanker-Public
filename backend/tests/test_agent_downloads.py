from __future__ import annotations

import io
import tarfile


def test_agent_source_archive_is_served_from_platform(client) -> None:
    response = client.get("/api/v1/agents/downloads/source.tar.gz")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gzip")

    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        names = set(archive.getnames())

    assert (
        "vulnflanker-agent-source/agent/cmd/vulnflanker-agent/main.go" in names
    )
    assert "vulnflanker-agent-source/agent/go.mod" in names


def test_unknown_agent_binary_arch_returns_404(client) -> None:
    response = client.get(
        "/api/v1/agents/downloads/vulnflanker-agent-linux-sparc"
    )

    assert response.status_code == 404
