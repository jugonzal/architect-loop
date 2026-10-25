"""Read the services' manifests: each service's deploy config, kept in its own folder (command-center/D46).

A manifest is `services/<service>/service.json` (the probe's is `scripts/gcp/probe/service.json`), one JSON object:

  identity   Required. {"name": "<service account ID>", "roles": ["roles/...", ...]}. The service and its jobs run as
             <name>@<project>.iam.gserviceaccount.com. bootstrap.sh creates it, grants it these roles on the project,
             and lets it read the secrets this manifest names, and no others.
  apis       The APIs the service needs beyond those every project has (APIS in common.sh). bootstrap.sh enables them.
  settings   Environment variables set by value: {"NAME": "value"}, or {"NAME": {"staging": "...", "production": "..."}}
             when the environments differ. A value may use {project}, {number} and {region}: the environment's
             project ID, its project number and the region. "TODO(owner)" marks a value only the owner can name, and
             deploy.sh refuses to deploy it until a commit names it.
  secrets    Environment variables filled from Secret Manager: {"NAME": "<secret name>"}, at its latest version. Only
             the name: the owner creates each secret and its value.
  cloudsql   The Cloud SQL instance the service connects to, by name, in the environment's project and region.
  firestore  The Firestore databases the service uses, by ID. bootstrap.sh creates each in the region.
  jobs       {"<job>": {"command": [...], "tasks": n, "max_retries": n, "task_timeout_s": n, "settings": {...},
             "secrets": {...}}}: Cloud Run jobs deployed with the service from the same image. A job runs as the
             service's identity, with the service's settings, secrets and Cloud SQL instance, plus its own.
  schedules  {"<name>": {"cron": "* * * * *", "time_zone": "Etc/UTC", "path": "/tick"}}: Cloud Scheduler jobs that
             POST to one of the service's paths on a cron (command-center/D67). Each is the Cloud Scheduler job
             <service>-<name> in the region, and calls https://<service>-<number>.<region>.run.app<path> with an
             OIDC token for the service's own identity and that URL as its audience. bootstrap.sh enables Cloud
             Scheduler and lets it mint those tokens; deploy.sh creates or updates each declared job, and deletes
             the service's jobs the manifest no longer declares, once the new revision answers /version.

deploy.sh applies the manifest of the commit it deploys; bootstrap.sh creates what the manifests in the working tree
declare. Both refuse a manifest that does not fit this format before they call gcloud. deploy.sh sets COMMIT_SHA
itself (command-center/D47), so no manifest may. docs/runbooks/deploy.md describes the format for people.

Standard library only, and it changes nothing anywhere: it reads manifests and writes the flags deploy.sh passes.

Usage:
  python3 manifest.py check <file> [--name=<path>] [--env=<staging|production>]
  python3 manifest.py check-all <repository root>
  python3 manifest.py render <file> --name=<path> --env=<environment> --project=<id> --region=<region>
                             --commit=<sha> [--number=<project number>] --out=<directory>
                             [--service=<service> --scheduled=<file>]
  python3 manifest.py fields <file>
  python3 manifest.py list <repository root> apis|identities|secrets|firestore|scheduled

render's --scheduled names the Cloud Scheduler jobs that exist in the region, one per line as
`gcloud scheduler jobs list --format='value(name,httpTarget.uri)'` prints them. It needs --service and --number when
the manifest declares schedules or the file names any job.
"""

import glob
import json
import os
import re
import sys

