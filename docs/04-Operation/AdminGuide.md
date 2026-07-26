# AI Webtoon Factory — 管理员指南

> **版本**：v1.0  
> **最后更新**：2026-06-27  
> **状态**：草案  
> **适用对象**：系统管理员、运维人员

---

## 1. 系统配置

### 1.1 环境变量配置

系统配置通过环境变量管理，关键配置项如下：

#### 通用配置

```bash
# 应用环境
APP_ENV=development                     # development / production / testing
APP_SECRET_KEY=change-me-to-random-key   # JWT 签名密钥（生产环境必须更换为强随机字符串）
APP_DEBUG=false                          # 生产环境必须设为 false
APP_LOG_LEVEL=INFO                       # DEBUG / INFO / WARNING / ERROR
```

> **安全提示**：生产环境必须更换 `APP_SECRET_KEY`，建议使用 `openssl rand -hex 32` 生成。

#### 数据库配置

```bash
# 生产环境使用 PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/webtoon_factory

# 连接池配置（生产环境推荐）
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_PRE_PING=true                    # 连接前检查可用性
```

#### Redis / Celery 配置

```bash
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Celery 并发配置
CELERY_WORKER_CONCURRENCY=4
CELERY_MAX_TASKS_PER_CHILD=1000
```

#### 存储配置

```bash
# 本地存储（开发环境）
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=./data/storage

# MinIO 对象存储（生产环境）
# STORAGE_BACKEND=minio
# MINIO_ENDPOINT=minio.example.com:9000
# MINIO_ACCESS_KEY=your-access-key
# MINIO_SECRET_KEY=your-secret-key
# MINIO_BUCKET_NAME=webtoon-images
# MINIO_USE_SSL=true
```

#### AI 模型配置

```bash
# LLM 配置（兼容 OpenAI API 格式）
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4-turbo
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# 生图模型配置（兼容 Stable Diffusion API 格式）
IMAGE_API_BASE=http://your-sd-server:7860/sdapi/v1
IMAGE_API_KEY=
IMAGE_MODEL=sd_xl_base_1.0
IMAGE_DEFAULT_WIDTH=1080
IMAGE_DEFAULT_HEIGHT=1440
IMAGE_DEFAULT_STEPS=30
IMAGE_DEFAULT_CFG_SCALE=7.5
IMAGE_MAX_CONCURRENT=2                 # 最大并发生图任务数
```

### 1.2 模型配置

#### 添加新的 LLM 模型

1. 登录系统后，进入"AI 模型中心"
2. 点击"添加模型" → 选择"LLM 模型"
3. 填写配置：
   - 模型名称（如 "DeepSeek V3"）
   - API Base URL
   - API Key
   - 模型 ID（如 "deepseek-chat"）
   - 最大 Token 数
4. 点击"测试连接"验证配置是否正确
5. 保存配置，新模型即可在系统中使用

**支持的 LLM 模型列表：**
| 模型 | API Base URL | 模型 ID |
|------|-------------|---------|
| GPT-4 Turbo | `https://api.openai.com/v1` | `gpt-4-turbo` |
| GPT-4o | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

#### 添加新的生图模型

1. 进入"AI 模型中心" → 点击"添加模型" → 选择"生图模型"
2. 填写配置：
   - 模型名称（如 "SDXL 1.0"）
   - API Base URL
   - 默认参数（宽度、高度、步数、CFG Scale）
3. 测试连接后保存

**支持的图模型：**
| 模型 | 接入方式 | 说明 |
|------|----------|------|
| Stable Diffusion WebUI | SD API | 本地部署或远程 API |
| ComfyUI | ComfyUI API | 自定义工作流 |
| Midjourney | MJ-Proxy | 通过中间代理接入 |

### 1.3 存储配置

#### 本地存储

默认开发环境使用本地文件系统存储：

```bash
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=./data/storage
```

**目录结构：**
```
data/storage/
├── novels/                    # 上传的小说文件
├── images/                    # 生成的漫画图片
│   ├── originals/             # 原图
│   ├── thumbnails/            # 缩略图（300px 宽）
│   └── previews/              # 预览图（1080px 宽）
├── exports/                   # 导出文件临时目录
└── cache/                     # 缓存（LRU 淘汰，最大 50GB）
```

#### MinIO 对象存储（生产环境推荐）

```bash
STORAGE_BACKEND=minio
MINIO_ENDPOINT=minio.example.com:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_BUCKET_NAME=webtoon-images
MINIO_USE_SSL=true
```

**MinIO 部署建议：**
- 使用 Docker Compose 部署 MinIO 实例
- 启用 HTTPS
- 配置定期生命周期策略删除过期临时文件
- 监控存储空间使用率，设置告警阈值（建议 80%）

