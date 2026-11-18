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
# Serve sampcup.com as soon as the certificate (infra/foundation) is issued.
if [ -z "${TF_VAR_enable_custom_domain:-}" ]; then
  if aws acm list-certificates --certificate-statuses ISSUED \
      --query "CertificateSummaryList[?DomainName=='sampcup.com'].CertificateArn" --output text | grep -q arn; then
    export TF_VAR_enable_custom_domain=true
  else
    echo "Certificate not issued yet: deploying on the CloudFront address only."
    export TF_VAR_enable_custom_domain=false
  fi
fi
terraform "$ACTION" "$@"
