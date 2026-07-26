# AI Webtoon Factory — 部署指南（Deployment Guide）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案  
> 适用范围：开发环境、生产环境（Docker / Linux）

---

## 1. 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端（浏览器）                           │
└──────────────────┬────────────────────────┬──────────────────────┘
                   │                        │
                   ▼                        ▼
            ┌──────────────┐       ┌──────────────────┐
            │  Nginx        │       │  WebSocket        │
            │  (反向代理)    │◄──────│  (wss://)         │
            │  :80 / :443   │       └──────────────────┘
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │  FastAPI      │
            │  (Uvicorn)    │
            │  :8000        │
            └──┬────┬───────┘
               │    │
        ┌──────┘    └──────┐
        ▼                   ▼
┌──────────────┐   ┌──────────────┐
│ PostgreSQL   │   │  Redis       │
│  :5432       │   │  :6379       │
│  (主库)       │   │  (缓存/队列)  │
└──────────────┘   └──────────────┘
                        │
                        ▼
                ┌──────────────┐
                │  Celery       │
                │  (Worker)     │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  MinIO        │
                │  (对象存储)    │
                │  :9000        │
                └──────────────┘
```

### 1.1 组件说明

| 组件 | 角色 | 端口 | 扩展方式 |
|------|------|------|----------|
| Nginx | 反向代理、SSL 终结、静态文件服务 | 80/443 | — |
| FastAPI (Uvicorn) | REST API + WebSocket 服务 | 8000 | 多 Worker 进程 |
| Celery Worker | 异步 AI 任务处理 | — | 水平扩展 Worker 数量 |
| Celery Beat | 定时任务调度（可选） | — | — |
| PostgreSQL | 关系数据库 | 5432 | 读写分离（V2+） |
| Redis | 缓存、Celery Broker/Backend | 6379 | Redis Cluster（V2+） |
| MinIO | 对象存储（图片文件） | 9000/9001 | 分布式部署（V2+） |

---

## 2. 开发环境部署

### 2.1 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| npm | 9 | 10 |
| SQLite | 3.x | 3.x |
| Redis | 7.0 | 7.2 |
| PostgreSQL | 15 | 16（可选，开发默认用 SQLite） |
| Docker | 24.0 | 25.0（可选） |

### 2.2 后端启动

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/ai-webtoon-factory.git
cd AI-Webtoon-Factory

# 2. 创建虚拟环境
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 3. 安装依赖
pip install -r requirements/dev.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，至少配置以下项：
#   DATABASE_URL=sqlite+aiosqlite:///./dev.db
#   LLM_API_KEY=your-api-key
#   LLM_BASE_URL=https://api.openai.com/v1

# 5. 执行数据库迁移
alembic upgrade head

# 6. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.3 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env.local
# 编辑 .env.local:
#   VITE_API_BASE=http://localhost:8000/api/v1

# 启动开发服务器
npm run dev
# 默认在 http://localhost:5173 启动
```

### 2.4 Redis 启动（可选，任务队列用）

```bash
# 使用 Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 2.5 数据库迁移

```bash
# 执行未应用的迁移
alembic upgrade head

# 自动生成新的迁移脚本
alembic revision --autogenerate -m "add_scene_table"

# 查看迁移历史
alembic history

# 回滚一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision_id>
```

### 2.6 开发环境验证

```bash
# 1. 验证后端健康检查
curl http://localhost:8000/api/v1/health
# 预期响应：{"status":"healthy","version":"0.1.0","timestamp":"..."}

# 2. 验证 API 文档
# http://localhost:8000/docs

# 3. 验证前端
# http://localhost:5173
```

---

## 3. 生产环境部署（Docker）

### 3.1 Docker Compose 配置

```yaml
# docker-compose.yml（开发/测试用）
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: webtoon_factory
      POSTGRES_USER: webtoon
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U webtoon"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-admin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-admin123}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"   # API
      - "9001:9001"   # Console
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://webtoon:${DB_PASSWORD}@postgres:5432/webtoon_factory
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      STORAGE_BACKEND: s3
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: ${MINIO_ROOT_USER:-admin}
      S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-admin123}
      S3_BUCKET: webtoon-images
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      minio:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://webtoon:${DB_PASSWORD}@postgres:5432/webtoon_factory
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      STORAGE_BACKEND: s3
      S3_ENDPOINT: http://minio:9000
      S3_ACCESS_KEY: ${MINIO_ROOT_USER:-admin}
      S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-admin123}
      S3_BUCKET: webtoon-images
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.openai.com/v1}
      LLM_MODEL: ${LLM_MODEL:-gpt-4o}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./backend:/app
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      VITE_API_BASE: /api/v1
    ports:
      - "3000:80"
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 3.2 环境变量清单

