# The notifier, built by the deploy convention (command-center/D32) with the repository root as context:
#   docker build -f services/notify/Dockerfile --build-arg COMMIT_SHA=<sha> .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY services/notify/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY services/notify/notify ./notify
COPY services/notify/openapi.yaml ./

# The deploy sets COMMIT_SHA on the service too (command-center/D47); either way GET /version answers it.
ARG COMMIT_SHA=unknown
ENV COMMIT_SHA=${COMMIT_SHA}

# gunicorn keeps a control socket in the user's home, so the user has one.
RUN useradd --system --create-home notify
USER notify

# Cloud Run sets PORT. One process with threads, as Cloud Run recommends for a synchronous app. The access log
# timestamps every request, each tick included.
CMD exec gunicorn --bind ":${PORT:-8080}" --workers 1 --threads 8 --timeout 0 --access-logfile - \
    "notify.app:create_app()"
