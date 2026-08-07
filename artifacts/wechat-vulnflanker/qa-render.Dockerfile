FROM vulnflanker-console-api

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       libreoffice-writer-nogui \
       fonts-noto-cjk \
       fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