```bash
# ============ 应用配置 ============
APP_NAME=AI Webtoon Factory
DEBUG=false
API_PREFIX=/api/v1
SECRET_KEY=<生成随机 32 位密钥>
ALLOWED_HOSTS=*

# ============ 数据库 ============
DATABASE_URL=postgresql+asyncpg://webtoon:password@postgres:5432/webtoon_factory
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_ECHO=false

# ============ Redis ============
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50

# ============ Celery ============
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_TASK_MAX_RETRIES=3
CELERY_TASK_DEFAULT_RATE_LIMIT=10/m

# ============ AI 服务 ============
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3

# 生图 API
IMAGE_GEN_API_KEY=
IMAGE_GEN_BASE_URL=http://sd-api:7860
IMAGE_GEN_MODEL=sdxl-turbo

# ============ 存储 ============
STORAGE_BACKEND=s3                # local | s3
STORAGE_PATH=./uploads            # 仅 local 模式生效
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=admin
S3_SECRET_KEY=admin123
S3_BUCKET=webtoon-images
S3_REGION=us-east-1
S3_SECURE=false

# ============ 日志 ============
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/app/app.log
LOG_MAX_BYTES=104857600           # 100MB
LOG_BACKUP_COUNT=10

# ============ 监控 ============
SENTRY_DSN=                       # Sentry DSN（可选）
METRICS_ENABLED=true
```

### 3.3 构建与启动

```bash
# 1. 准备环境
cp .env.example .env
# 编辑 .env，填入生产环境配置

# 2. 构建镜像
docker-compose build

# 3. 初始化 MinIO 存储桶（首次部署）
docker-compose run --rm backend python -c "
from app.adapters.storage_adapter import init_bucket
import asyncio
asyncio.run(init_bucket())
"

# 4. 启动所有服务
docker-compose up -d

# 5. 查看启动日志
docker-compose logs -f

# 6. 验证服务状态
curl http://localhost:8000/api/v1/health
```

### 3.4 缩略图服务（Nginx 配置）

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # 日志格式
    log_format json_log escape=json
        '{"time": "$time_iso8601", '
        '"remote_addr": "$remote_addr", '
        '"method": "$request_method", '
        '"path": "$uri", '
        '"status": $status, '
        '"request_time": $request_time, '
        '"body_bytes_sent": $body_bytes_sent, '
        '"user_agent": "$http_user_agent"}';

    access_log /var/log/nginx/access.log json_log;
    error_log /var/log/nginx/error.log warn;

    # SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript image/svg+xml;
    gzip_min_length 1000;
    gzip_vary on;

    # 上传大小限制
    client_max_body_size 50M;

    server {
        listen 80;
        server_name webtoon-factory.example.com;

        # HTTP 自动跳转 HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name webtoon-factory.example.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # 静态资源缓存
        location /assets/ {
            root /usr/share/nginx/html;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # 前端 SPA
        location / {
            root /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ /index.html;

            # HTML 不缓存
            location = /index.html {
                add_header Cache-Control "no-cache, must-revalidate";
            }
        }

        # API 反向代理
        location /api/ {
            proxy_pass http://backend:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 超时配置
            proxy_connect_timeout 60s;
            proxy_read_timeout 120s;
            proxy_send_timeout 60s;

            # 限制 API 速率
            limit_req zone=api burst=20 nodelay;
            limit_req_status 429;
        }

        # WebSocket 反向代理
        location /ws/ {
            proxy_pass http://backend:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;

            # WebSocket 超时
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }

        # 健康检查
        location /health {
            proxy_pass http://backend:8000/api/v1/health;
            access_log off;
        }
    }

    # API 速率限制
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
}
```

### 3.5 SSL 证书（Let's Encrypt）

```bash
# 使用 certbot 获取证书
docker run -it --rm \
  -v /docker/nginx/ssl:/etc/letsencrypt \
  certbot/certbot \
  certonly --webroot \
  --webroot-path=/docker/nginx/html \
  -d webtoon-factory.example.com

# 自动续期（crontab）
# 0 0 * * * docker run --rm -v /docker/nginx/ssl:/etc/letsencrypt certbot/certbot renew && docker exec nginx nginx -s reload
```

---

## 4. 数据库相关

### 4.1 PostgreSQL 生产配置

```ini
# postgresql.conf 关键配置
listen_addresses = '*'
port = 5432

