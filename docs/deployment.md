# 部署

需要 Docker Compose、Node.js 20.19+ 或 22.12+，以及已解析到服务器的域名。以下命令在仓库根目录执行。

## 配置与构建

复制 `infra/production.env.example` 为 `infra/production.env`，填写：

| 配置 | 用途 |
|---|---|
| `APP_DOMAIN` | 网页域名，不含协议和路径 |
| `PUBLIC_BASE_URL` | 与域名一致的 HTTPS 地址 |
| `POSTGRES_PASSWORD` | 随机数据库密码，建议使用十六进制字符 |
| `SECRET_KEY` | 至少 32 字符的随机服务密钥 |
| `RELEASE_TAG` | 本次后端镜像版本 |

模型服务与地图配置可通过管理后台设置。计费价格应按实际服务合同填写。

```sh
cd frontend
npm ci
npm run build
cd ..
docker compose --env-file infra/production.env -f infra/compose.yaml up --build -d
```

前端构建生成 `frontend/dist/` 和 `backend/app/static/admin-preview.js`，因此必须在后端镜像构建之前完成。Caddy 提供前端页面并代理后端接口。数据库、媒体及证书使用 Docker 命名卷保存。

## 初始化

API 启动时自动执行数据库迁移并导入公共素材与模板。创建管理员：

```sh
docker compose --env-file infra/production.env -f infra/compose.yaml exec api python -m app.admin_setup
```

访问 `https://你的域名/admin`，首次登录后修改密码，在后台创建用户账号并配置服务。普通用户不开放自行注册。

## 运行检查

```sh
docker compose --env-file infra/production.env -f infra/compose.yaml ps
docker compose --env-file infra/production.env -f infra/compose.yaml logs --tail=100 api
```

`/health` 提供进程状态，`/ready` 检查数据库连接。部署后还需实际验证登录、图片上传、笔记保存与导出，以及已配置的外部服务。

## 更新与数据

更新前备份数据库、媒体和运行配置，并暂停新请求。在重启前确认没有正在执行的任务：

```sh
docker compose --env-file infra/production.env -f infra/compose.yaml exec -T api python < scripts/check-tasks.py
```

检查通过后重新构建前端和镜像，再更新容器。不要删除数据库或媒体卷。`SECRET_KEY` 用于会话与配置加密，应安全保存，不能随意更换。

管理员登录锁定可通过 `scripts/admin-access.py` 检查；加 `--unlock` 只解除锁定，不修改密码：

```sh
docker compose --env-file infra/production.env -f infra/compose.yaml exec -T api python - --unlock < scripts/admin-access.py
```

真实配置、数据库、用户媒体和备份不纳入版本控制。
