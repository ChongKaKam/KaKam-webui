#!/usr/bin/env bash
# No Docker/SSH/system changes. Exercise the actual deployment orchestration.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../deploy.sh"
export KAKAM_BUILD_NODE_HEAP_MB=6144 KAKAM_DEPLOY_WAIT_SECONDS=300
passed=0
assert_contains() { [[ "$1" == *"$2"* ]] || { echo "Missing: $2" >&2; exit 1; }; }
assert_absent() { [[ "$1" != *"$2"* ]] || { echo "Unexpected: $2" >&2; exit 1; }; }

# Matches the original host: ~6GB available RAM and zero swap must fail safely.
if check_capacity 6000 0 50000 >/dev/null 2>&1; then exit 1; fi
passed=$((passed + 1))
check_capacity 6000 8000 50000 >/dev/null
passed=$((passed + 1))
if check_capacity 6000 8000 1000 >/dev/null 2>&1; then exit 1; fi
passed=$((passed + 1))

compose() {
  echo "COMPOSE $*"
  if [[ "$*" == "${fail_at:-}" ]]; then return 7; fi
}
backup_data() { echo BACKUP; return "${backup_status:-0}"; }
git() { echo test-commit; }
output=$(deploy_release)
assert_contains "$output" $'COMPOSE build open-webui\nCOMPOSE build memory-api\nBACKUP'
assert_contains "$output" 'COMPOSE up -d --no-build --wait --wait-timeout 300'
assert_contains "$output" 'COMPOSE ps'
assert_absent "$output" '--build'
passed=$((passed + 1))

for fail_at in 'build open-webui' 'build memory-api'; do
  if output=$(deploy_release); then exit 1; fi
  assert_absent "$output" 'BACKUP'
  assert_absent "$output" 'COMPOSE up'
  passed=$((passed + 1))
done
fail_at=''
backup_status=8
if output=$(deploy_release); then exit 1; fi
assert_absent "$output" 'COMPOSE up'
passed=$((passed + 1))
backup_status=0
fail_at='up -d --no-build --wait --wait-timeout 300'
if output=$(deploy_release); then exit 1; fi
assert_absent "$output" '部署完成'
assert_absent "$output" 'COMPOSE ps'
passed=$((passed + 1))
echo "$passed deployment regression checks passed"
