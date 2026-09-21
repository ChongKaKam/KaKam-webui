#!/usr/bin/env bash
# Linux deployment entry point. Never source .env.kakam or print expanded config.
set -euo pipefail

die() { echo "部署中止：$*" >&2; return 1; }
compose() { docker compose --env-file .env.kakam -f compose.kakam.yaml "$@"; }

check_capacity() {
  local available_mb=$1 swap_free_mb=$2 disk_free_mb=$3
  local required_mb=$((KAKAM_BUILD_NODE_HEAP_MB + 2048))
  echo "资源检查：可用 RAM ${available_mb}MB，空闲 Swap ${swap_free_mb}MB，空闲磁盘 ${disk_free_mb}MB；Node 堆 ${KAKAM_BUILD_NODE_HEAP_MB}MB。"
  if (( available_mb + swap_free_mb < required_mb )); then
    die "RAM + 空闲 Swap 不足 ${required_mb}MB。请先扩容或配置 Swap；不会停服、自动创建 Swap 或修改系统配置。"; return 1
  fi
  if (( disk_free_mb < 10240 )); then
    die "部署目录至少需要 10GB 空闲磁盘用于镜像和备份；不会自动清理镜像或数据卷。"; return 1
  fi
}

build_images() {
  # Separate invocations: do not run concurrent frontend / Python builds.
  # memory-worker uses exactly the image built by memory-api.
  compose build open-webui || return
  compose build memory-api || return
}

smoke_images() {
  # No network, production credentials, volume mounts or database writes.
  docker run --rm --network none --entrypoint python kakam-memory:local \
    -c 'import kakam_memory.admin, kakam_memory.manager' || return
}

backup_data() {
  local backup_parent="$PWD/../kakam-deploy-backups" backup_dir container_id service
  mkdir -p "$backup_parent" || return
  backup_dir=$(mktemp -d "$backup_parent/deploy-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX") || return
  echo "保存更新前备份：$backup_dir（含密钥，请勿上传或分享）"
  cp .env.kakam "$backup_dir/env.kakam" || return
  git rev-parse HEAD > "$backup_dir/target-commit.txt" || return
  for service in open-webui memory-api memory-worker memory-db; do
    container_id=$(compose ps -q "$service") || return
    if [[ -n "$container_id" ]]; then
      docker inspect --format '{{.Image}}' "$container_id" > "$backup_dir/$service.image-id" || return
    fi
  done
  container_id=$(compose ps -q memory-db) || return
  if [[ -n "$container_id" ]]; then
    compose exec -T memory-db pg_dump -U postgres -d kakam_memory -Fc > "$backup_dir/memory.dump" || return
    test -s "$backup_dir/memory.dump" || return
  fi
  container_id=$(compose ps -q open-webui) || return
  if [[ -n "$container_id" ]]; then
    # SQLite online backup includes WAL writes; copying the live DB file does not.
    compose exec -T open-webui python -c '
import os, pathlib, shutil, sqlite3, sys, tempfile
url = os.environ.get("DATABASE_URL", "")
path = pathlib.Path("/app/backend/data/webui.db")
if url and url != "sqlite:////app/backend/data/webui.db":
    raise SystemExit("Non-default WebUI database: back it up explicitly before deploying")
if not path.is_file():
    raise SystemExit("WebUI SQLite database is missing; refusing an incomplete backup")
with tempfile.TemporaryDirectory() as tmp:
    target = pathlib.Path(tmp) / "webui.db"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    with target.open("rb") as stream:
        shutil.copyfileobj(stream, sys.stdout.buffer)
' > "$backup_dir/webui.db" || return
    test -s "$backup_dir/webui.db" || return
  fi
  echo "数据库及部署配置备份完成。上传文件仍在原数据卷中；此备份不替代定期完整备份。"
}

deploy_release() {
  echo "串行构建；构建失败时不重建正在运行的容器。"
  build_images || return
  smoke_images || return
  backup_data || return
  echo "镜像与备份就绪，更新容器并等待健康检查（最多 ${KAKAM_DEPLOY_WAIT_SECONDS} 秒）。"
  compose up -d --no-build --wait --wait-timeout "$KAKAM_DEPLOY_WAIT_SECONDS" || return
  compose ps || return
  echo "部署完成：$(git rev-parse --short HEAD)"
}

main() {
  local mode=${1:-deploy} available_mb swap_free_mb disk_free_mb
  if [[ "$mode" == --help ]]; then
    echo "用法：bash deploy.sh [--check]"
    echo "环境选项：KAKAM_BUILD_NODE_HEAP_MB=6144 KAKAM_DEPLOY_WAIT_SECONDS=300"
    echo "--check 只验证配置和资源，不构建、不备份、不重启。先 git pull --ff-only 再部署。"
    return
  fi
  [[ $# -le 1 && ( "$mode" == deploy || "$mode" == --check ) ]] || { die "未知参数；使用 --help"; return 1; }
  cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [[ "$(uname -s)" == Linux ]] || { die "请在 Linux Docker 部署服务器运行。"; return 1; }
  for command in docker git awk df flock; do
    command -v "$command" >/dev/null || { die "缺少命令 $command"; return 1; }
  done
  export KAKAM_BUILD_NODE_HEAP_MB=${KAKAM_BUILD_NODE_HEAP_MB:-6144}
  export KAKAM_DEPLOY_WAIT_SECONDS=${KAKAM_DEPLOY_WAIT_SECONDS:-300}
  [[ "$KAKAM_BUILD_NODE_HEAP_MB" =~ ^[1-9][0-9]{2,4}$ ]] || { die "Node 堆大小必须是正整数 MB"; return 1; }
  [[ "$KAKAM_DEPLOY_WAIT_SECONDS" =~ ^[1-9][0-9]{0,4}$ ]] || { die "健康检查等待时间必须是正整数秒"; return 1; }
  # Avoid Compose/Bake parallelism; do not change daemon-wide settings.
  export COMPOSE_PARALLEL_LIMIT=1 COMPOSE_BAKE=false
  test -f .env.kakam || { die "缺少 .env.kakam，请参考 deploy/memory/.env.example"; return 1; }
  git diff --quiet && git diff --cached --quiet || { die "有未提交的跟踪文件修改；请先备份并处理，不会覆盖。"; return 1; }
  compose version >/dev/null
  compose up --help | awk '/--wait-timeout/ {found=1} END {exit !found}' || { die "请升级 Docker Compose 至支持 --wait-timeout 的版本。"; return 1; }
  compose config --quiet
  available_mb=$(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo)
  swap_free_mb=$(awk '/^SwapFree:/ {print int($2/1024)}' /proc/meminfo)
  disk_free_mb=$(df -Pm . | awk 'NR==2 {print $4}')
  check_capacity "$available_mb" "$swap_free_mb" "$disk_free_mb" || return
  [[ "$mode" != --check ]] || { echo "预检查通过；未执行构建或重启。"; return; }
  umask 077
  # Lock lives in Git metadata, not the build context. Do not run two deployments.
  exec 9>"$(git rev-parse --git-path kakam-deploy.lock)"
  flock -n 9 || { die "另一个部署正在运行。"; return 1; }
  deploy_release
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  trap 'echo "部署失败（行 $LINENO）。未删除数据卷；请检查容器状态，不会自动回滚数据库。" >&2' ERR
  main "$@"
fi