---

## 2. 日常运维

### 2.1 备份策略

#### 数据库备份

```bash
# PostgreSQL 备份
pg_dump -U webtoon -h localhost webtoon_factory > backup_$(date +%Y%m%d).sql

# 定时备份（crontab）
0 3 * * * pg_dump -U webtoon -h localhost webtoon_factory | gzip > /backup/db/backup_$(date +\%Y\%m\%d).sql.gz

# 保留最近 30 天的备份
0 4 * * * find /backup/db -name "*.sql.gz" -mtime +30 -delete
```

**备份频率建议：**
| 数据类型 | 备份频率 | 保留时间 |
|----------|----------|----------|
| 数据库 | 每日全量备份 | 30 天 |
| 图片文件 | 实时同步至灾备 | 7 天增量，30 天全量 |
| 配置文件 | 每次变更后备份 | 永久保留 |

#### 文件系统备份

```bash
# 备份图片文件
rsync -avz --delete /data/storage/ backup-server:/backup/storage/

# 打包备份
tar -czf images_backup_$(date +%Y%m%d).tar.gz /data/storage/images/
```

### 2.2 性能监控

#### 关键指标

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| CPU 使用率 | > 80% | 后端服务 CPU 负载 |
| 内存使用率 | > 85% | 物理内存使用率 |
| 磁盘使用率 | > 80% | 图片存储磁盘 |
| 数据库连接数 | > 80% pool | PostgreSQL 连接池 |
| API 响应时间 P99 | > 5 秒 | 慢请求告警 |
| AI 任务失败率 | > 5% | 生图/分析任务失败 |
| Redis 内存使用 | > 80% | 缓存淘汰率过高 |

#### 监控命令

```bash
# 查看 Celery 任务队列状态
celery -A app.tasks.celery_app inspect active
celery -A app.tasks.celery_app inspect reserved
celery -A app.tasks.celery_app inspect stats

# 查看 Redis 内存使用
redis-cli INFO memory

# 查看 PostgreSQL 连接数
psql -U webtoon -c "SELECT count(*) FROM pg_stat_activity;"

# 查看后端日志
journalctl -u webtoon-backend -f
```

### 2.3 日志查看

日志文件位置：

```bash
# 后端日志
./data/logs/backend.log
./data/logs/backend-error.log

# Celery Worker 日志
./data/logs/celery.log

# Nginx 访问日志
/var/log/nginx/webtoon-access.log
/var/log/nginx/webtoon-error.log
```

**日志轮转配置示例（logrotate）：**

```
/data/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

---

## 3. 故障排除

### 3.1 AI 任务失败排查

**症状**：AI 任务长时间停留在"排队中"或"进行中"

**排查步骤：**

1. **检查 Redis 连接**
   ```bash
   redis-cli ping  # 应返回 PONG
   ```

2. **检查 Celery Worker 状态**
   ```bash
   celery -A app.tasks.celery_app status
   # 如果没有 Worker 在线，启动 Worker
   celery -A app.tasks.celery_app worker -l info -Q ai_generation,ai_analysis,export,default
   ```

3. **检查 LLM/生图 API 可用性**
   ```bash
   # 测试 LLM API
   curl -X POST $LLM_API_BASE/chat/completions \
     -H "Authorization: Bearer $LLM_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-4-turbo","messages":[{"role":"user","content":"test"}]}'

   # 测试生图 API
   curl $IMAGE_API_BASE/sdapi/v1/txt2img \
     -H "Content-Type: application/json" \
     -d '{"prompt":"test","width":512,"height":512}'
   ```

4. **检查日志**
   ```bash
   tail -200 ./data/logs/backend-error.log | grep -i "error|exception|fail"
   ```

**常见原因及解决方案：**
| 原因 | 解决方案 |
|------|----------|
| API Key 过期或无效 | 在模型中心更新 API Key |
| LLM API 配额用尽 | 检查 API 配额，升级套餐或更换模型 |
| 生图服务未启动 | 重启 Stable Diffusion / ComfyUI 服务 |
| Redis 连接中断 | 检查 Redis 服务状态并重启 |
| Celery Worker 崩溃 | 查看 Worker 日志，修复后重启 Worker |

### 3.2 数据库问题排查

**症状**：API 响应慢、数据库连接超时

**排查步骤：**

1. **检查数据库连接数**
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
   ```

