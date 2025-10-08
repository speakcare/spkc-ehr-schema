#!/usr/bin/env bash
set -euo pipefail

# Build vendored dependencies for Lambda functions.
# - user_handler: pure-Python deps; install locally into vendor/
# - shift_handler: includes compiled deps (pydantic-core); build in Lambda base image (Linux)
#
# Usage (from repo root or deploy/):
#   ./deploy/build_lambda_functions.sh              # defaults to x86_64
#   ARCH=arm64 ./deploy/build_lambda_functions.sh   # build shift_handler vendor for ARM64
#
# Requirements:
# - Docker running (for shift_handler)
# - Lambda runtime version: Python 3.12

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCH="${ARCH:-x86_64}"   # x86_64 | arm64

# Map arch to docker image/platform
if [[ "$ARCH" == "x86_64" ]]; then
  PLATFORM="linux/amd64"
  IMAGE="public.ecr.aws/lambda/python:3.12"
elif [[ "$ARCH" == "arm64" ]]; then
  PLATFORM="linux/arm64"
  IMAGE="public.ecr.aws/lambda/python:3.12-arm64"
else
  echo "Invalid ARCH: $ARCH (expected x86_64 or arm64)" >&2
  exit 1
fi

echo "=== Building user_handler vendor (local pip) ==="
UH_DIR="$SCRIPT_DIR/lambda/user_handler"
rm -rf "$UH_DIR/vendor"
python3 -m pip install --no-cache-dir -r "$UH_DIR/requirements.txt" -t "$UH_DIR/vendor"
echo "User handler vendor built at: $UH_DIR/vendor"

echo "=== Building shift_handler vendor in Docker ($ARCH) ==="
SH_DIR="$SCRIPT_DIR/lambda/shift_handler"
rm -rf "$SH_DIR/vendor"
docker run --rm --platform "$PLATFORM" \
  -v "$SCRIPT_DIR":/var/task -w /var/task \
  --entrypoint /bin/bash "$IMAGE" \
  -lc "python3 -m pip install --no-cache-dir -r lambda/shift_handler/requirements.txt -t lambda/shift_handler/vendor"
echo "Shift handler vendor built at: $SH_DIR/vendor"

echo "✅ Done."
