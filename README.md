# Smart Wardrobe Recommender

一个前后端分离的智能衣橱与穿搭推荐系统。用户可以管理个人衣物、查看衣橱统计、保存穿搭方案，并结合图像识别与视觉大模型生成个性化穿搭建议。

## 主要功能

- 用户注册与登录
- 衣物图片上传、去背景和类别识别
- 衣物信息的新增、编辑、删除与分类管理
- 衣橱数量、分类和颜色分布统计
- 基于场合、季节和个人衣橱的 AI 穿搭推荐
- 穿搭方案的收藏、编辑和管理

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、ECharts、Axios
- 后端：Flask、PyMySQL、OpenCV、Pillow、rembg
- 模型：PyTorch、ResNet-50、火山方舟视觉模型
- 数据库：MySQL

## 目录结构

```text
.
├── backend/
│   ├── app.py                  # Flask API、图像处理与模型推理
│   ├── requirements.txt        # Python 依赖
│   └── static/                 # 运行时生成，不提交
├── database/
│   └── schema.sql              # MySQL 表结构
├── frontend/
│   ├── public/
│   ├── src/                    # Vue 页面、路由和组件
│   ├── package.json
│   └── vite.config.ts
├── models/
│   └── final_model_*.pth       # 衣物分类模型权重
├── .env.example                # 配置模板
└── README.md
```

## 环境要求

- Node.js 20+
- Python 3.10
- MySQL 8.0
- 推荐使用 Conda 管理 Python 环境

## 本地运行

### 1. 安装后端依赖

```bash
conda create -n smart-wardrobe python=3.10 -y
conda activate smart-wardrobe
pip install -r backend/requirements.txt
```

macOS Apple Silicon 如果安装 PyTorch 时出现兼容问题，请按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 选择当前平台命令。

### 2. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 3. 初始化数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS fashion_system CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
mysql -u root -p fashion_system < database/schema.sql
```

表结构导入后，可以在登录页注册新账号。

### 4. 配置环境变量

```bash
cp .env.example .env
```

在项目根目录的 `.env` 中填写本地数据库凭据和所需 API Token。前后端共用这一个配置文件。

| 变量 | 用途 |
| --- | --- |
| `VITE_API_BASE_URL` | 前端访问的 Flask API 地址 |
| `DB_HOST` / `DB_PORT` | MySQL 地址与端口 |
| `DB_USER` / `DB_PASSWORD` | MySQL 用户名与密码 |
| `DB_NAME` | 数据库名称 |
| `ARK_API_TOKEN` | 火山方舟 API Token |
| `SUPERBED_TOKEN` | Superbed 图床 Token |
| `CLOTHES_MODEL_PATH` | PyTorch 模型权重路径 |

`.env` 已被 Git 忽略。`.env.example` 只包含配置项与占位符，可以安全公开。

### 5. 启动后端

在项目根目录运行：

```bash
python backend/app.py
```

默认 API 地址为 `http://127.0.0.1:8088`。第一次启动时，`rembg` 可能会下载去背景模型。

### 6. 启动前端

新建终端并运行：

```bash
cd frontend
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。

## 常用命令

```bash
cd frontend && npm run dev          # 启动前端开发服务器
cd frontend && npm run build        # 构建前端产物
cd frontend && npm run type-check   # TypeScript 类型检查
python backend/app.py               # 启动 Flask 后端
```

## 模型文件

仓库包含约 90 MB 的 PyTorch 权重，因此首次克隆会比纯代码项目更慢。如果后续频繁迭代模型，建议改用 Git LFS 或 GitHub Releases 管理权重。

## 安全说明

- 不要提交 `.env`、真实 API Token 或数据库密码。
- 当前登录逻辑面向本地演示。生产环境应使用强哈希存储用户密码，并补充完整的会话鉴权。
- 图片上传会访问第三方图床和视觉模型 API，请留意服务配额与图片隐私。

## License

本项目目前未声明开源许可证。未经作者允许，不得将代码用于商业目的。
