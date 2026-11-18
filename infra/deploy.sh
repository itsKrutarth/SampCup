#!/usr/bin/env bash
# Build, then run Terraform for the production stack.
#   infra/deploy.sh plan     # show what would change
#   infra/deploy.sh apply    # build and deploy
# Extra arguments go to Terraform, e.g. infra/deploy.sh apply -var enable_custom_domain=true
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ACTION="${1:-plan}"
shift || true

"$HERE/build.sh"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
cd "$HERE/terraform"
terraform init -input=false -reconfigure -backend-config="bucket=sampcup-tfstate-${ACCOUNT}" >/dev/null
terraform "$ACTION" "$@"
