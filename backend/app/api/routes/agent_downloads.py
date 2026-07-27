from __future__ import annotations

import io
import tarfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_SOURCE_DIR = REPO_ROOT / "agent"
AGENT_BIN_DIR = AGENT_SOURCE_DIR / "bin"
AGENT_SOURCE_PREFIX = Path("vulnflanker-agent-source") / "agent"
AGENT_BINARY_FILES = {
    "amd64": "vulnflanker-agent-linux-amd64",
    "arm64": "vulnflanker-agent-linux-arm64",
}


def _source_archive_bytes() -> io.BytesIO:
    if not AGENT_SOURCE_DIR.exists():
        raise HTTPException(status_code=404, detail="Agent source directory not found")

    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for path in sorted(AGENT_SOURCE_DIR.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(AGENT_SOURCE_DIR)
            if relative_path.parts and relative_path.parts[0] == "bin":
                continue
            tar.add(path, arcname=AGENT_SOURCE_PREFIX / relative_path)
    archive.seek(0)
    return archive


@router.get("/source.tar.gz")
async def download_agent_source() -> StreamingResponse:
    return StreamingResponse(
        _source_archive_bytes(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": (
                'attachment; filename="vulnflanker-agent-source.tar.gz"'
            )
        },
    )


@router.get("/vulnflanker-agent-linux-{arch}")
async def download_agent_binary(arch: str) -> FileResponse:
    binary_name = AGENT_BINARY_FILES.get(arch)
    if binary_name is None:
        raise HTTPException(status_code=404, detail="Unsupported agent binary arch")

    binary_path = AGENT_BIN_DIR / binary_name
    if not binary_path.is_file():
        raise HTTPException(status_code=404, detail="Agent binary has not been built")

    return FileResponse(
        binary_path,
        media_type="application/octet-stream",
        filename=binary_name,
    )
