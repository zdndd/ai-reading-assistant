# AI 读书助手

一个前后端分离的 monorepo。后端基于 `rag_mark` 中实践的 RAG 链路：

1. 文档编码识别与标准化
2. 按语义边界切块并保留重叠
3. 中文 SentenceTransformer 向量化
4. Chroma 持久化向量检索
5. CrossEncoder 二次重排
6. 带证据编号的 Gemini 生成，未配置 API Key 时降级为检索摘录

后端使用 FastAPI，前端使用 Angular 20 standalone、Signals 和 HttpClient。

运行环境固定为 Python 3.11，以兼容 macOS Intel 上可用的 Chroma/ONNX 版本。

## 目录

```text
ai_reading_assistant/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI 路由与依赖
│   │   ├── core/            # 配置、异常
│   │   ├── domain/          # 领域数据结构
│   │   ├── infrastructure/  # Chroma 持久化
│   │   ├── schemas/         # API 请求/响应模型
│   │   ├── services/        # 文档、向量、重排、生成
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/                # Angular 20 前端
│   ├── src/app/             # Angular 页面、组件、API 服务
│   ├── angular.json
│   └── package.json
├── .env.example
└── Makefile
```

## 启动

先启动后端：

```bash
cd ai_reading_assistant
cp .env.example .env
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

打开 `http://127.0.0.1:8000/docs` 查看并调试接口。

再启动前端：

```bash
cd ai_reading_assistant/frontend
npm install
npm start
```

访问 `http://127.0.0.1:4200`。开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

默认复用同仓库 `rag_mark/models` 下的本地模型。首次上传书籍或首次提问时会加载模型，可能需要几十秒。

部署或迁移时，可以下载模型到本项目 `models/`，再把 `.env` 中的路径改为：

```dotenv
EMBEDDING_MODEL=models/text2vec-base-chinese
RERANKER_MODEL=models/mmarco-mMiniLMv2-L12-H384-v1
```

如果直接填写 Hugging Face 模型名，需要把 `MODEL_LOCAL_FILES_ONLY` 设为 `false`，允许运行时下载模型。

不配置 `GEMINI_API_KEY` 也能完成上传、检索和问答，此时回答模式为 `extractive`，直接返回最相关的原文证据。

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/health` | 健康检查与当前能力 |
| `POST` | `/api/v1/books` | 上传 `.txt`/`.md` 并建立索引 |
| `GET` | `/api/v1/books` | 查看书库 |
| `GET` | `/api/v1/books/{book_id}` | 查看单本书信息 |
| `DELETE` | `/api/v1/books/{book_id}` | 删除书籍与索引 |
| `POST` | `/api/v1/questions` | 单书或跨书提问 |
| `POST` | `/api/v1/questions/stream` | SSE 流式单书或跨书提问 |

上传示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/books \
  -F "file=@rag_mark/doc.md" \
  -F "title=时空之战"
```

提问示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/questions \
  -H "Content-Type: application/json" \
  -d '{"book_id":"替换为上传返回的 id","question":"大雄为什么决定继续战斗？","top_k":3}'
```

`book_id` 为空时会在全部书籍中检索。响应中的 `evidence` 包含命中片段、召回分数、重排分数和书籍信息，可供前端渲染引用。

前端问答使用 `POST /api/v1/questions/stream`。服务端依次推送：

- `meta`：问题与检索证据
- `delta`：回答文本增量
- `done`：最终回答模式与模型
- `error`：流式异常

## 测试

```bash
cd ai_reading_assistant
make test
make lint
make frontend-build
```
