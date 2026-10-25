# Shared by bootstrap.sh and deploy.sh, which source it after setting $here to the repository root.
# The names here are the convention every service follows (command-center/D32).

REGION=us-east1
# The Artifact Registry repository in each project. An image is <REGION>-docker.pkg.dev/<project>/services/<name>:<sha>.
REPOSITORY=services
# The deploy identity: deploy@<project>.iam.gserviceaccount.com. deploy.sh acts as it.
DEPLOY_ACCOUNT=deploy
# The roles the deploy identity holds on its project: deploy Cloud Run services and make /version public, push
# images, and run a service as its runtime identity.
DEPLOY_ROLES="roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser"
# The APIs each project enables. Budgets are created through the project, so it enables their API too.
APIS="run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com billingbudgets.googleapis.com"
# Cloud Scheduler, for a manifest that declares schedules (command-center/D67). bootstrap.sh enables its API, gives
# the deploy identity this role so that deploy.sh can create, update and delete the jobs, and lets the API's service
# agent, service-<project number>@gcp-sa-cloudscheduler.iam.gserviceaccount.com, mint OIDC tokens as each identity
# whose manifest declares one. A project with no such manifest gets none of these.
SCHEDULER_API=cloudscheduler.googleapis.com
SCHEDULER_DEPLOY_ROLE=roles/cloudscheduler.admin
# The environment variable that carries the commit a service was built from. Its GET /version answers it.
COMMIT_VAR=COMMIT_SHA
# The services in services/<name>/. Each has one LOOP.md §3 row per environment.
SERVICES="status runner threads notify"
PROJECTS="$here/scripts/gcp/projects.txt"

# Print the GCP project ID of an environment, or say what is missing and fail.
project_of() {
  case $1 in
    staging|production) ;;
    *) echo "unknown environment '$1': use staging or production" >&2; return 2 ;;
  esac
  id=$(awk -v env="$1" '$1 == env { print $2; exit }' "$PROJECTS")
  case $id in
    ''|'TODO(owner)')
      echo "TODO(owner): name $1's GCP project ID in scripts/gcp/projects.txt first" >&2
      return 1 ;;
  esac
  if ! printf '%s\n' "$id" | grep -Eq '^[a-z][a-z0-9-]{4,28}[a-z0-9]$'; then
    echo "'$id' in scripts/gcp/projects.txt is not a GCP project ID (6 to 30 lowercase letters, digits and hyphens)" >&2
    return 1
  fi
  printf '%s\n' "$id"
}

deploy_account_of() {
  printf '%s@%s.iam.gserviceaccount.com\n' "$DEPLOY_ACCOUNT" "$1"
}

# Cloud Scheduler's service agent in the project with this number.
scheduler_agent_of() {
  printf 'service-%s@gcp-sa-cloudscheduler.iam.gserviceaccount.com\n' "$1"
}
