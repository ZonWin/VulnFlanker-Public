FROM golang:1.22-bookworm AS watchvuln-collector-builder

ARG GOPROXY=https://goproxy.cn,direct
ENV GOPROXY=${GOPROXY} \
    GOTOOLCHAIN=auto

WORKDIR /src

COPY tools/watchvuln-collector/go.mod tools/watchvuln-collector/go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY tools/watchvuln-collector ./
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -o /out/watchvuln-collector .

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY --from=watchvuln-collector-builder /out/watchvuln-collector ./bin/watchvuln-collector
COPY --from=watchvuln-collector-builder /out/watchvuln-collector /usr/local/bin/watchvuln-collector

RUN chmod +x /usr/local/bin/watchvuln-collector

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -e .
