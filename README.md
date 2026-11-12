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

需要 Python 3.12+、Node.js 20.19+ 或 22.12+。以下命令在仓库根目录执行，按操作系统选择脚本。

### Windows

需要 PowerShell 7.3+，初始化依赖并复制本地配置：

```powershell
pwsh -File scripts/start-local.ps1 setup
Copy-Item backend/.env.example backend/.env
```

将 `backend/.env` 中的 `SECRET_KEY` 替换为至少 32 字符的随机密钥，再在两个终端分别启动后端和前端：

```powershell
pwsh -File scripts/start-local.ps1 api
pwsh -File scripts/start-local.ps1 web
```

### Linux / WSL

使用 Bash，并确保 `python3` 和 `npm` 来自 Linux 环境。Python 需要支持 `venv`；Ubuntu / Debian 如缺少该模块，可安装对应版本的 `python3-venv` 软件包。

```bash
bash scripts/start-local.sh setup
cp backend/.env.example backend/.env
```

将 `backend/.env` 中的 `SECRET_KEY` 替换为至少 32 字符的随机密钥，再在两个 Linux / WSL 终端分别启动后端和前端：

```bash
bash scripts/start-local.sh api
bash scripts/start-local.sh web
```

### 访问与账号

网页：`http://127.0.0.1:5173/`；管理后台：`http://127.0.0.1:5173/admin`；接口文档：`http://127.0.0.1:8010/docs`。

WSL 下可从 Windows 浏览器打开上述地址。

首次启动后创建管理员，再通过后台创建用户账号：Windows 执行 `pwsh -File scripts/start-local.ps1 admin`，Linux / WSL 执行 `bash scripts/start-local.sh admin`。模型接口、密钥、价格及地图 Key 可在后台配置。图片生成、识别与知识问答需要外部服务；网页轨迹记录需要定位权限并保持页面在前台。

## 检查与部署

两个启动脚本均支持 `check`，执行前端类型检查、测试、构建及后端隔离测试；不传操作时默认执行 `check`。前端构建同时生成管理后台使用的预览脚本。

| 操作 | Windows | Linux / WSL |
|---|---|---|
| 检查与构建（仓库根目录） | `pwsh -File scripts/start-local.ps1 check` | `bash scripts/start-local.sh check` |
| 更新接口定义（`backend/` 目录） | `../.venv/Scripts/python.exe ../scripts/export-openapi.py` | `../.venv/bin/python ../scripts/export-openapi.py` |

生产部署见 [部署说明](docs/deployment.md)。许可见 [LICENSE](LICENSE)。
