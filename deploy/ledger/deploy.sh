#!/usr/bin/env bash
# Deploy the Colbert ledger to Google Cloud: Cloud Run (the HTTP service) + Firestore (the data).
#
#   PROJECT=colbert-ledger-1234 BILLING=XXXXXX-XXXXXX-XXXXXX deploy/ledger/deploy.sh
#
# Optional: REGION (default us-central1), SERVICE (colbert-ledger), BUDGET (15, in the billing
# account's own currency; 0 = no budget alert), MAX_INSTANCES (2). Safe to re-run: every step checks before it creates, and a
# re-run just deploys the current code.
#
# COST. Linking billing is required even for the free tier. At the load of a volunteer project
# (tens to a few hundred computers) this stays within, or a few dollars above, the always-free
# quotas of Cloud Run and Firestore. See "What it costs" in docs/LEDGER.md. MAX_INSTANCES caps
# compute, and a budget alert emails the billing account's admins at 50%, 90% and 100% of
# BUDGET per month. A budget alerts; it does not stop spending.
#
# Everything lives in one dedicated project, so `deploy/ledger/teardown.sh` removes all of it.
set -euo pipefail
: "${PROJECT:?set PROJECT (a new project id, e.g. colbert-ledger-1234)}"
: "${BILLING:?set BILLING (from: gcloud billing accounts list)}"
REGION=${REGION:-us-central1}
SERVICE=${SERVICE:-colbert-ledger}
BUDGET=${BUDGET:-15}
MAX_INSTANCES=${MAX_INSTANCES:-2}
SA="$SERVICE@$PROJECT.iam.gserviceaccount.com"
BUILD_SA="$SERVICE-build@$PROJECT.iam.gserviceaccount.com"
SECRET="$SERVICE-admin-token"
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
export CLOUDSDK_CORE_PROJECT="$PROJECT"              # every gcloud call, including quota/billing
g() { gcloud --project "$PROJECT" --quiet "$@"; }     # never fall back to the default project

say() { printf '\n== %s\n' "$*"; }

say "project $PROJECT"
if ! gcloud projects describe "$PROJECT" >/dev/null 2>&1; then
  gcloud projects create "$PROJECT" --name "Colbert ledger"
fi

say "billing account $BILLING"
current=$(gcloud billing projects describe "$PROJECT" --format='value(billingAccountName)' 2>/dev/null || true)
if [ "$current" != "billingAccounts/$BILLING" ]; then
  gcloud billing projects link "$PROJECT" --billing-account "$BILLING"
fi

say "APIs"
g services enable run.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com billingbudgets.googleapis.com

say "Firestore database (native mode, $REGION)"
if ! g firestore databases describe --database='(default)' >/dev/null 2>&1; then
  g firestore databases create --database='(default)' --location="$REGION" --type=firestore-native
fi

say "service account $SA (Firestore read/write only)"
if ! g iam service-accounts describe "$SA" >/dev/null 2>&1; then
  g iam service-accounts create "$SERVICE" --display-name "Colbert ledger"
fi
g projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role roles/datastore.user --condition=None >/dev/null

say "build service account $BUILD_SA"
# New projects' default build account lacks the permissions Cloud Build needs; use a
# dedicated one with exactly the role for building Cloud Run sources.
if ! g iam service-accounts describe "$BUILD_SA" >/dev/null 2>&1; then
  g iam service-accounts create "$SERVICE-build" --display-name "Colbert ledger build"
  sleep 10                                              # let the new account propagate
fi
g projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$BUILD_SA" --role roles/run.builder --condition=None >/dev/null

say "admin token (Secret Manager: $SECRET)"
if ! g secrets describe "$SECRET" >/dev/null 2>&1; then
  openssl rand -hex 32 | tr -d '\n' | g secrets create "$SECRET" --replication-policy automatic --data-file=-
fi
g secrets add-iam-policy-binding "$SECRET" --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor >/dev/null

say "build context (the ledger package only)"
CTX=$(mktemp -d)
trap 'rm -rf "$CTX"' EXIT
mkdir -p "$CTX/ledger"
cp "$REPO/ledger/Dockerfile" "$REPO/ledger/requirements.txt" "$CTX/"
cp "$REPO"/ledger/*.py "$CTX/ledger/"            # the package is flat; tests stay behind

say "Cloud Run service $SERVICE ($REGION, at most $MAX_INSTANCES instances)"
g run deploy "$SERVICE" --source "$CTX" --region "$REGION" --service-account "$SA" \
  --build-service-account "projects/$PROJECT/serviceAccounts/$BUILD_SA" \
  --allow-unauthenticated --set-env-vars LEDGER_STORE=firestore --set-secrets "LEDGER_ADMIN_TOKEN=$SECRET:latest" \
  --min-instances 0 --max-instances "$MAX_INSTANCES" --concurrency 40 --cpu 1 --memory 512Mi --timeout 300
URL=$(g run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')

if [ "$BUDGET" != "0" ] && ! gcloud billing budgets list --billing-project "$PROJECT" --billing-account "$BILLING" --format='value(displayName)' 2>/dev/null | grep -qx "$SERVICE"; then
  CURRENCY=$(gcloud billing accounts describe "$BILLING" --format='value(currencyCode)')   # budgets must use it
  say "budget alert: $BUDGET $CURRENCY/month"
  gcloud billing budgets create --billing-project "$PROJECT" --billing-account "$BILLING" --display-name "$SERVICE" \
    --budget-amount "${BUDGET}${CURRENCY}" --filter-projects "projects/$PROJECT" \
    --threshold-rule percent=0.5 --threshold-rule percent=0.9 --threshold-rule percent=1.0
fi

say "done"
cat <<EOF
Ledger:  $URL   (status page at /, JSON at /v1/status)

Admin commands need the token:
  export LEDGER_URL=$URL
  export LEDGER_ADMIN_TOKEN=\$(gcloud --project $PROJECT secrets versions access latest --secret $SECRET)
  python3 -m ledger admin status
  python3 -m ledger admin seed data/candidates_47.9M-57.5M_p4.3e9.txt.gz
  python3 -m ledger admin config registration='"invite"' invite_code='"choose-one"'

The app joins with this address on its Work tab, or: python3 app/run.py --headless --ledger $URL --owner NAME
EOF
