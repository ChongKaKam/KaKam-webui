# KaKam Linux 部署

在服务器仓库根目录运行（密钥沿用现有 `.env.kakam`，不要重新生成）：

```sh
git pull --ff-only
bash deploy.sh --check
bash deploy.sh
```

脚本只负责部署当前检出的版本，不隐式拉取代码。需要 Bash、Git、Docker Compose
（支持 `up --wait --wait-timeout`）和 `flock`；不需要 sudo。
未提交的跟踪文件修改会阻止部署，必须先备份和处理，不能用强制 reset 丢弃。

## 针对构建 OOM 的处理

旧部署中 Node 被 Linux 全局 OOM killer 杀死；Svelte warning 不是原因。
8GB RAM 的服务器现已配置 8GB Swap。新流程：

1. 校验 Compose 配置但不打印展开后的密钥；检查可用 RAM + 空闲 Swap 和磁盘。
2. Node 堆默认 6144MB，另预留 2048MB；磁盘至少空闲 10GB。
3. 禁用 Compose/Bake 并行，先构建 WebUI，再构建一次 Memory 共用镜像。
4. 先以镜像默认的非 root 用户、禁用网络运行 Memory 导入冒烟检查；构建、检查和备份都成功后才 `up --no-build --wait`，不重复构建，不先 `down`。
5. 健康检查失败会返回非零状态，不会谎报成功或自动回滚数据库。

`--check` 不构建、不备份、不重启。资源预检查是保守估算，不保证峰值内存；其他服务
负载、Docker/cgroup 限额和磁盘耗尽仍可能导致失败。脚本不会自动创建 Swap、改 fstab、
停止其他业务、清理镜像或删除数据卷。Swap 应由管理员配置并持久化。

需要调整时显式传入（MB / 秒）：

```sh
KAKAM_BUILD_NODE_HEAP_MB=6144 KAKAM_DEPLOY_WAIT_SECONDS=600 bash deploy.sh
```

该堆参数由脚本导出并传给 Docker build，**仅影响构建阶段**；不更改运行时模型配置。
单独执行 Compose build 时也可通过同名环境变量或 `.env.kakam` 覆盖。

KaKam 生产镜像默认不生成前端 sourcemap，减少 Rollup 在生成最终资源时的内存占用；
页面功能不受影响，浏览器调试时无法映射到原始 TypeScript / Svelte 源码。
需要映射文件时设置 `KAKAM_BUILD_SOURCEMAP=true`，并为构建预留更多内存。
普通 Dockerfile 构建保持原来的 sourcemap 默认值 `true`。

在没有可用 Swap、但可用 RAM 至少为 6144MB 的服务器上，可使用：

```sh
KAKAM_BUILD_NODE_HEAP_MB=4096 bash deploy.sh --check
KAKAM_BUILD_NODE_HEAP_MB=4096 bash deploy.sh
```

这仍会执行同样的内存余量检查，不跳过预检或修改服务器 Swap。

## 更新前备份与失败恢复

构建后、重建容器前，会在仓库同级 `kakam-deploy-backups/deploy-时间-随机串/` 中保存：

- `.env.kakam` 的副本（包含密钥，目录权限 700、文件 600）。
- 当前容器镜像 ID、待部署的 Git 提交 ID。
- 正在运行的 Memory PostgreSQL 的 `pg_dump -Fc` 备份。
- 正在运行的 WebUI 默认 SQLite 的在线一致性备份（包含 WAL 数据）。

两份数据库是分别一致的快照，不是跨服务原子快照。首次部署没有运行中容器则跳过其备份；
非默认 WebUI 数据库拒绝自动升级，应先扩展对应的备份适配。上传文件仍在原数据卷，
这不是全量灾备；仍需定期备份整个数据卷，并把加密主密钥单独保存到密码管理器。
不自动清理备份；注意磁盘和访问权限，不要提交 Git 或发送给他人。

构建/备份失败不会进入容器更新；但低资源构建本身仍可能影响宿主机其他进程。
健康检查失败后先运行以下命令查看状态；日志可能含私人内容，分享前请脱敏：

```sh
docker compose --env-file .env.kakam -f compose.kakam.yaml ps
docker compose --env-file .env.kakam -f compose.kakam.yaml logs --tail=80 open-webui memory-api memory-worker
```

不要执行 `down -v`。如需回滚，先确认数据库迁移兼容性，必要时用上述备份恢复；
不能仅回滚镜像后直接让旧版本写入新数据库。

脚本回归检查：`bash deploy/test-deploy.sh`（模拟命令，不连接 Docker 或 SSH）。

Memory Dockerfile 会显式规范代码/迁移文件的读取权限，并在构建时以运行用户检查导入。
这避免服务器 Git checkout 使用 `umask 077` 时，把 root 拥有的 `600` 文件原样复制
进镜像导致非 root 服务启动失败。备份仍使用 `077`，不放宽任何密钥或数据库的权限。
