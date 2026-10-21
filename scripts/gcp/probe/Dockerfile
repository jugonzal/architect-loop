# The probe (command-center/environments C2): the smallest container that follows command-center/D32.
# deploy.sh builds it with the repository root as the context: sh scripts/gcp/deploy.sh probe <env> <sha>
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
COPY scripts/gcp/probe/server.py /srv/server.py
USER nobody
CMD ["python3", "/srv/server.py"]