2. **查看慢查询**
   ```sql
   SELECT query, calls, total_time, mean_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

3. **检查是否有锁等待**
   ```sql
   SELECT blocked_locks.pid AS blocked_pid,
          blocking_locks.pid AS blocking_pid
   FROM pg_locks blocked_locks
   JOIN pg_locks blocking_locks ON ...
   WHERE NOT blocked_locks.granted;
   ```

4. **检查表大小和膨胀率**
   ```sql
   SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
   FROM pg_catalog.pg_statio_user_tables
   ORDER BY pg_total_relation_size(relid) DESC;
   ```

**常见问题：**
| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| 连接池耗尽 | 检查 `DB_POOL_SIZE` 配置 | 增大连接池或优化查询 |
| 索引缺失 | 检查慢查询分析 | 添加缺失索引（参考 DBD 文档） |
| 表膨胀 | 检查表大小 | 执行 VACUUM 或 REINDEX |
| 磁盘空间不足 | `df -h` 检查磁盘 | 清理日志、扩容磁盘 |

### 3.3 存储问题排查

**症状**：图片加载失败、导出失败

**排查步骤：**

1. **检查存储服务**
   ```bash
   # 本地存储
   ls -la ./data/storage/images/

   # MinIO
   mc ls minio/webtoon-images/
   ```

2. **检查磁盘空间**
   ```bash
   df -h
   du -sh ./data/storage/
   ```

3. **检查文件权限**
   ```bash
   ls -la ./data/storage/
   # 确保运行用户有读写权限
   ```

---

## 4. 安全管理

### 4.1 API Key 管理

**存储安全：**
- API Key 在数据库中使用 AES-256-GCM 加密存储
- 加密密钥来自 `APP_SECRET_KEY` 环境变量
- 前端永不接触原始 API Key

**轮换策略：**
- 生产环境 API Key 建议每 90 天轮换一次
- 轮换步骤：
  1. 在模型中心添加使用新 Key 的新模型配置
  2. 在管线设置中切换使用新配置
  3. 确认系统运行正常后，删除旧配置

### 4.2 用户权限管理

系统当前版本使用简单的用户模型（单用户模式），后续版本将引入更完善的权限体系：

**当前权限模型：**
| 角色 | 权限 | 说明 |
|------|------|------|
| 管理员 | 全部权限 | 系统配置、用户管理 |
| 创作者 | 项目管理、管线操作 | 创建/编辑项目、运行管线 |
| 审核员 | 质量控制、导出 | 审核图片、导出成品 |

**安全建议：**
- 为所有用户设置强密码（12 位以上，含大小写字母、数字、特殊字符）
- 定期审计用户账号和权限
- 离职人员及时禁用账号

### 4.3 审计日志

系统记录所有关键操作的审计日志：

```sql
-- 审计日志表结构（示例）
CREATE TABLE system_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL,        -- create / update / delete / login / export
    entity_type VARCHAR(50) NOT NULL,   -- novel / character / panel / image
    entity_id UUID,
    detail JSONB,                       -- 变更详情（变更前后数据快照）
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**审计日志查询示例：**

```sql
-- 查看最近 100 条操作日志
SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 100;

-- 查看某个 Panel 的所有变更历史
SELECT * FROM system_logs
WHERE entity_type = 'panel' AND entity_id = 'specific-panel-uuid'
ORDER BY created_at;

-- 查看某个用户的所有操作
SELECT * FROM system_logs
WHERE user_id = 'specific-user-uuid'
ORDER BY created_at DESC;
```

**审计日志保留策略：**
- 在线保留：90 天
- 归档保留：1 年
- 定期清理：超过 1 年的日志压缩归档后删除

---

## 附录 A：Docker 运维命令

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f celery_worker

# 重启某个服务
docker-compose restart backend

# 更新服务（拉取最新镜像后）
docker-compose pull
docker-compose up -d

# 数据迁移
docker-compose exec backend alembic upgrade head

# 进入容器调试
docker-compose exec backend bash
```

---

## 附录 B：健康检查端点

系统提供以下健康检查端点，用于监控系统状态：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 基础健康检查 |
| `/health/db` | GET | 数据库连接检查 |
| `/health/redis` | GET | Redis 连接检查 |
| `/health/llm` | GET | LLM API 可用性检查 |
| `/health/image` | GET | 生图 API 可用性检查 |
| `/health/storage` | GET | 存储服务检查 |

示例响应：
```json
{
    "status": "healthy",
    "timestamp": "2026-06-27T10:00:00Z",
    "checks": {
        "database": {"status": "ok", "latency_ms": 5},
        "redis": {"status": "ok", "latency_ms": 2},
        "llm": {"status": "ok", "latency_ms": 350},
        "image_gen": {"status": "ok", "latency_ms": 120},
        "storage": {"status": "ok", "free_gb": 250}
    }
}
```

---

*本文档为系统管理员提供完整的运维指导。如有未覆盖的问题，请提交 Issue 至项目仓库。*
