#!/usr/bin/env bash
# Test suite for wizard template.sh write_env hardening
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_SH="${1:-/opt/hermes-agent/.agents/skills/wizard/template.sh}"

echo "=== Testing template: $TEMPLATE_SH ==="

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Extract library portion (everything above STAGES marker)
LIB_CODE=$(sed '/^# STAGES:/q' "$TEMPLATE_SH")

source_lib() {
  local env_file="$1"
  cat <<EOF
ENV_FILE="$env_file"
WRITTEN_ENV=()
RED="" GREEN="" RESET=""
$LIB_CODE
EOF
}

# Test 1: Normal secret write creates 0600 file
echo -n "Test 1: Normal secret write creates 0600 file... "
ENV_1="$TEST_DIR/test1.env"
bash -c "$(source_lib "$ENV_1")
write_env 'TEST_KEY' 'test_secret_123'
" >/dev/null

if [[ ! -f "$ENV_1" ]]; then
  echo "FAILED: File not created"
  exit 1
fi

PERMS=$(stat -c "%a" "$ENV_1" 2>/dev/null || stat -f "%OLp" "$ENV_1")
if [[ "$PERMS" != "600" ]]; then
  echo "FAILED: Permissions are $PERMS, expected 600"
  exit 1
fi

if ! grep -q "TEST_KEY='test_secret_123'" "$ENV_1"; then
  echo "FAILED: Key/value not found in file"
  exit 1
fi
echo "PASSED"

# Test 2: Symlink rejection
echo -n "Test 2: Rejects symlink target... "
REAL_FILE="$TEST_DIR/real_target.txt"
echo "DO_NOT_OVERWRITE" > "$REAL_FILE"
SYMLINK_FILE="$TEST_DIR/symlink.env"
ln -s "$REAL_FILE" "$SYMLINK_FILE"

if bash -c "$(source_lib "$SYMLINK_FILE")
write_env 'TEST_KEY' 'malicious_overwrite'
" 2>/dev/null; then
  echo "FAILED: write_env should have failed on symlink"
  exit 1
fi

if ! grep -q "DO_NOT_OVERWRITE" "$REAL_FILE"; then
  echo "FAILED: Target file was clobbered via symlink"
  exit 1
fi
echo "PASSED"

# Test 3: Key identifier format validation
echo -n "Test 3: Validates POSIX key identifiers... "
ENV_3="$TEST_DIR/test3.env"
for bad_key in "BAD-KEY" "BAD KEY" "BAD=KEY" "123BAD" "BAD/KEY"; do
  if bash -c "$(source_lib "$ENV_3")
write_env '$bad_key' 'value'
" 2>/dev/null; then
    echo "FAILED: write_env should have rejected invalid key '$bad_key'"
    exit 1
  fi
done
echo "PASSED"

# Test 4: Single quote escaping
echo -n "Test 4: Handles values with single quotes... "
ENV_4="$TEST_DIR/test4.env"
bash -c "$(source_lib "$ENV_4")
write_env 'QUOTED_VAL' \"test'quote'val\"
" >/dev/null

VAL_READ=$(bash -c "source '$ENV_4' && echo \"\$QUOTED_VAL\"")
if [[ "$VAL_READ" != "test'quote'val" ]]; then
  echo "FAILED: Expected \"test'quote'val\", got \"$VAL_READ\""
  exit 1
fi
echo "PASSED"

# Test 5: Rejects directory target
echo -n "Test 5: Rejects existing directory as ENV_FILE... "
DIR_TARGET="$TEST_DIR/existing_dir"
mkdir -p "$DIR_TARGET"
ORIG_DIR_PERMS=$(stat -c "%a" "$DIR_TARGET" 2>/dev/null || stat -f "%OLp" "$DIR_TARGET")

if bash -c "$(source_lib "$DIR_TARGET")
write_env 'TEST_KEY' 'dir_overwrite'
" 2>/dev/null; then
  echo "FAILED: write_env should have failed when ENV_FILE is a directory"
  exit 1
fi

NEW_DIR_PERMS=$(stat -c "%a" "$DIR_TARGET" 2>/dev/null || stat -f "%OLp" "$DIR_TARGET")
if [[ "$NEW_DIR_PERMS" != "$ORIG_DIR_PERMS" ]]; then
  echo "FAILED: Directory permissions altered from $ORIG_DIR_PERMS to $NEW_DIR_PERMS"
  exit 1
fi

CHILD_COUNT=$(find "$DIR_TARGET" -type f | wc -l)
if [[ "$CHILD_COUNT" -ne 0 ]]; then
  echo "FAILED: Temporary file dumped inside directory ($CHILD_COUNT files found)"
  exit 1
fi
echo "PASSED"

echo "=== All write_env hardening tests passed! ==="
