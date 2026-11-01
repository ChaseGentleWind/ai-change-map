# 前端开发说明

前端使用 Vue 3、TypeScript、Vite、Tailwind CSS 和 Axios。开发服务器默认运行在 `http://localhost:5174`，`/api` 由 Vite 代理到 `http://localhost:8001`。图片通过 `/api/assets/{id}` 从数据库读取。

```powershell
npm ci
npm run dev
npm run build
```

页面入口位于 `src/views/`，通用编辑器组件位于 `src/components/`，API 请求统一封装在 `src/api/index.ts`。