ENVIRONMENTS = ("staging", "production")
TODO = "TODO(owner)"
FIELDS = ("identity", "apis", "settings", "secrets", "cloudsql", "firestore", "jobs", "schedules")
JOB_FIELDS = ("command", "tasks", "max_retries", "task_timeout_s", "settings", "secrets")
SCHEDULE_FIELDS = ("cron", "time_zone", "path")
# The API a manifest with schedules needs. bootstrap.sh enables it for such a manifest, which need not list it.
SCHEDULER_API = "cloudscheduler.googleapis.com"
PLACEHOLDERS = ("project", "number", "region")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
# Set by deploy.sh or by Cloud Run itself, never by a manifest.
RESERVED = {
    "COMMIT_SHA": "deploy.sh sets it to the commit it deploys (command-center/D47)",
    "PORT": "Cloud Run sets it",
    "K_SERVICE": "Cloud Run sets it",
    "K_REVISION": "Cloud Run sets it",
    "K_CONFIGURATION": "Cloud Run sets it",
    "CLOUD_RUN_JOB": "Cloud Run sets it",
    "CLOUD_RUN_EXECUTION": "Cloud Run sets it",
    "CLOUD_RUN_TASK_INDEX": "Cloud Run sets it",
    "CLOUD_RUN_TASK_ATTEMPT": "Cloud Run sets it",
    "CLOUD_RUN_TASK_COUNT": "Cloud Run sets it",
}
# A setting whose name says it holds a secret belongs in secrets, so that no manifest holds a secret's value.
SECRET_LIKE = re.compile(r"KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|DATABASE_URL")
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ACCOUNT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
ROLE = re.compile(r"^roles/[A-Za-z0-9_.]+$")
API = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.googleapis\.com$")
SECRET_NAME = re.compile(r"^[A-Za-z0-9_-]{1,255}$")
INSTANCE = re.compile(r"^[a-z]([a-z0-9-]{0,78}[a-z0-9])?$")
DATABASE = re.compile(r"^[a-z][a-z0-9-]{2,61}[a-z0-9]$")
JOB = re.compile(r"^[a-z]([a-z0-9-]{0,47}[a-z0-9])?$")
SCHEDULE = re.compile(r"^[a-z]([a-z0-9-]{0,46}[a-z0-9])?$")
# One field of a cron: digits, names (JAN, MON), *, ranges, steps and lists. Cloud Scheduler checks the rest.
CRON_FIELD = re.compile(r"^[0-9A-Za-z*/,-]+$")
TIME_ZONE = re.compile(r"^(UTC|[A-Z][A-Za-z_]*(/[A-Za-z0-9_+-]+)+)$")
URL_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/?-]*$")
# A field that cannot work without APIs the service must then list. gcloud checks both Cloud SQL APIs before it
# attaches an instance, and a --quiet deploy is cancelled when one is not enabled.
NEEDS_API = {"cloudsql": ("sqladmin.googleapis.com", "sql-component.googleapis.com"),
             "firestore": ("firestore.googleapis.com",)}
MAX_VALUE = 32768


class Refused(Exception):
    pass


def load(path):
    def no_repeats(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise Refused("%r appears twice in one object" % key)
            seen[key] = value
        return seen

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f, object_pairs_hook=no_repeats)
    except ValueError as error:
        raise Refused("not JSON: %s" % error)


