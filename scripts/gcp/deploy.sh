#!/bin/sh
# Build a service's image from a commit on main and deploy it to one environment with exactly the config its
# manifest declares at that commit, then read its /version back (command-center/environments C2, by the convention
# in command-center/D32; command-center/service-manifests C1, per command-center/D46).
#
# It refuses a commit that is not on origin/main. It reads services/<service>/service.json (the probe's is
# scripts/gcp/probe/service.json) as it is in that commit, and refuses a commit without one, a manifest that does
# not fit the format, or one that leaves a value TODO(owner) for the environment, all before it builds anything or
# calls gcloud. It builds services/<service>/Dockerfile (the probe's is scripts/gcp/probe/Dockerfile) from the
# commit itself, not the working tree, with the repository root as the context, for linux/amd64, which is what
# Cloud Run runs. The image is tagged with the commit. It deploys the manifest's jobs, then the service, to Cloud
# Run in us-east1 as the environment's deploy identity: each runs as the manifest's runtime identity, with its
# settings, secrets and Cloud SQL instance and no others, plus the commit in COMMIT_SHA (command-center/D47).
# /version is open to anyone, and the deploy fails unless /version then answers that commit.
#
# Only once /version answers the commit does it apply the manifest's schedules (command-center/service-schedules C2,
# per command-center/D67): it creates or updates the Cloud Scheduler job <service>-<name> for each one, calling the
# service's URL with an OIDC token for the service's own identity and that URL as the audience, and deletes the
# service's jobs the manifest no longer declares. A deploy that fails earlier leaves the old schedules calling the
# old revision. A manifest with schedules, in a project whose bootstrap has not enabled Cloud Scheduler, is refused
# before anything is built.
#
# The owner runs it: a deploy to a shared environment is gated (LOOP.md §2). See docs/runbooks/deploy.md.
# To roll back, deploy the previous commit with the same command: that restores its image, its config and its
# schedules.
#
# Usage: sh scripts/gcp/deploy.sh <service> <staging|production> <sha>
set -eu

here=$(cd "$(dirname "$0")/../.." && pwd)
. "$here/scripts/gcp/common.sh"

usage() {
  echo "usage: sh scripts/gcp/deploy.sh <service> <staging|production> <sha>" >&2
  echo "       <service> is a folder in services/, or probe" >&2
  exit 2
}

[ $# -eq 3 ] || usage
service=$1
env=$2
sha=$3
case $service in
  ''|-*|*[!a-z0-9-]*) usage ;;
esac
project=$(project_of "$env")
if [ "$service" = probe ]; then
  dockerfile=scripts/gcp/probe/Dockerfile
  manifest=scripts/gcp/probe/service.json
else
  dockerfile=services/$service/Dockerfile
  manifest=services/$service/service.json
fi
command -v python3 >/dev/null 2>&1 || { echo "deploy: python3 is not installed; it reads $manifest" >&2; exit 1; }

# 1. Only a commit on main.
git -C "$here" fetch --quiet origin main
if ! commit=$(git -C "$here" rev-parse --verify --quiet "$sha^{commit}"); then
  echo "deploy: $sha is not a commit in this repository; fetch it, or check the SHA" >&2
  exit 1
fi
if ! git -C "$here" merge-base --is-ancestor "$commit" origin/main; then
  echo "deploy: refusing $commit: it is not on origin/main. Only a commit on main is deployed (command-center/D32)." >&2
  exit 1
fi
if ! git -C "$here" cat-file -e "$commit:$dockerfile" 2>/dev/null; then
  echo "deploy: commit $commit has no $dockerfile" >&2
  exit 1
fi

tmp=$(mktemp -d "${TMPDIR:-/tmp}/deploy.XXXXXX")
trap 'rm -rf "$tmp"' EXIT

# 2. The manifest of that commit, checked before anything is built or deployed (command-center/D46).
if ! git -C "$here" show "$commit:$manifest" >"$tmp/service.json" 2>/dev/null; then
  echo "deploy: commit $commit has no $manifest, so it does not say how $service is configured (command-center/D46)" >&2
  exit 1
fi
python3 "$here/scripts/gcp/manifest.py" check "$tmp/service.json" --name="$manifest" --env="$env" || exit 1

sa=$(deploy_account_of "$project")
registry=$REGION-docker.pkg.dev
image=$registry/$project/$REPOSITORY/$service:$commit
echo "deploy $service to $env: commit $commit, project $project, region $REGION"

