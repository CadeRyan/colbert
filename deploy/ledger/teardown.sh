#!/usr/bin/env bash
# Remove the ledger deployment completely by deleting its dedicated project (Cloud Run, Firestore
# data, secrets, images). Export the data first if you want to keep it:
#   python3 -m ledger admin export --out ledger-export.jsonl
# Google keeps a deleted project recoverable for 30 days (gcloud projects undelete), then purges it.
#
#   PROJECT=colbert-ledger-1234 deploy/ledger/teardown.sh
set -euo pipefail
: "${PROJECT:?set PROJECT}"
read -r -p "Delete project $PROJECT and everything in it? Type the project id to confirm: " answer
[ "$answer" = "$PROJECT" ] || { echo "not confirmed"; exit 1; }
gcloud projects delete "$PROJECT" --quiet
echo "Deleted. Remove the budget alert too: gcloud billing budgets list --billing-account BILLING_ID"
