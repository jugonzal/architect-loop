# The status service, built by the deploy convention (command-center/D32) with the repository root as context:
#   docker build -f services/status/Dockerfile --build-arg COMMIT_SHA=<sha> .
# It derives with loop-status's own script from the same commit (command-center/D13, D15), so the image keeps the
# repository's layout: /srv/services/status/status beside /srv/plugin/skills/loop-status/scripts.
FROM python:3.12-slim

# git for the service's clone of each project; the derivation and check_loop_pr.sh need nothing else.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY services/status/requirements.txt services/status/requirements.txt
RUN pip install --no-cache-dir -r services/status/requirements.txt

COPY plugin/skills/loop-status/scripts plugin/skills/loop-status/scripts
COPY services/status/status services/status/status

# The deploy sets COMMIT_SHA on the service too (command-center/D47); either way GET /version answers it.
ARG COMMIT_SHA=unknown
ENV COMMIT_SHA=${COMMIT_SHA} PYTHONPATH=/srv/services/status

# The clones live under STATUS_CACHE_DIR (/tmp/status), which Cloud Run keeps in memory; gunicorn keeps a control
# socket in the user's home, so the user has one.
RUN useradd --system --create-home status
USER status

# Cloud Run sets PORT. One process, so every request shares one cache and one clone; threads for concurrent reads,
# which share one gather. The access log timestamps every request, webhook deliveries included.
CMD exec gunicorn --bind ":${PORT:-8080}" --workers 1 --threads 8 --timeout 0 --access-logfile - \
    "status.app:create_app()"
