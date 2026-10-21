#!/bin/sh
# Build a service's image from a commit on main and deploy it to one environment, then read its /version back
# (command-center/environments C2, by the convention in command-center/D32).
#
# It refuses a commit that is not on origin/main. It builds services/<service>/Dockerfile (the probe's is
# scripts/gcp/probe/Dockerfile) from the commit itself, not the working tree, with the repository root as the
# context, for linux/amd64, which is what Cloud Run runs. The image is tagged with the commit. It deploys to Cloud
# Run in us-east1 as the environment's deploy identity, with the commit in COMMIT_SHA and /version open to anyone,
# and fails unless /version then answers that commit.
#
# The owner runs it: a deploy to a shared environment is gated (LOOP.md §2). See docs/runbooks/deploy.md.
# To roll back, deploy the previous commit with the same command.
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
else
  dockerfile=services/$service/Dockerfile
fi

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

sa=$(deploy_account_of "$project")
registry=$REGION-docker.pkg.dev
image=$registry/$project/$REPOSITORY/$service:$commit
echo "deploy $service to $env: commit $commit, project $project, region $REGION"

# 2. Build from the commit's own tree, with the repository root as the context.
tmp=$(mktemp -d "${TMPDIR:-/tmp}/deploy.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
git -C "$here" archive --format=tar "$commit" | tar -x -C "$tmp"
docker build --platform=linux/amd64 --file="$tmp/$dockerfile" --tag="$image" \
  --label="org.opencontainers.image.revision=$commit" "$tmp"

# 3. Push as the deploy identity. The token lasts an hour, and docker keeps it for this registry only.
token=$(gcloud auth print-access-token --impersonate-service-account="$sa")
printf '%s\n' "$token" | docker login --username=oauth2accesstoken --password-stdin "$registry"
docker push "$image"

# 4. Deploy. --update-env-vars keeps the service's other variables. A failed deploy leaves the previous revision
# serving.
gcloud run deploy "$service" --image="$image" --region="$REGION" --project="$project" \
  --update-env-vars="$COMMIT_VAR=$commit" --allow-unauthenticated \
  --impersonate-service-account="$sa" --quiet

# 5. Read /version back.
url=$(gcloud run services describe "$service" --region="$REGION" --project="$project" \
  --impersonate-service-account="$sa" --format='value(status.url)')
sh "$here/scripts/gcp/served.sh" "$url/version" "$commit" >/dev/null
echo "deployed $service to $env: $url/version answers $commit"
