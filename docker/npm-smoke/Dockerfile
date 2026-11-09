# Throwaway lab image: Python (for PyInstaller) + Node (for npm) in one container,
# so `npx manji-downloader` and `npm install -g manji-downloader` can be exercised
# without touching the host.
FROM python:3.12-slim

ARG NODE_VERSION=20.18.1
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=3.12 \
    npm_config_fund=false \
    npm_config_audit=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates xz-utils binutils bash \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv \
    && rm -rf /var/lib/apt/lists/*

RUN node --version && npm --version && uv --version

WORKDIR /src
COPY . /src

RUN uv sync --frozen --group build

ENTRYPOINT ["/src/docker/npm-smoke/run.sh"]