def is_int(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _variables(where, mapping, kind, seen, found):
    """Check one settings or secrets object, recording each name in `seen` so that none is declared twice."""
    if not isinstance(mapping, dict):
        found.append('%s: an object of environment variables, {"NAME": ...}' % where)
        return
    for name, value in mapping.items():
        at = "%s.%s" % (where, name)
        if not ENV_NAME.match(name):
            found.append("%s: an environment variable's name is upper case letters, digits and _" % at)
            continue
        if name in RESERVED:
            found.append("%s: %s, so no manifest sets it" % (at, RESERVED[name]))
            continue
        if name in seen:
            found.append("%s: already declared in %s" % (at, seen[name]))
            continue
        seen[name] = where
        if kind == "secrets":
            if not isinstance(value, str) or not SECRET_NAME.match(value):
                found.append("%s: the name of a secret in Secret Manager (letters, digits, - and _), never its value"
                             % at)
            continue
        if SECRET_LIKE.search(name):
            found.append("%s: its name says it holds a secret; name its secret in secrets instead of a value here" % at)
            continue
        if isinstance(value, dict):
            if sorted(value) != sorted(ENVIRONMENTS):
                found.append('%s: a value per environment names both, {"staging": ..., "production": ...}' % at)
                continue
            values = [value[env] for env in ENVIRONMENTS]
        else:
            values = [value]
        for one in values:
            if not isinstance(one, str):
                found.append("%s: a value is a string (environment variables are text)" % at)
            elif len(one) > MAX_VALUE:
                found.append("%s: a value of more than %d characters" % (at, MAX_VALUE))
            elif "-----BEGIN" in one:
                found.append("%s: holds a key; keep it in Secret Manager and name it in secrets" % at)
            else:
                unknown = sorted(set(PLACEHOLDER.findall(one)) - set(PLACEHOLDERS))
                if unknown:
                    found.append("%s: {%s} is not a placeholder; use {project}, {number} or {region}"
                                 % (at, "}, {".join(unknown)))


def problems(manifest):
    """Every way the manifest does not fit the format, as messages; empty when it fits."""
    if not isinstance(manifest, dict):
        return ["a manifest is a JSON object"]
    found = []
    for key in manifest:
        if key not in FIELDS:
            found.append("%s: not a field of a manifest (%s)" % (key, ", ".join(FIELDS)))

    identity = manifest.get("identity")
    if identity is None:
        found.append("identity: missing; every service names the runtime identity it runs as")
    elif not isinstance(identity, dict) or "name" not in identity or set(identity) - {"name", "roles"}:
        found.append('identity: {"name": "<service account ID>", "roles": ["roles/...", ...]}')
    else:
        name = identity["name"]
        if not isinstance(name, str) or not ACCOUNT_ID.match(name):
            found.append("identity.name: a service account ID, 6 to 30 lowercase letters, digits and hyphens")
        elif name == "deploy":
            found.append("identity.name: deploy is the deploy identity (common.sh); a service runs as its own")
        roles = identity.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(r, str) and ROLE.match(r) for r in roles):
            found.append("identity.roles: a list of predefined roles, each roles/<name>")
        elif len(set(roles)) != len(roles):
            found.append("identity.roles: a role is listed twice")

    apis = manifest.get("apis", [])
    if not isinstance(apis, list) or not all(isinstance(a, str) and API.match(a) for a in apis):
        found.append("apis: a list of service names, each <name>.googleapis.com")
        apis = []
    elif len(set(apis)) != len(apis):
        found.append("apis: an API is listed twice")

    seen = {}
    _variables("settings", manifest.get("settings", {}), "settings", seen, found)
    _variables("secrets", manifest.get("secrets", {}), "secrets", seen, found)

    cloudsql = manifest.get("cloudsql")
    if cloudsql is not None and (not isinstance(cloudsql, str) or not INSTANCE.match(cloudsql)):
        found.append("cloudsql: the name of a Cloud SQL instance in the environment's project and region")
    firestore = manifest.get("firestore", [])
    if not isinstance(firestore, list) or not all(isinstance(d, str) and DATABASE.match(d) for d in firestore):
        found.append("firestore: a list of database IDs, each 4 to 63 lowercase letters, digits and hyphens")
    elif len(set(firestore)) != len(firestore):
        found.append("firestore: a database is listed twice")
    for field, needed in NEEDS_API.items():
        missing = [api for api in needed if api not in apis]
        if manifest.get(field) and missing:
            found.append("%s: needs %s in apis" % (field, " and ".join(missing)))

    jobs = manifest.get("jobs", {})
    if not isinstance(jobs, dict):
        found.append('jobs: an object, {"<job>": {...}}')
        jobs = {}
    for name, job in jobs.items():
        at = "jobs.%s" % name
        if not JOB.match(name):
            found.append("%s: a job's name is lowercase letters, digits and hyphens" % at)
            continue
        if not isinstance(job, dict):
            found.append("%s: an object with %s" % (at, ", ".join(JOB_FIELDS)))
            continue
        for key in job:
            if key not in JOB_FIELDS:
                found.append("%s.%s: not a field of a job (%s)" % (at, key, ", ".join(JOB_FIELDS)))
        for key in ("command", "tasks", "max_retries", "task_timeout_s"):
            if key not in job:
                found.append("%s.%s: missing; a job states it, so every deploy sets it" % (at, key))
        command = job.get("command", ["-"])
        if (not isinstance(command, list) or not command
                or not all(isinstance(c, str) and c and "," not in c and "\n" not in c for c in command)):
            found.append("%s.command: a list of strings, none empty or with a comma" % at)
        if "tasks" in job and not is_int(job["tasks"], 1, 10000):
            found.append("%s.tasks: a whole number from 1" % at)
        if "max_retries" in job and not is_int(job["max_retries"], 0, 10):
            found.append("%s.max_retries: a whole number from 0 to 10" % at)
        if "task_timeout_s" in job and not is_int(job["task_timeout_s"], 1, 86400):
            found.append("%s.task_timeout_s: whole seconds, from 1 to 86400" % at)
        names = dict(seen)
        _variables(at + ".settings", job.get("settings", {}), "settings", names, found)
        _variables(at + ".secrets", job.get("secrets", {}), "secrets", names, found)

    schedules = manifest.get("schedules", {})
    if not isinstance(schedules, dict):
        found.append('schedules: an object, {"<name>": {"cron": ..., "time_zone": ..., "path": ...}}')
        schedules = {}
    for name, schedule in schedules.items():
        at = "schedules.%s" % name
        if not SCHEDULE.match(name):
            found.append("%s: a schedule's name is lowercase letters, digits and hyphens, at most 48" % at)
            continue
        if not isinstance(schedule, dict):
            found.append("%s: an object with %s" % (at, ", ".join(SCHEDULE_FIELDS)))
            continue
        for key in schedule:
            if key not in SCHEDULE_FIELDS:
                found.append("%s.%s: not a field of a schedule (%s)" % (at, key, ", ".join(SCHEDULE_FIELDS)))
        for key in SCHEDULE_FIELDS:
            if key not in schedule:
                found.append("%s.%s: missing; a schedule states its cron, its time zone and the path it calls"
                             % (at, key))
        cron = schedule.get("cron", "* * * * *")
        if not isinstance(cron, str) or len(cron.split()) != 5 or cron != " ".join(cron.split()) or not all(
                CRON_FIELD.match(f) for f in cron.split()):
            found.append('%s.cron: five fields separated by single spaces, as in "*/5 * * * *"' % at)
        time_zone = schedule.get("time_zone", "UTC")
        if not isinstance(time_zone, str) or not TIME_ZONE.match(time_zone) or not _known_zone(time_zone):
            found.append('%s.time_zone: a time zone from the tz database, such as "Etc/UTC" or "America/New_York"'
                         % at)
        path = schedule.get("path", "/")
        if not isinstance(path, str) or not URL_PATH.match(path) or len(path) > 2000:
            found.append("%s.path: a path on the service, starting with /, without spaces or #" % at)
    return found