# 连接池
max_connections = 200
superuser_reserved_connections = 10

# 内存
shared_buffers = 1GB            # 物理内存的 25%
effective_cache_size = 3GB      # 物理内存的 75%
work_mem = 32MB                 # 每个排序操作的内存
maintenance_work_mem = 256MB    # 维护操作（VACUUM、CREATE INDEX）

# 写入
wal_buffers = 16MB
wal_level = replica
synchronous_commit = on

# 查询
random_page_cost = 1.1          # SSD 配置
effective_io_concurrency = 200  # SSD 配置
default_statistics_target = 500

# 日志
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000  # 记录超过 1 秒的查询
```

### 4.2 备份策略

```bash
#!/bin/bash
# scripts/backup_db.sh
# 每日数据库备份脚本

BACKUP_DIR="/backups/postgres"
DB_NAME="webtoon_factory"
DB_USER="webtoon"
RETENTION_DAYS=30

mkdir -p "${BACKUP_DIR}/daily"
mkdir -p "${BACKUP_DIR}/weekly"

DATE=$(date +%Y%m%d)
WEEKDAY=$(date +%u)

# 每日备份
pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
  --format=custom \
  --compress=9 \
  --file="${BACKUP_DIR}/daily/${DB_NAME}_${DATE}.dump"

# 每周日执行全量备份
if [ "${WEEKDAY}" = "7" ]; then
  cp "${BACKUP_DIR}/daily/${DB_NAME}_${DATE}.dump" \
     "${BACKUP_DIR}/weekly/${DB_NAME}_week_$(date +%Y%V).dump"
fi

# 删除过期备份
find "${BACKUP_DIR}/daily" -name "*.dump" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}/weekly" -name "*.dump" -mtime +90 -delete

# 备份到远程存储（可选）
# aws s3 sync "${BACKUP_DIR}" s3://webtoon-backups/postgres/
```

### 4.3 恢复流程

```bash
# 恢复数据库
pg_restore -U webtoon -d webtoon_factory \
  --clean \
  --if-exists \
  --jobs=4 \
  /backups/postgres/daily/webtoon_factory_20260101.dump

# 如果只需要恢复特定表
pg_restore -U webtoon -d webtoon_factory \
  --table=scenes \
  --table=panels \
  /backups/postgres/daily/webtoon_factory_20260101.dump
```

### 4.4 Redis 配置

```conf
# redis.conf 关键配置

# 持久化（AOF + RDB 混合模式）
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

save 900 1
save 300 10
save 60 10000

# 内存限制
maxmemory 1gb
maxmemory-policy allkeys-lru

# 连接
maxclients 10000
timeout 300

# 慢查询日志
slowlog-log-slower-than 10000
slowlog-max-len 128
```

---

## 5. 监控与运维

### 5.1 日志

#### 5.1.1 日志级别配置

```python
# 生产环境日志配置
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(module)s %(funcName)s %(lineno)d",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if os.getenv("LOG_FORMAT") == "json" else "standard",
            "level": os.getenv("LOG_LEVEL", "INFO"),
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.getenv("LOG_FILE", "/var/log/app/app.log"),
            "maxBytes": int(os.getenv("LOG_MAX_BYTES", 104857600)),
            "backupCount": int(os.getenv("LOG_BACKUP_COUNT", 10)),
            "formatter": "json",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "sqlalchemy.engine": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "httpx": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}
```

#### 5.1.2 日志轮转

```bash
# logrotate 配置
# /etc/logrotate.d/webtoon-factory

/var/log/app/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    dateext
    dateformat -%Y%m%d
    create 0644 app app
}
```

### 5.2 健康检查端点

```python
# app/routers/v1/health.py
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """健康检查端点"""
    # 检查数据库连接
    db_healthy = await check_database()
    # 检查 Redis 连接
    redis_healthy = await check_redis()
    # 检查 MinIO 连接
    storage_healthy = await check_storage()

    overall_healthy = all([db_healthy, redis_healthy, storage_healthy])

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "up" if db_healthy else "down",
            "redis": "up" if redis_healthy else "down",
            "storage": "up" if storage_healthy else "down",
        },
    }
