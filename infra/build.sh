#!/usr/bin/env bash
# Build what Terraform uploads: the API package (infra/build/api.zip, for Lambda on arm64)
# and the website (frontend/dist).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/infra/build"
PKG="$OUT/lambda"

rm -rf "${PKG:?}" "$OUT/api.zip"
mkdir -p "$PKG"

# Lambda already provides boto3; leaving it out keeps the package small and starts faster.
grep -v '^boto3' "$ROOT/backend/requirements.txt" > "$OUT/requirements-lambda.txt"
python3 -m pip install --quiet --disable-pip-version-check \
  --target "$PKG" \
  --platform manylinux2014_aarch64 --implementation cp --python-version 3.12 \
  --only-binary=:all: \
  -r "$OUT/requirements-lambda.txt"
cp -R "$ROOT/backend/app" "$PKG/"
find "$PKG" -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd "$PKG" && zip -qr9 "$OUT/api.zip" .)
echo "API package: $(du -h "$OUT/api.zip" | cut -f1)"

(cd "$ROOT/frontend" && npm ci --silent && npm run --silent build)
echo "Website: $(find "$ROOT/frontend/dist" -type f | wc -l | tr -d ' ') files"
