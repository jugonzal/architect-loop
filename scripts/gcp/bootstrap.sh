#!/bin/sh
# Create or confirm one environment's GCP project (command-center/environments C1, per its D1 and D2, and
# command-center/D8, D32): the project, linked to a billing account; the APIs the services use; an Artifact
# Registry repository for their images; a deploy identity that deploy.sh acts as; and a monthly budget that emails
# the billing account's administrators at 50%, 90% and 100% of the amount named here.
#
# Every step reads first, changes only what is missing, and prints what it found or changed, so a second run
# changes nothing and says "0 changes". It never relinks billing, deletes anything or removes a grant. It ends by
# printing each service's /version URL for LOOP.md §3.
#
# The owner runs it: it spends money and grants IAM roles (LOOP.md §2). See docs/runbooks/deploy.md.
#
# Usage: sh scripts/gcp/bootstrap.sh <staging|production> --billing-account=<ID> --budget=<amount>[<currency>]
set -eu

here=$(cd "$(dirname "$0")/../.." && pwd)
. "$here/scripts/gcp/common.sh"

usage() {
  echo "usage: sh scripts/gcp/bootstrap.sh <staging|production> --billing-account=<ID> --budget=<amount>[<currency>]" >&2
  echo "       --budget is a whole amount a month in the billing account's currency, e.g. --budget=25USD" >&2
  exit 2
}

[ $# -ge 1 ] || usage
env=$1
shift
billing=
budget=
for arg in "$@"; do
  case $arg in
    --billing-account=*) billing=${arg#*=} ;;
    --budget=*) budget=${arg#*=} ;;
    *) usage ;;
  esac
done
project=$(project_of "$env")
billing=${billing#billingAccounts/}
if [ -z "$billing" ]; then
  echo "bootstrap: name the billing account with --billing-account=<ID> ('gcloud billing accounts list' shows it)" >&2
  exit 2
fi
if [ -z "$budget" ]; then
  echo "bootstrap: name the monthly budget with --budget=<amount>, e.g. --budget=25USD (environments/D2)" >&2
  exit 2
fi
printf '%s\n' "$billing" | grep -Eq '^[A-Za-z0-9-]+$' || usage
printf '%s\n' "$budget" | grep -Eq '^[0-9]+([A-Z]{3})?$' || usage
units=$(printf '%s\n' "$budget" | sed 's/[A-Z]*$//')
currency=$(printf '%s\n' "$budget" | sed 's/^[0-9]*//')

changes=0
ok() { echo "ok       $*"; }
changed() { changes=$((changes + 1)); echo "changed  $*"; }

# Google Cloud is eventually consistent: a grant on an account created seconds ago, or a call to an API enabled
# seconds ago, can fail at first. Try a few times before giving up.
retry() {
  n=1
  until "$@"; do
    [ "$n" -lt 5 ] || return 1
    echo "         retrying in 10 s ($n of 4): a change made seconds ago may not have reached it yet" >&2
    sleep 10
    n=$((n + 1))
  done
}

command -v gcloud >/dev/null 2>&1 || { echo "bootstrap: gcloud is not installed" >&2; exit 1; }
account=$(gcloud config get-value account 2>/dev/null || true)
[ -n "$account" ] || { echo "bootstrap: gcloud has no active account; run 'gcloud auth login' first" >&2; exit 1; }
echo "bootstrap $env: project $project in $REGION, as $account"

# 1. The project.
if number=$(gcloud projects describe "$project" --format='value(projectNumber)' 2>/dev/null) && [ -n "$number" ]; then
  ok "project $project (number $number)"
else
  gcloud projects create "$project" --name="architect-loop $env" --quiet
  number=$(gcloud projects describe "$project" --format='value(projectNumber)')
  changed "created project $project (number $number)"
fi

# 2. Billing. A project linked to another account is left alone: moving it is the owner's call, made by hand.
linked=$(gcloud billing projects describe "$project" --format='value(billingAccountName)')
case $linked in
  "billingAccounts/$billing") ok "billing account $billing linked" ;;
  '')
    gcloud billing projects link "$project" --billing-account="$billing" --format=none --quiet
    changed "linked billing account $billing" ;;
  *)
    echo "bootstrap: $project is linked to billing account ${linked#billingAccounts/}, not $billing; not changing it" >&2
    exit 1 ;;
esac

# 3. The APIs.
enabled=$(gcloud services list --enabled --project="$project" --format='value(config.name)')
missing=
for api in $APIS; do
  printf '%s\n' "$enabled" | grep -qx "$api" || missing="$missing $api"