```

### 5.3 监控指标

| 指标 | 来源 | 报警阈值 | 说明 |
|------|------|----------|------|
| API 响应时间 P95 | Uvicorn metrics | > 500ms | HTTP 请求处理时间 |
| API 错误率 | Prometheus | > 1%（5m） | 5xx 响应比例 |
| 任务队列深度 | Celery Flower | > 100 | 等待处理的任务数 |
| 任务失败率 | Celery Flower | > 5% | 失败/总任务数 |
| CPU 使用率 | Docker/Prometheus | > 80% | 容器 CPU 使用率 |
| 内存使用率 | Docker/Prometheus | > 85% | 容器内存使用率 |
| 磁盘使用率 | Node Exporter | > 80% | 数据盘使用率 |
| 图片生成时间 | 应用指标 | > 120s | 单张图片生成耗时 |
| LLM 调用延迟 | 应用指标 | > 30s | LLM 响应时间 |
| 数据库连接数 | PostgreSQL Exporter | > 150 | 活跃连接数 |

### 5.4 报警规则示例

```yaml
# prometheus/rules.yml
groups:
  - name: webtoon-factory
    rules:
      - alert: HighAPIErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API error rate > 1% ({{ $value | humanizePercentage }})"

      - alert: TaskQueueBacklog
        expr: celery_queue_depth{queue="default"} > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Task queue depth > 100 ({{ $value }})"

      - alert: HighDatabaseConnections
        expr: pg_stat_activity_count > 150
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connections > 150 ({{ $value }})"
```

---

## 6. CI/CD 配置

### 6.1 GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
    tags: ["v*"]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: backend/requirements/dev.txt

      - name: Install Python dependencies
        run: pip install -r backend/requirements/dev.txt

      - name: Run Python tests
        run: |
          cd backend
          pytest tests/unit -v --cov=app --cov-report=xml
          pytest tests/integration -v

      - name: Set up Node.js 18
        uses: actions/setup-node@v4
        with:
          node-version: "18"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install Node.js dependencies
        run: cd frontend && npm ci

      - name: Run Frontend tests
        run: cd frontend && npm test -- --run

      - name: Lint
        run: |
          cd backend && ruff check .
          cd ../frontend && npm run lint

  build:
    name: Build Docker Images
    needs: test
    if: github.event_name == 'push' && (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v'))
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix=,suffix=,format=short

      - name: Build and push Backend
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ${{ steps.meta.outputs.tags }}-backend
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push Frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ${{ steps.meta.outputs.tags }}-frontend
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Production
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            cd /opt/webtoon-factory
            docker-compose pull
            docker-compose up -d --remove-orphans
            docker system prune -f
```

### 6.2 Docker 镜像构建文件

#### 6.2.1 后端 Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements/prod.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 6.2.2 前端 Dockerfile

```dockerfile
# frontend/Dockerfile
# ---- 构建阶段 ----
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/nginx.conf

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

EXPOSE 80
```

---

## 7. 安全性指南

### 7.1 生产环境安全基线

| 项目 | 要求 |
|------|------|
| HTTPS | 强制，HSTS 启用 |
| API 认证 | JWT Token（access + refresh） |
| 密码加密 | bcrypt（work_factor=12） |
| CORS | 限定具体域名 |
| 请求限流 | 30 r/s（API）、5 r/s（登录） |
| 容器安全 | 非 root 用户运行 |
| Secret 管理 | 环境变量 / Vault |
| 文件上传 | 限制类型和大小 |

### 7.2 Docker 安全实践

```dockerfile
# ✅ 正确：非 root 用户运行
USER appuser

# ✅ 正确：最小化基础镜像
FROM python:3.11-slim  # 使用 slim 而非 full

# ❌ 错误：使用 root 运行
USER root

# ❌ 错误：使用大型基础镜像
FROM python:3.11
```

---

## 附录：部署检查清单

### 首次部署检查项

- [ ] 所有环境变量已配置
- [ ] 数据库密码已修改为强密码
- [ ] JWT Secret Key 已生成
- [ ] SSL 证书已配置
- [ ] CORS 域名已限制
- [ ] 防火墙端口已开放（80/443）
- [ ] Docker 非 root 用户运行
- [ ] 日志轮转已配置
- [ ] 自动备份已配置
- [ ] 健康检查端点可访问
- [ ] 监控告警已配置
- [ ] `.gitignore` 排除了 `.env` 文件

### 日常运维检查项

- [ ] 数据库备份状态
- [ ] 磁盘使用率
- [ ] 任务队列深度
- [ ] 错误日志检查
- [ ] SSL 证书到期检查
- [ ] 依赖安全更新
