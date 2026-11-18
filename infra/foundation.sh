#!/usr/bin/env bash
# Terraform for the long-lived layer (Route 53 zone and certificate).
#   infra/foundation.sh plan | apply | output
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
cd "$HERE/foundation"
terraform init -input=false -reconfigure -backend-config="bucket=sampcup-tfstate-${ACCOUNT}" >/dev/null
terraform "${1:-plan}" "${@:2}"
