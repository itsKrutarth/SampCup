#!/usr/bin/env bash
# Take the whole production stack down (the Terraform state bucket stays, so
# infra/deploy.sh apply brings everything back). All tournament data is deleted.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
cd "$HERE/terraform"
terraform init -input=false -reconfigure -backend-config="bucket=sampcup-tfstate-${ACCOUNT}" >/dev/null
# Terraform needs the build files to evaluate the config; build them if missing.
[ -f "$HERE/build/api.zip" ] && [ -d "$HERE/../frontend/dist" ] || "$HERE/build.sh"
# Lift the database's delete protection, then remove everything.
terraform apply -input=false -auto-approve -var protect_data=false -target=aws_dynamodb_table.main
terraform destroy -input=false "$@"
