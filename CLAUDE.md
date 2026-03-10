# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

HAA-Social-Autopilot 是一个 Twitter/X 社交媒体自动化推广工具，支持内容管理、排期发布和LLM智能内容生成。

## 常用命令

### 后端开发 (Python/FastAPI)
```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器 (端口8000)
uvicorn app.main:app --reload

# 运行测试
pytest
pytest -v tests/test_xxx.py  # 单个测试文件
pytest -v tests/test_xxx.py::test_function_name  # 单个测试函数
```

### 前端开发 (React/Vite)
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 运行开发服务器 (端口3000)
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

### Docker部署
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 重建并启动
docker-compose up -d --build
```

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│  前端 (React + Vite + TailwindCSS + shadcn/ui)      │
│  frontend/src/pages/ - 5个主要页面                   │
│  状态管理: Zustand | HTTP: axios                    │
└────────────────────────┬────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────┐
│  后端 (FastAPI + SQLite + APScheduler)              │
│  backend/app/                                       │
│  ├── routers/    API路由 (tweets, media, settings)  │
│  ├── services/   业务逻辑 (发布引擎, LLM, 调度器)     │
│  ├── models/     SQLAlchemy数据模型                  │
│  └── schemas/    Pydantic请求/响应模型               │
└─────────────────────────────────────────────────────┘
```

## 核心模块

### Twitter发布引擎
- **twikit** (`services/twitter_twikit.py`) - 唯一发布引擎，免费无限制
- `services/twitter_api.py` 为统一入口，内部调用 twikit

### 定时任务调度
`services/scheduler.py` 使用 APScheduler 管理排期发布任务，在应用启动时自动初始化。

### LLM内容生成
`services/llm_service.py` 支持 OpenAI 兼容接口（GPT、Claude、Deepseek等）。

## 环境配置

复制 `.env.example` 为 `.env` 并配置：
- Twitter 账号凭据（用户名、邮箱、密码，用于 twikit 登录）
- LLM API配置（API地址、密钥、模型名）
- 服务端口和数据库路径

## 数据存储

- **数据库**: `backend/data/haa.db` (SQLite)
- **上传文件**: `backend/uploads/`
