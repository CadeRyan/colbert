#!/usr/bin/env bash
# Measure colbert on one real GPU in Google Cloud, then delete the VM.
#
# NOT YET RUN. Written without access to a GCP project; read it before using it.
# It costs money: one spot g2-standard-4 (1x NVIDIA L4) for well under an hour.
# Cost guards: spot pricing, --max-run-duration 90m with termination action DELETE,
# and the startup script powers the VM off when it finishes.
#
#   PROJECT=my-project ZONE=us-central1-a REPO_TARBALL=gs://my-bucket/colbert.tar.gz deploy/gcp-benchmark.sh
#
# The VM reads the source from REPO_TARBALL (so the repository can stay private) and writes
# its log to the serial console:  gcloud compute instances get-serial-port-output colbert-bench
set -euo pipefail
: "${PROJECT:?set PROJECT}"; : "${ZONE:=us-central1-a}"; : "${REPO_TARBALL:?set REPO_TARBALL (gs://...)}"
NAME=${NAME:-colbert-bench}
MACHINE=${MACHINE:-g2-standard-4}
ACCEL=${ACCEL:-type=nvidia-l4,count=1}

cat > /tmp/colbert-startup.sh <<'EOS'
#!/bin/bash
exec > >(tee /dev/ttyS0) 2>&1
set -x
TARBALL=$(curl -s -H Metadata-Flavor:Google http://metadata/computeMetadata/v1/instance/attributes/repo-tarball)
apt-get update && apt-get install -y build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers clinfo
mkdir -p /opt/colbert && cd /opt/colbert
gsutil cp "$TARBALL" src.tar.gz && tar xzf src.tar.gz --strip-components=1
make colbert
nvidia-smi
./colbert devices
echo "=== SELFTEST ===";  ./colbert selftest --backend ocl | tail -3
echo "=== BENCH 46M ==="; ./colbert bench 21181 46000028 2000 --backend ocl
echo "=== VERIFY ===";    ./colbert bench 67607 46000000 20 --backend ocl --verify
echo "=== DONE ==="
poweroff
EOS

gcloud compute instances create "$NAME" --project "$PROJECT" --zone "$ZONE" \
  --machine-type "$MACHINE" --accelerator "$ACCEL" \
  --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 90m \
  --maintenance-policy TERMINATE \
  --image-family common-cu123-ubuntu-2204 --image-project deeplearning-platform-release \
  --metadata "install-nvidia-driver=True,repo-tarball=$REPO_TARBALL" \
  --metadata-from-file startup-script=/tmp/colbert-startup.sh \
  --scopes storage-ro --boot-disk-size 60GB
echo "started $NAME; follow with: gcloud compute instances get-serial-port-output $NAME --project $PROJECT --zone $ZONE"