done
if [ -n "$missing" ]; then
  # Word splitting is intended: one argument per API.
  # shellcheck disable=SC2086
  gcloud services enable $missing --project="$project" --quiet
  changed "enabled$missing"
else
  ok "APIs enabled: $APIS"
fi

# 4. The image repository.
if gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" --project="$project" \
    --format='value(name)' >/dev/null 2>&1; then
  ok "Artifact Registry repository $REPOSITORY in $REGION"
else
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location="$REGION" \
    --project="$project" --description="Service images, each tagged with the commit it was built from" --quiet
  changed "created Artifact Registry repository $REPOSITORY in $REGION"
fi

# 5. The deploy identity, its roles on the project, and the owner's right to act as it.
sa=$(deploy_account_of "$project")
if gcloud iam service-accounts describe "$sa" --project="$project" --format='value(email)' >/dev/null 2>&1; then
  ok "deploy identity $sa"
else
  gcloud iam service-accounts create "$DEPLOY_ACCOUNT" --project="$project" \
    --display-name="Deploys services from commits on main" --quiet
  changed "created deploy identity $sa"
fi
held=$(gcloud projects get-iam-policy "$project" --flatten='bindings[].members' \
  --filter="bindings.members:serviceAccount:$sa" --format='value(bindings.role)')
for role in $DEPLOY_ROLES; do
  if printf '%s\n' "$held" | grep -qx "$role"; then
    ok "$sa holds $role"
  else
    retry gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:$sa" --role="$role" \
      --condition=None --format=none --quiet
    changed "granted $role to $sa"
  fi
done
case $account in
  *.gserviceaccount.com) member=serviceAccount:$account ;;
  *) member=user:$account ;;
esac
creators=$(gcloud iam service-accounts get-iam-policy "$sa" --project="$project" --flatten='bindings[].members' \
  --filter='bindings.role:roles/iam.serviceAccountTokenCreator' --format='value(bindings.members)')
if printf '%s\n' "$creators" | grep -qix "$member"; then
  ok "$account may act as $sa"
else
  retry gcloud iam service-accounts add-iam-policy-binding "$sa" --project="$project" --member="$member" \
    --role=roles/iam.serviceAccountTokenCreator --condition=None --format=none --quiet
  changed "let $account act as $sa (roles/iam.serviceAccountTokenCreator)"
fi

# 6. The budget (environments/D2). It is found by its display name, which the project ID makes unique.
budget_name="$project-monthly"
budgets=$(retry gcloud billing budgets list --billing-account="$billing" --billing-project="$project" \
  --format='value(displayName,name,amount.specifiedAmount.units,amount.specifiedAmount.currencyCode)')
row=$(printf '%s\n' "$budgets" | awk -F '\t' -v name="$budget_name" '$1 == name { print; exit }')
if [ -z "$row" ]; then
  gcloud billing budgets create --billing-account="$billing" --billing-project="$project" \
    --display-name="$budget_name" --budget-amount="$budget" --calendar-period=month \
    --filter-projects="projects/$project" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 --format=none --quiet
  changed "created budget $budget_name: $budget a month, emailing the billing administrators at 50%, 90% and 100%"
else
  id=$(printf '%s\n' "$row" | cut -f 2)
  have_units=$(printf '%s\n' "$row" | cut -f 3)
  have_currency=$(printf '%s\n' "$row" | cut -f 4)
  if [ "$have_units" = "$units" ] && { [ -z "$currency" ] || [ "$have_currency" = "$currency" ]; }; then
    ok "budget $budget_name: $have_units$have_currency a month"
  else
    gcloud billing budgets update "$id" --billing-account="$billing" --billing-project="$project" \
      --budget-amount="$budget" --format=none --quiet
    changed "budget $budget_name was $have_units$have_currency a month, now $budget"
  fi
fi

if [ "$changes" = 1 ]; then noun=change; else noun=changes; fi
echo
echo "$env: $changes $noun. Project $project, number $number, region $REGION."
echo "The served-commit command of each $env row in LOOP.md §3 (a service not deployed yet answers 404 and reads as unknown):"
for service in $SERVICES; do
  echo "  $env/$service  sh scripts/gcp/served.sh https://$service-$number.$REGION.run.app/version"
done
echo "Next: sh scripts/gcp/deploy.sh probe $env <sha>, with a commit on main (docs/runbooks/deploy.md)."
