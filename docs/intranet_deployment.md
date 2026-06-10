# 内网部署说明

本文档用于将文档审查与生成平台部署到公司内网环境。

## 1. 基本要求

- Python 版本：以项目 `.python-version` 为准。
- 依赖管理：使用 `uv`。
- 服务地址：固定 `http://127.0.0.1:5000/`。
- 数据库：默认 SQLite，路径 `web/database.db`。
- 上传与生成文件：默认保存在 `uploads/` 目录。

## 2. 配置文件

复制 `.env.example` 为 `.env`，按内网环境修改：

```env
ENVIRONMENT=dev
LLM_API_KEY=内网模型服务APIKey
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-ai/DeepSeek-V3.2
LLM_PROVIDER=siliconflow
MAX_TOKENS=4096
TEMPERATURE=0.1
LLM_TIMEOUT=120
LLM_CONNECT_TIMEOUT=30
LLM_TRUST_ENV=true
WEB_HOST=127.0.0.1
WEB_PORT=5000
UV_CACHE_DIR=D:\code\new-wdsc\.uv-cache
```

后续替换模型时，优先修改 `.env` 中的 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`，不要改业务代码。运行时以 `.env` 实际生效值为准。

## 3. 启动与停止

启动或重启 Web 服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restart_web.ps1
```

检查服务状态：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_web.ps1
```

访问地址：

```text
http://127.0.0.1:5000/
```

## 4. 目录说明

- `uploads/templates/`：上传的 DOCX 模板源文件。
- `uploads/generated/`：生成后的 DOCX 文件。
- `uploads/generation_references/`：文档生成前上传的补充材料 Word 文件。
- `config/generation_templates.json`：生成模板库元数据。
- `web/database.db`：审查记录、生成记录等运行数据。
- `web_server.log`：本地 Web 服务日志。
- `.uv-cache/`：uv 缓存目录，建议固定在项目目录。

## 5. 生成模块使用流程

1. 在“生成模板库”上传 DOCX 模板。
2. 系统自动解析章节、说明、示例、表格和占位符。
3. 按章节设置生成策略：
   - 固定保留
   - 占位替换
   - 智能生成
   - 表格填充
4. 在“文档生成”页面选择模板，填写生成素材。
5. 选择生成模式：
   - 智能生成：逐章节调用大模型。
   - 模板填充：不调用大模型，仅删除说明并替换占位符。
6. 下载生成 DOCX。
7. 在生成记录详情中查看输入素材、基础检查、章节提示词和模型返回内容。

## 6. 数据备份建议

内网测试前后建议备份：

- `config/generation_templates.json`
- `web/database.db`
- `uploads/templates/`
- `uploads/generated/`
- `uploads/generation_references/`
- `.env`

可按日期压缩备份整个项目目录，或只备份上述运行数据。

## 7. 常见问题

### 页面打不开

先检查服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_web.ps1
```

如果端口被占用，先查看 5000 端口进程，再重启服务。

### 大模型调用失败

检查 `.env`：

- `LLM_API_KEY` 是否正确。
- `LLM_BASE_URL` 是否为内网可访问地址。
- `LLM_MODEL` 是否为模型服务支持的名称。
- 代理环境不稳定时可设置 `LLM_TRUST_ENV=false`。

### 生成文档格式不符合预期

优先检查：

- 模板是否为正确 DOCX 源文件。
- 是否替换过源文件并重新解析。
- 章节生成策略是否正确。
- 生成记录详情中的章节提示词和模型返回内容是否符合预期。

### 模板解析不准确

处理方式：

- 在模板库中人工修正章节结构和章节生成说明。
- 调整章节生成策略。
- 对格式变化较大的模板，使用“替换源文件”重新解析。
