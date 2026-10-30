FROM python:3.11-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==9.1.1

RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /work/ledger-svc \
    && chown agent:agent /work/ledger-svc

USER agent
WORKDIR /work/ledger-svc

RUN git config --global user.name "dev" \
    && git config --global user.email "dev@example.com"

# History is rebuilt from a bind mount so the build inputs never land in a layer.
RUN --mount=type=bind,source=.,target=/build \
    python /build/history/build_history.py /build/history /build/repo /work/ledger-svc

RUN mkdir -p logs && touch logs/agent_audit.log

CMD ["tail", "-f", "/dev/null"]