def _known_zone(name):
    """Whether the tz database knows the zone, when this Python can read one; the pattern alone otherwise."""
    try:
        import zoneinfo
        known = zoneinfo.available_timezones()
    except ImportError:
        return True
    return not known or name in known


def _each_setting(manifest):
    yield "settings", manifest.get("settings", {})
    for name, job in sorted(manifest.get("jobs", {}).items()):
        yield "jobs.%s.settings" % name, job.get("settings", {})


def todos(manifest, env):
    """The settings still left TODO(owner) for this environment."""
    left = []
    for where, settings in _each_setting(manifest):
        for name, value in sorted(settings.items()):
            if TODO in (value[env] if isinstance(value, dict) else value):
                left.append("%s.%s" % (where, name))
    return left


def checked(path, name=None, env=None):
    """The manifest at `path`, or Refused naming every problem."""
    label = name or path
    try:
        manifest = load(path)
    except Refused as error:
        raise Refused("%s: %s" % (label, error))
    found = problems(manifest)
    if found:
        raise Refused("%s does not fit the manifest format (docs/runbooks/deploy.md):\n%s"
                      % (label, "\n".join("  " + p for p in found)))
    if env is not None:
        if env not in ENVIRONMENTS:
            raise Refused("unknown environment %r: use staging or production" % env)
        left = todos(manifest, env)
        if left:
            raise Refused("%s leaves %s TODO(owner) for %s; name %s in a pull request first"
                          % (label, ", ".join(left), env, "it" if len(left) == 1 else "them"))
    return manifest


