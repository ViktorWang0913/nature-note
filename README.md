# 自然记 Nature Note

自然观察记录与笔记创作网页应用，支持照片管理、物种识别、GPS 观察记录和图文笔记编辑。

## 功能

- 照片上传、物种确认、素材生成与个人图鉴。
- GPS 轨迹、观察点与照片关联，支持本地缓存和同步。
- 自然笔记背景生成、图片手动编辑、裁剪、绘图、图层排版与图片导出。
- 作品分享、社区浏览和自然知识问答。
- 管理后台提供账号、内容审核、服务配置及额度与计费管理。

## 技术栈

前端使用 Vue 3、TypeScript 和 Vite；后端使用 FastAPI、SQLAlchemy 和 Alembic。本地运行使用 SQLite，生产部署使用 PostgreSQL、Redis、Celery 和 Caddy。

## 文件结构

```text
frontend/
  src/pages/       页面
  src/components/  共享组件
  src/services/    接口与业务状态
  src/engine/      画布、图片编辑与轨迹处理
  src/web/         浏览器适配、账户与本地存储
  public/          静态资源
  scripts/         构建工具
backend/
  app/             接口、业务服务与管理后台
  alembic/         数据库迁移
  tests/           后端测试
  seed-assets/     公共素材与模板
infra/             容器与反向代理配置
contracts/         接口定义
scripts/           本地运行与维护工具
docs/              部署说明
```

## 本地运行

需要 Python 3.12、Node.js 20.19+ 或 22.12+、PowerShell 7.3+。以下命令适用于 Windows，在仓库根目录执行：

```powershell
pwsh -File scripts/start-local.ps1 setup
Copy-Item backend/.env.example backend/.env
```

将 `backend/.env` 中的 `SECRET_KEY` 替换为随机密钥，再分别启动后端和前端：

```powershell
pwsh -File scripts/start-local.ps1 api
pwsh -File scripts/start-local.ps1 web
```

网页：`http://127.0.0.1:5173/`；管理后台：`http://127.0.0.1:5173/admin`；接口文档：`http://127.0.0.1:8010/docs`。

执行 `pwsh -File scripts/start-local.ps1 admin` 创建管理员，再通过后台创建用户账号。模型接口、密钥、价格及地图 Key 可在后台配置。图片生成、识别与知识问答需要外部服务；网页轨迹记录需要定位权限并保持页面在前台。

## 检查与部署

`pwsh -File scripts/start-local.ps1 check` 执行前端类型检查、测试、构建及后端隔离测试。前端构建同时生成管理后台使用的预览脚本。

接口变更后，在 `backend/` 目录执行 `../.venv/Scripts/python.exe ../scripts/export-openapi.py` 更新接口定义。

生产部署见 [部署说明](docs/deployment.md)。许可见 [LICENSE](LICENSE)。