# 3. The Cloud Scheduler jobs in the region, so that the schedules a manifest no longer declares can be deleted
# (service-schedules C1). Where Cloud Scheduler is not enabled no job can call the service, so there is none to
# read; a manifest that declares schedules there is refused, since its bootstrap has not run.
: >"$tmp/scheduled"
scheduler=
enabled=$(gcloud services list --enabled --project="$project" --format='value(config.name)')
if printf '%s\n' "$enabled" | grep -qx "$SCHEDULER_API"; then
  scheduler=yes
elif python3 "$here/scripts/gcp/manifest.py" fields "$tmp/service.json" --name="$manifest" >"$tmp/fields" &&
    grep -qx schedules "$tmp/fields"; then
  echo "deploy: $manifest declares schedules, but Cloud Scheduler is not enabled in $project;" \
    "run sh scripts/gcp/bootstrap.sh $env first (docs/runbooks/deploy.md)" >&2
  exit 1
fi

# 4. What the manifest means in this environment: the flags for each job and for the service, and what to do to each
# schedule. {number} is the project's number, read only when the manifest uses it or Cloud Scheduler may hold jobs
# that call the service's URL.
number=
if [ -n "$scheduler" ] || grep -q '{number}' "$tmp/service.json"; then
  number=$(gcloud projects describe "$project" --format='value(projectNumber)')
fi
if [ -n "$scheduler" ]; then
  gcloud scheduler jobs list --location="$REGION" --project="$project" --impersonate-service-account="$sa" \
    --format='value(name,httpTarget.uri)' >"$tmp/scheduled"
fi
python3 "$here/scripts/gcp/manifest.py" render "$tmp/service.json" --name="$manifest" --env="$env" \
  --project="$project" --region="$REGION" --number="$number" --commit="$commit" --out="$tmp/config" \
  --service="$service" --scheduled="$tmp/scheduled"

# 5. Build from the commit's own tree, with the repository root as the context.
mkdir "$tmp/tree"
git -C "$here" archive --format=tar "$commit" | tar -x -C "$tmp/tree"
docker build --platform=linux/amd64 --file="$tmp/tree/$dockerfile" --tag="$image" \
  --label="org.opencontainers.image.revision=$commit" "$tmp/tree"

# 6. Push as the deploy identity. The token lasts an hour, and docker keeps it for this registry only.
token=$(gcloud auth print-access-token --impersonate-service-account="$sa")
printf '%s\n' "$token" | docker login --username=oauth2accesstoken --password-stdin "$registry"
docker push "$image"

# 7. Deploy the jobs, then the service, so the service never starts a job left at an earlier commit. Their variables
# and secrets replace whatever they had, so each ends with exactly what the manifest says. A failed deploy leaves
# the previous revision serving. Job names are checked to be words, so the loop splits them safely.
for job in $(cat "$tmp/config/jobs"); do
  set --
  while IFS= read -r flag; do set -- "$@" "$flag"; done <"$tmp/config/job-$job.flags"
  gcloud run jobs deploy "$job" --image="$image" --region="$REGION" --project="$project" "$@" \
    --impersonate-service-account="$sa" --quiet
done
set --
while IFS= read -r flag; do set -- "$@" "$flag"; done <"$tmp/config/service.flags"
gcloud run deploy "$service" --image="$image" --region="$REGION" --project="$project" "$@" \
  --allow-unauthenticated --impersonate-service-account="$sa" --quiet

# 8. Read /version back.
url=$(gcloud run services describe "$service" --region="$REGION" --project="$project" \
  --impersonate-service-account="$sa" --format='value(status.url)')
sh "$here/scripts/gcp/served.sh" "$url/version" "$commit" >/dev/null

# 9. Only now, with the new revision answering, the schedules: each declared one created or updated to call it, and
# each of the service's that the manifest no longer declares deleted (service-schedules C2). The steps are read on
# descriptor 3, so that no gcloud call can read them from its standard input.
while read -r action job <&3; do
  if [ "$action" = delete ]; then
    gcloud scheduler jobs delete "$job" --location="$REGION" --project="$project" \
      --impersonate-service-account="$sa" --quiet
    continue
  fi
  set --
  while IFS= read -r flag; do set -- "$@" "$flag"; done <"$tmp/config/schedule-$job.flags"
  gcloud scheduler jobs "$action" http "$job" --location="$REGION" --project="$project" "$@" \
    --impersonate-service-account="$sa" --quiet
done 3<"$tmp/config/schedules"
echo "deployed $service to $env: $url/version answers $commit"