def identity_of(manifest, project):
    return "%s@%s.iam.gserviceaccount.com" % (manifest["identity"]["name"], project)


def service_url(service, facts):
    """Cloud Run's URL for the service, which LOOP.md §3 reads and the status service calls (command-center/D32)."""
    return "https://%s-%s.%s.run.app" % (service, facts["number"], facts["region"])


def render(manifest, env, facts, commit, service_name=None, scheduled=()):
    """What the manifest means in one environment: the identity, each target's variables and secrets, and what to
    do to each Cloud Scheduler job (command-center/D67).

    `scheduled` is every Cloud Scheduler job in the region, as (job ID, the URI it calls). The service's own are the
    ones that call its URL, or that carry a name its manifest declares; each declared one is created or updated,
    and each other one of the service's is deleted. Jobs that call other services are left alone.
    """

    def resolve(where, name, value):
        value = value[env] if isinstance(value, dict) else value

        def fill(match):
            if not facts.get(match.group(1)):
                raise Refused("%s.%s uses {%s}, which deploy.sh did not give" % (where, name, match.group(1)))
            return facts[match.group(1)]

        return PLACEHOLDER.sub(fill, value)

    def variables(where, settings):
        return {name: resolve(where, name, value) for name, value in settings.items()}

    project, region = facts["project"], facts["region"]
    cloudsql = manifest.get("cloudsql")
    service = {
        "env": dict(variables("settings", manifest.get("settings", {})), COMMIT_SHA=commit),
        "secrets": dict(manifest.get("secrets", {})),
        "cloudsql": "%s:%s:%s" % (project, region, cloudsql) if cloudsql else None,
    }
    jobs = {}
    for name, job in sorted(manifest.get("jobs", {}).items()):
        jobs[name] = {
            "env": dict(service["env"], **variables("jobs.%s.settings" % name, job.get("settings", {}))),
            "secrets": dict(service["secrets"], **job.get("secrets", {})),
            "cloudsql": service["cloudsql"],
            "command": job["command"],
            "tasks": job["tasks"],
            "max_retries": job["max_retries"],
            "task_timeout_s": job["task_timeout_s"],
        }
    schedules = manifest.get("schedules", {})
    plan = []
    if schedules or scheduled:
        if not service_name or not facts.get("number"):
            raise Refused("schedules need the service's name and the project's number, which deploy.sh did not give")
        url = service_url(service_name, facts)
        declared = {"%s-%s" % (service_name, name): schedule for name, schedule in sorted(schedules.items())}
        existing = dict(scheduled)
        for job_id, schedule in declared.items():
            plan.append({"action": "update" if job_id in existing else "create", "id": job_id,
                         "cron": schedule["cron"], "time_zone": schedule["time_zone"],
                         "uri": url + schedule["path"], "audience": url})
        for job_id, uri in sorted(existing.items()):
            if job_id not in declared and (uri == url or uri.startswith(url + "/")):
                plan.append({"action": "delete", "id": job_id, "uri": uri})
    return {"identity": identity_of(manifest, project), "service": service, "jobs": jobs, "schedules": plan}


