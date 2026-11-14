# The runner. The dispatching service and a session's job run this same image (command-center/D32).
# Build from the repository root:  docker build -f services/runner/Dockerfile --build-arg COMMIT_SHA=<sha> .
FROM python:3.12-slim

# git for the session's own clone, gh because the skills open pull requests with it, and curl because a session
# runs the project's commands: scripts/gcp/served.sh reads each LOOP.md §3 row's served commit with it, and without
# it a session's /loop-status reads every service row as unknown. Only gnupg is here just to fetch gh's key.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl gnupg \
 && install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh \
 && apt-get purge -y gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# The Agent SDK's wheel bundles the Claude Code binary, so nothing else is installed for it.
COPY services/runner/requirements.txt /opt/runner/requirements.txt
RUN pip install --no-cache-dir -r /opt/runner/requirements.txt

COPY services/runner/runner /opt/runner/runner

# /version answers this commit (D32).
ARG COMMIT_SHA=""
ENV COMMIT_SHA=${COMMIT_SHA} PYTHONPATH=/opt/runner PYTHONUNBUFFERED=1

RUN useradd --create-home runner
USER runner
WORKDIR /home/runner

# The service. A session's job runs the same image with the command `python -m runner job`.
CMD exec gunicorn --bind ":${PORT:-8080}" --workers 1 --threads 8 --timeout 60 runner.main:application
