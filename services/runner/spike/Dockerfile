# The session-runner Q1 spike: one container per session, as a Cloud Run job would run it.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# The wheel bundles the Claude Code binary, so nothing else is installed.
RUN pip install --no-cache-dir claude-agent-sdk==0.2.168

RUN useradd --create-home runner
USER runner

COPY spike.py /opt/spike/spike.py
ENTRYPOINT ["python", "/opt/spike/spike.py"]