def parse_scheduled(text):
    """The jobs `gcloud scheduler jobs list --format='value(name,httpTarget.uri)'` printed, as (job ID, URI)."""
    found = []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, uri = line.partition("\t")
        found.append((name.strip().rsplit("/", 1)[-1], uri.strip()))
    return found


def _secrets_flag(secrets):
    if not secrets:
        return "--clear-secrets"
    return "--set-secrets=" + ",".join("%s=%s:latest" % (name, secrets[name]) for name in sorted(secrets))


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_flags(config, out):
    """Write the flags deploy.sh passes to gcloud, one per line, and each target's variables as a YAML file.

    --env-vars-file and --set-secrets replace everything the service had, so the deploy leaves exactly what the
    manifest says. A JSON object is YAML, so the variables file is JSON.
    """
    os.makedirs(out, exist_ok=True)
    service = config["service"]
    _write(os.path.join(out, "service.env.yaml"), json.dumps(service["env"], indent=1, sort_keys=True,
                                                             ensure_ascii=False) + "\n")
    flags = ["--service-account=" + config["identity"],
             "--env-vars-file=" + os.path.join(out, "service.env.yaml"),
             _secrets_flag(service["secrets"]),
             "--set-cloudsql-instances=" + service["cloudsql"] if service["cloudsql"] else "--clear-cloudsql-instances"]
    _write(os.path.join(out, "service.flags"), "".join(f + "\n" for f in flags))
    for name, job in config["jobs"].items():
        env_file = os.path.join(out, "job-%s.env.yaml" % name)
        _write(env_file, json.dumps(job["env"], indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        flags = ["--service-account=" + config["identity"], "--env-vars-file=" + env_file,
                 _secrets_flag(job["secrets"])]
        # Cloud Run jobs have no flag that clears a Cloud SQL instance, so a job without one is left as it is.
        if job["cloudsql"]:
            flags.append("--set-cloudsql-instances=" + job["cloudsql"])
        flags += ["--command=" + job["command"][0], "--args=" + ",".join(job["command"][1:]),
                  "--tasks=%d" % job["tasks"], "--max-retries=%d" % job["max_retries"],
                  "--task-timeout=%ds" % job["task_timeout_s"]]
        _write(os.path.join(out, "job-%s.flags" % name), "".join(f + "\n" for f in flags))
    _write(os.path.join(out, "jobs"), "".join(name + "\n" for name in config["jobs"]))
    # What to do to each Cloud Scheduler job, one `<action> <job ID>` per line; create and update read their flags.
    for step in config["schedules"]:
        if step["action"] != "delete":
            flags = ["--schedule=" + step["cron"], "--time-zone=" + step["time_zone"], "--uri=" + step["uri"],
                     "--http-method=POST", "--oidc-service-account-email=" + config["identity"],
                     "--oidc-token-audience=" + step["audience"]]
            _write(os.path.join(out, "schedule-%s.flags" % step["id"]), "".join(f + "\n" for f in flags))
    _write(os.path.join(out, "schedules"), "".join("%s %s\n" % (s["action"], s["id"]) for s in config["schedules"]))


def summary(config, label):
    service = config["service"]
    lines = ["config from %s: runs as %s" % (label, config["identity"]),
             "  settings  %s" % ", ".join(sorted(service["env"])),
             "  secrets   %s" % (", ".join("%s from %s" % (k, v) for k, v in sorted(service["secrets"].items()))
                                 or "none"),
             "  Cloud SQL %s" % (service["cloudsql"] or "none")]
    for name, job in config["jobs"].items():
        lines.append("  job %s: %s; tasks %d, retries %d, timeout %d s; settings %s; secrets %s" % (
            name, " ".join(job["command"]), job["tasks"], job["max_retries"], job["task_timeout_s"],
            ", ".join(sorted(job["env"])), ", ".join(sorted(job["secrets"])) or "none"))
    for step in config["schedules"]:
        if step["action"] == "delete":
            lines.append("  schedule %s: delete, no longer declared (it called %s)" % (step["id"], step["uri"]))
        else:
            lines.append("  schedule %s: %s, %s %s, POST %s as %s" % (
                step["id"], step["action"], step["cron"], step["time_zone"], step["uri"], config["identity"]))
    return "\n".join(lines)


def manifests(root):
    """Every manifest in the working tree at `root`, as (label, path relative to root, manifest), checked."""
    paths = sorted(glob.glob(os.path.join(root, "services", "*", "service.json")))
    probe = os.path.join(root, "scripts", "gcp", "probe", "service.json")
    if os.path.exists(probe):
        paths.append(probe)
    found, errors, owners = [], [], {}
    for path in paths:
        rel = os.path.relpath(path, root)
        label = "probe" if path == probe else os.path.basename(os.path.dirname(path))
        try:
            manifest = checked(path, rel)
        except Refused as error:
            errors.append(str(error))
            continue
        name = manifest["identity"]["name"]
        if name in owners:
            errors.append("%s: identity %s is already %s's; each service runs as its own" % (rel, name, owners[name]))
            continue
        owners[name] = rel
        found.append((label, rel, manifest))
    if errors:
        raise Refused("\n".join(errors))
    return found


def listing(root, kind):
    lines = []
    for label, rel, m in manifests(root):
        name = m["identity"]["name"]
        if kind == "apis":
            lines += m.get("apis", []) + ([SCHEDULER_API] if m.get("schedules") else [])
        elif kind == "identities":
            lines.append(" ".join([name, label] + m["identity"].get("roles", [])))
        elif kind == "secrets":
            secrets = set(m.get("secrets", {}).values())
            for job in m.get("jobs", {}).values():
                secrets |= set(job.get("secrets", {}).values())
            lines += ["%s %s %s" % (name, secret, label) for secret in sorted(secrets)]
        elif kind == "firestore":
            lines += ["%s %s" % (database, label) for database in m.get("firestore", [])]
        elif kind == "scheduled":
            lines += ["%s %s" % (name, label)] if m.get("schedules") else []
        else:
            raise Refused("list what? apis, identities, secrets, firestore or scheduled, not %r" % kind)
    unique = []
    for line in lines:
        if line not in unique:
            unique.append(line)
    return unique


def options(argv):
    found, rest = {}, []
    for arg in argv:
        if arg.startswith("--") and "=" in arg:
            key, _, value = arg[2:].partition("=")
            found[key] = value
        else:
            rest.append(arg)
    return found, rest


def main(argv):
    opts, args = options(argv[1:])
    command = args[0] if args else ""
    try:
        if command == "check" and len(args) == 2:
            checked(args[1], opts.get("name"), opts.get("env"))
        elif command == "fields" and len(args) == 2:
            for field in sorted(checked(args[1], opts.get("name"))):
                print(field)
        elif command == "check-all" and len(args) == 2:
            manifests(args[1])
        elif command == "render" and len(args) == 2:
            label = opts.get("name", args[1])
            manifest = checked(args[1], label, opts["env"])
            facts = {"project": opts["project"], "region": opts["region"], "number": opts.get("number", "")}
            scheduled = []
            if opts.get("scheduled"):
                with open(opts["scheduled"], encoding="utf-8") as f:
                    scheduled = parse_scheduled(f.read())
            config = render(manifest, opts["env"], facts, opts["commit"], opts.get("service"), scheduled)
            write_flags(config, opts["out"])
            print(summary(config, label))
        elif command == "list" and len(args) == 3:
            for line in listing(args[1], args[2]):
                print(line)
        else:
            print(__doc__.split("Usage:", 1)[1].rstrip(), file=sys.stderr)
            return 2
    except Refused as error:
        print("manifest: %s" % error, file=sys.stderr)
        return 1
    except KeyError as error:
        print("manifest: %s needs --%s=" % (command, error.args[0]), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
