# The local harness's fakes (command-center/D53): GitHub, Cloud Run's job launch, the metadata server, and the
# forwards from the host to the services. harness.py builds it with the repository root as the context.
FROM python:3.12-slim

# git serves the project's repository over smart HTTP, and openssl signs the metadata server's ID tokens.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssl \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'

ENV PYTHONUNBUFFERED=1
COPY scripts/local/fakes/server.py scripts/local/fakes/fakesdk.py /srv/fakes/

# Root, to reach the Docker socket that the fake Cloud Run starts each job's container through.
CMD ["python3", "/srv/fakes/server.py"]
