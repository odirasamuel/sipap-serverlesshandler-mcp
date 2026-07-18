#!/usr/bin/env bash
# Build Lambda layer package for sipap-common
# Usage: ./scripts/build-lambda-package.sh [python-version]

set -euo pipefail

PYTHON_VERSION="${1:-3.12}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Building sipap-common Lambda layer ==="
echo "Python version: ${PYTHON_VERSION}"
echo "Repository root: ${REPO_ROOT}"

cd "$REPO_ROOT"

# Verify requirements-lambda.txt exists
if [[ ! -f requirements-lambda.txt ]]; then
  echo "❌ requirements-lambda.txt not found"
  exit 1
fi

# Clean up old layer directory
rm -rf layer
mkdir -p layer/python

echo "Installing dependencies..."
python${PYTHON_VERSION} -m pip install --upgrade pip
pip${PYTHON_VERSION} install \
  -r requirements-lambda.txt \
  --no-cache-dir \
  --no-compile \
  --upgrade \
  --target layer/python

# Clean up unnecessary files
echo "Cleaning up unnecessary files..."
find layer -type d -name "__pycache__" -exec rm -rf {} + || true
find layer -type d -name "tests" -exec rm -rf {} + || true
find layer -type f -name "*.pyc" -delete || true

# Package layer
ZIP_NAME="sipap_common_layer_py${PYTHON_VERSION}.zip"
echo "Packaging layer: ${ZIP_NAME}"

cd layer
zip -X -r "../${ZIP_NAME}" python
cd ..

rm -rf layer

echo "✅ Layer package created: ${ZIP_NAME}"
ls -lh "${ZIP_NAME}"

echo ""
echo "To test locally:"
echo "  unzip ${ZIP_NAME} -d /tmp/layer"
echo "  python${PYTHON_VERSION} -c 'import sys; sys.path.insert(0, \"/tmp/layer/python\"); from sipap_common import get_logger; print(\"✓ Import successful\")'"
