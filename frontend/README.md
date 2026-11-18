# AI 读书助手前端

Angular 20 standalone 应用，使用 Signals、HttpClient 和 Lucide 图标。

## 开发

```bash
cd frontend
npm install
npm start
```

开发服务器运行在 `http://127.0.0.1:4200`，`/api` 请求会由 `proxy.conf.json` 转发到 `http://127.0.0.1:8000`。问答使用 `fetch + ReadableStream` 解析 SSE，并逐段渲染回答。

## 构建

```bash
npm run build
```
