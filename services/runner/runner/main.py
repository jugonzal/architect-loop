"""Wiring: the service (`gunicorn runner.main:application`) and a session's job (`python -m runner job`), both
configured from environment variables and secrets mounted as environment variables (command-center/D32)."""

import asyncio
import logging
import os

from .api import Api
from .config import Config
from .dispatch import Dispatcher
from .github import AppAuth, RestGitHub
from .launcher import CloudRunJobs
from .session import SessionJob
from .store import SqliteStore
from .workspace import Workspace

PRIVATE_KEY = "RUNNER_APP_PRIVATE_KEY"  # the runner app's key, mounted from Secret Manager (D27)
FIRESTORE = "firestore:"  # RUNNER_STORE=firestore:<database>, as services/runner/service.json sets it


def store_from(config):
    """The store RUNNER_STORE names. `firestore:<database>` is that Firestore database in the runner's project, which
    the service and every session's job share across containers (runner-store C1, per command-center/D44). Anything
    else is the path of a SQLite file, which only one machine can share, for local runs and tests."""
    if config.store_path.startswith(FIRESTORE):
        database = config.store_path[len(FIRESTORE):]
        if not database:
            raise ValueError(f"RUNNER_STORE={config.store_path} names no database: write firestore:<database>")
        from .firestore_store import FirestoreStore  # only a store on Firestore needs Firestore's client

        return FirestoreStore(database, project=config.gcp_project or None, seeds=config.seeds)
    return SqliteStore(config.store_path, seeds=config.seeds)


def github_from(config, private_key):
    auth = AppAuth(config.app_id, config.app_installation_id, private_key, config.project.split("/", 1)[1])
    return RestGitHub(config.project, auth, app_slug=config.app_slug, main_branch=config.main_branch)


def service_from_env(env):
    config = Config.from_env(env)
    store = store_from(config)
    launcher = CloudRunJobs(config.gcp_project, config.region, config.job)
    return Api(Dispatcher(config, store, github_from(config, env.get(PRIVATE_KEY, "")), launcher))


_service = None


def application(environ, start_response):
    global _service
    if _service is None:
        logging.basicConfig(level=logging.INFO)
        _service = service_from_env(os.environ)
    return _service(environ, start_response)


def job_from_env(env):
    """The session's job. It takes the app's key out of `env` first, so the session never inherits it."""
    private_key = env.pop(PRIVATE_KEY, "")
    config = Config.from_env(env)
    session_id = env.get("RUNNER_SESSION_ID", "")
    if not session_id:
        raise SystemExit("RUNNER_SESSION_ID is not set")
    if not (config.app_slug and config.app_id and config.app_installation_id and private_key):
        raise SystemExit("the runner's GitHub App is not configured: RUNNER_APP_ID, RUNNER_APP_INSTALLATION_ID, "
                         "RUNNER_APP_SLUG and RUNNER_APP_PRIVATE_KEY")
    github = github_from(config, private_key)
    login = config.bot_login
    identity = (login, f"{github.bot_user_id()}+{login}@users.noreply.github.com")
    workspace = Workspace(config.clone_url, config.workdir, identity, main_branch=config.main_branch,
                          credential_helper="!gh auth git-credential")
    return SessionJob(config, store_from(config), github, workspace), session_id


def run_job():
    logging.basicConfig(level=logging.INFO)
    job, session_id = job_from_env(os.environ)
    session = asyncio.run(job.run(session_id))
    logging.getLogger("runner").info("session %s ended: %s", session_id, session and session.outcome)
    # Once the store records how it ended, the task succeeded, whatever the outcome; a retry could only spend twice.
    return 0 if session and session.state == "ended" else 1


def serve(port):
    """A local server for trying the API by hand; the deployed service runs under gunicorn."""
    from wsgiref.simple_server import make_server

    with make_server("", port, application) as server:
        server.serve_forever()
