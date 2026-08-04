#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA="b2b84d7b372316472ffc9e7483b52757dc1b8a36104c4f8c361394b29adc42fa"
ARCHIVE="${TMPDIR:-/tmp}/kayi-source.tar.gz"

cat .bootstrap/source.part-* | base64 --decode > "$ARCHIVE"
echo "${EXPECTED_SHA}  ${ARCHIVE}" | sha256sum --check
tar -xzf "$ARCHIVE"

echo "KAYI source tree assembled and verified."
