# AI Webtoon Factory — 前端开发规范

> **版本**：v1.0  
> **最后更新**：2026-06-27  
> **状态**：草案  
> **适用技术栈**：React 18 + TypeScript + Vite + Zustand + Ant Design 5.x + Konva.js

---

## 1. 项目结构

```
frontend/
├── src/
│   ├── main.tsx                        # 应用入口
│   ├── App.tsx                         # 路由配置
│   ├── vite-env.d.ts
│   │
│   ├── pages/                          # 页面级组件
│   │   ├── Dashboard/                  #   工作台
│   │   ├── NovelManager/               #   小说管理
│   │   ├── CharacterManager/           #   人物 IP
│   │   ├── WorldBuilding/              #   世界观资产
│   │   ├── SceneManager/               #   剧情拆解
│   │   ├── StoryboardCenter/           #   分镜中心
│   │   ├── LayoutCenter/               #   版式中心
│   │   ├── TextCenter/                 #   漫画文本
│   │   ├── PromptCenter/               #   Prompt 中心
│   │   ├── GenerationCenter/           #   生图中心
│   │   ├── QualityCenter/              #   质量控制
│   │   ├── ComicEditor/                #   漫画编辑器 (Konva.js)
│   │   ├── ExportCenter/               #   导出中心
│   │   ├── ResourceCenter/             #   资源中心
│   │   ├── ModelCenter/                #   AI 模型
│   │   ├── PluginCenter/               #   插件中心
│   │   ├── SystemSettings/             #   系统管理
│   │   └── HelpCenter/                 #   帮助中心
│   │
│   ├── components/                     # 通用组件
│   │   ├── Layout/                     #   布局组件
│   │   │   ├── AppLayout.tsx           #     主布局（侧栏+顶栏+内容区）
│   │   │   ├── Sidebar.tsx             #     侧栏导航
│   │   │   ├── Header.tsx              #     顶栏
│   │   │   └── Breadcrumb.tsx          #     面包屑
│   │   ├── PanelPreview/              #   画格预览
│   │   ├── ImageGallery/              #   图片画廊
│   │   ├── TaskQueue/                 #   任务队列
│   │   ├── CharacterRelationGraph/    #   人物关系图
│   │   ├── NovelReader/               #   小说阅读器
│   │   ├── PromptEditor/              #   Prompt 编辑器
│   │   ├── ImageViewer/               #   图片查看器
│   │   └── common/                    #   原子组件
│   │       ├── Loading.tsx
│   │       ├── EmptyState.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── ConfirmDialog.tsx
│   │
│   ├── stores/                         # Zustand 状态存储
│   │   ├── novelStore.ts
│   │   ├── sceneStore.ts
│   │   ├── panelStore.ts
│   │   ├── characterStore.ts
│   │   ├── taskStore.ts
│   │   ├── generationStore.ts
│   │   ├── editorStore.ts
│   │   ├── uiStore.ts                  # UI 状态（侧栏折叠、主题等）
│   │   └── authStore.ts
│   │
│   ├── hooks/                          # 自定义 Hooks
│   │   ├── useWebSocket.ts
│   │   ├── useIntersectionObserver.ts
│   │   ├── useDebounce.ts
│   │   ├── usePagination.ts
│   │   └── useKeyboard.ts
│   │
│   ├── api/                            # API 客户端
│   │   ├── client.ts                   #   Axios 实例 + 拦截器
│   │   ├── novelApi.ts
│   │   ├── characterApi.ts
│   │   ├── sceneApi.ts
│   │   ├── panelApi.ts
│   │   ├── generationApi.ts
│   │   └── ...
│   │
│   ├── types/                          # TypeScript 类型定义
│   │   ├── novel.ts
│   │   ├── scene.ts
│   │   ├── panel.ts
│   │   ├── character.ts
│   │   ├── prompt.ts
│   │   ├── image.ts
│   │   ├── task.ts
│   │   └── api.ts                      # 通用 API 响应类型
│   │
│   └── utils/                          # 工具函数
│       ├── canvas.ts                   #   Konva.js 工具
│       ├── format.ts                   #   日期、数字格式化
│       ├── validation.ts               #   表单校验
│       └── constants.ts                #   常量定义
│
├── public/
│   └── favicon.svg
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json                 # 规划中
├── tailwind.config.js
├── postcss.config.js
├── package.json
└── Dockerfile                          # 规划中
```

---

## 2. 开发环境搭建

### 2.1 前置条件

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Node.js | 20+ | 推荐使用 nvm 管理版本 |
| npm / pnpm | 9+ / 8+ | 推荐使用 pnpm（更快、节省磁盘） |

### 2.2 安装步骤

```bash
# 1. 进入前端目录
cd webtoon-factory/frontend

# 2. 安装依赖
pnpm install

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 VITE_API_BASE_URL=http://localhost:8000/api/v1

# 4. 启动开发服务器
pnpm run dev
# 默认在 http://localhost:5173 启动

# 5. 构建生产版本
pnpm run build
```

### 2.3 环境变量

```env
# .env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_APP_TITLE=AI Webtoon Factory
```

> **注意**：前端配置中禁止包含任何 API Key、Secret 等敏感信息。所有敏感凭据仅在后端管理。

---

## 3. 核心架构模式

### 3.1 页面路由

使用 React Router 6 的嵌套路由结构：

```tsx
// App.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import AppLayout from '@/components/Layout/AppLayout';
import Dashboard from '@/pages/Dashboard';
import NovelManager from '@/pages/NovelManager';
import ComicEditor from '@/pages/ComicEditor';
// ...

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'projects/:id/novels', element: <NovelManager /> },
      { path: 'projects/:id/editor', element: <ComicEditor /> },
      // ... 其他页面路由
    ],
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
```

### 3.2 状态管理（Zustand）

使用 Zustand 进行状态管理，遵循以下规范：

```tsx
// stores/novelStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { novelApi } from '@/api/novelApi';
import type { Novel } from '@/types/novel';

interface NovelState {
  // 状态
  novels: Novel[];
  currentNovel: Novel | null;
  loading: boolean;
  error: string | null;

  // 动作
  fetchNovels: (projectId: string) => Promise<void>;
  setCurrentNovel: (novel: Novel | null) => void;
  createNovel: (data: CreateNovelDto) => Promise<void>;
}

export const useNovelStore = create<NovelState>()(
  devtools(
    (set) => ({
      novels: [],
      currentNovel: null,
      loading: false,
      error: null,

      fetchNovels: async (projectId) => {
        set({ loading: true, error: null });
        try {
          const novels = await novelApi.list(projectId);
          set({ novels, loading: false });
        } catch (e) {
          set({ error: (e as Error).message, loading: false });
        }
      },

      setCurrentNovel: (novel) => set({ currentNovel: novel }),

      createNovel: async (data) => {
        const novel = await novelApi.create(data);
        set((state) => ({ novels: [...state.novels, novel] }));
      },
    }),
    { name: 'novel-store' }
  )
);
```

**Store 设计原则：**

1. **按模块拆分**：每个业务模块一个 Store，避免巨型 Store
2. **只存必要状态**：能从 API 重新获取的数据不持久化到 Store
3. **UI 状态与业务状态分离**：`uiStore` 管理主题、侧栏折叠等，业务 Store 管理数据
4. **Actions 命名规范**：`fetch*`（获取）、`create*`（创建）、`update*`（更新）、`delete*`（删除）
5. **错误处理**：每个异步 Action 必须处理 loading/error 状态

### 3.3 API 调用（Axios）

```tsx
// api/client.ts
import axios from 'axios';
import { useAuthStore } from '@/stores/authStore';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动附加 Token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一错误处理
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

```tsx
// api/novelApi.ts
import apiClient from './client';
import type { Novel, CreateNovelDto, UpdateNovelDto } from '@/types/novel';

export const novelApi = {
  list: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/novels`),

  getById: (novelId: string) =>
    apiClient.get(`/novels/${novelId}`),

  create: (data: CreateNovelDto) =>
    apiClient.post('/novels', data),

  update: (novelId: string, data: UpdateNovelDto) =>
    apiClient.patch(`/novels/${novelId}`, data),

  delete: (novelId: string) =>
    apiClient.delete(`/novels/${novelId}`),
};
```

### 3.4 WebSocket 连接

```tsx
// hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react';
import { useTaskStore } from '@/stores/taskStore';

export function useWebSocket(taskId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const updateTask = useTaskStore((state) => state.updateTask);

  useEffect(() => {
    const ws = new WebSocket(
      `${import.meta.env.VITE_WS_URL}/task/${taskId}`
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      updateTask(data.taskId, {
        status: data.status,
        progress: data.progress,
        result: data.result,
      });
    };

    ws.onclose = () => {
      // 自动重连
      setTimeout(() => { /* 重连逻辑 */ }, 3000);
    };

    wsRef.current = ws;
    return () => ws.close();
  }, [taskId]);

  return wsRef;
}
```

---

## 4. 组件开发规范

### 4.1 通用组件

- 位于 `src/components/common/` 目录
- 必须使用 TypeScript 接口定义 Props
- 必须包含 ErrorBoundary 包裹
- 遵循原子设计原则：Atom → Molecule → Organism

```tsx
// components/common/Loading.tsx
interface LoadingProps {
  size?: 'small' | 'medium' | 'large';
  text?: string;
  fullScreen?: boolean;
}

export function Loading({ size = 'medium', text, fullScreen }: LoadingProps) {
  return (
    <div className={`flex items-center justify-center ${fullScreen ? 'h-screen' : 'h-full'}`}>
      <Spin size={size} />
      {text && <p className="ml-3 text-gray-500">{text}</p>}
    </div>
  );
}
```

### 4.2 页面组件

- 位于 `src/pages/` 目录，每个页面一个文件夹
- 页面组件命名：`PageNamePage.tsx`（如 `NovelManagerPage.tsx`）
- 页面内部子组件放在同一文件夹下（仅当该子组件不共享给其他页面时）

```tsx
// pages/NovelManager/NovelManagerPage.tsx
import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useNovelStore } from '@/stores/novelStore';
import { NovelList } from './components/NovelList';
import { NovelUploader } from './components/NovelUploader';
import { Loading } from '@/components/common/Loading';

export default function NovelManagerPage() {
  const { id: projectId } = useParams();
  const { novels, loading, fetchNovels } = useNovelStore();

  useEffect(() => {
    if (projectId) fetchNovels(projectId);
  }, [projectId]);

  if (loading) return <Loading text="加载小说列表中..." />;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">小说管理</h1>
        <NovelUploader projectId={projectId!} />
      </div>
      <NovelList novels={novels} />
    </div>
  );
}
```

### 4.3 编辑器组件（Konva.js）

漫画编辑器是系统最复杂的组件，基于 Konva.js 实现。开发规范如下：

```tsx
// pages/ComicEditor/components/CanvasEditor.tsx
import React, { useRef, useEffect } from 'react';
import { Stage, Layer, Image as KonvaImage, Transformer } from 'react-konva';
import useImage from 'use-image';

interface CanvasEditorProps {
  panelImages: PanelImage[];
  width: number;
  height: number;
  onSelect?: (panelId: string) => void;
}

export function CanvasEditor({ panelImages, width, height, onSelect }: CanvasEditorProps) {
  const stageRef = useRef<Konva.Stage>(null);
  const transformerRef = useRef<Konva.Transformer>(null);

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      scaleX={1}
      scaleY={1}
    >
      <Layer>
        {/* Panel 图片层 */}
        {panelImages.map((panel) => (
          <PanelImageNode
            key={panel.id}
            panel={panel}
            onSelect={() => onSelect?.(panel.id)}
          />
        ))}
      </Layer>
      <Layer>
        {/* 气泡层 */}
        {bubbles.map((bubble) => (
          <BubbleNode key={bubble.id} bubble={bubble} />
        ))}
      </Layer>
      <Transformer ref={transformerRef} />
    </Stage>
  );
}
```

**编辑器组件规范：**
- 所有 Canvas 操作通过 Konva.Node 接口，不直接操作 DOM
- 编辑器状态使用独立的 `editorStore` 管理
- 图片加载使用 `use-image` hook（内置缓存）
- 缩放/平移使用 Stage 的 scale/position 属性，不修改图片本身

---

## 5. 如何添加新页面

### 5.1 步骤

1. 在 `src/pages/` 下创建页面目录：`mkdir src/pages/YourNewPage/`
2. 在目录中创建页面主组件：`YourNewPage.tsx`
3. 在目录中创建所需的子组件（可选）
4. 在 `src/api/` 中添加对应的 API 函数
5. 在 `src/stores/` 中添加对应的 Store
6. 在 `src/types/` 中添加对应的类型定义
7. 在 `App.tsx` 中注册路由

### 5.2 页面文件模板

```tsx
// pages/YourNewPage/YourNewPage.tsx
import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { PageHeader } from '@/components/common/PageHeader';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { useYourStore } from '@/stores/yourStore';

export default function YourNewPage() {
  const { id } = useParams();
  const { data, loading, error, fetchData } = useYourStore();

  useEffect(() => {
    fetchData(id!);
  }, [id]);

  if (loading) return <Loading text="加载中..." />;
  if (error) return <EmptyState type="error" message={error} />;
  if (!data) return <EmptyState type="empty" message="暂无数据" />;

  return (
    <div className="p-6">
      <PageHeader
        title="新页面"
        subtitle="页面描述"
        actions={[
          { label: '创建', onClick: handleCreate, type: 'primary' },
        ]}
      />
      {/* 页面内容 */}
    </div>
  );
}
```

### 5.3 路由注册

```tsx
// App.tsx
{
  path: 'projects/:id/your-new-page',
  element: <YourNewPage />,
}
```

---

## 6. 状态管理规范

### 6.1 数据流原则

```
用户操作 → 组件事件 → Store Action → API 调用 → 后端接口
                                                     ↓
用户界面 ← 组件渲染 ← Store State  ←  更新 Store  ←┘
```

### 6.2 状态分类

| 状态类型 | 存储位置 | 示例 |
|----------|----------|------|
| 服务端数据 | 业务 Store | 小说列表、Panel 数据 |
| UI 状态 | uiStore | 侧栏折叠、当前 Tab |
| 表单状态 | 组件内 useState | 输入框值、校验状态 |
| 路由参数 | URL Params | projectId, novelId |
| 缓存数据 | IndexedDB / localStorage | 用户偏好设置 |

### 6.3 状态更新规则

- **不可变更新**：永远使用不可变方式更新状态（Zustand 默认支持）
- **批量更新**：相关的状态变更合并到一个 set 调用中
- **派生状态**：能用已有状态计算得到的，不要单独存储
- **持久化**：仅持久化用户设置、主题偏好等非频繁变更的数据

---

## 7. 性能优化指南

### 7.1 渲染优化

| 策略 | 说明 | 使用场景 |
|------|------|----------|
| React.memo | 组件 Props 浅比较，避免无关渲染 | 列表项、频繁更新的组件 |
| useMemo | 缓存计算结果 | 复杂数据转换、过滤 |
| useCallback | 缓存回调函数 | 传递给子组件的回调 |
| 虚拟滚动 | 仅渲染可见区域 DOM | Panel 长列表、图片画廊 |

### 7.2 图片优化

```tsx
// 图片懒加载
import { useInView } from 'react-intersection-observer';

function LazyImage({ src, alt }: { src: string; alt: string }) {
  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: '200px',
  });

  return (
    <div ref={ref}>
      {inView ? (
        <img src={src} alt={alt} loading="lazy" />
      ) : (
        <div className="skeleton w-full h-48" />
      )}
    </div>
  );
}
```

### 7.3 代码分割

```tsx
// 按页面路由分割
const ComicEditor = React.lazy(() => import('@/pages/ComicEditor'));
const NovelManager = React.lazy(() => import('@/pages/NovelManager'));

// 使用 Suspense 包裹
<Suspense fallback={<Loading fullScreen />}>
  <ComicEditor />
</Suspense>
```

### 7.4 状态更新节流

WebSocket 任务状态推送频率可能很高，需要进行渲染节流：

```tsx
// hooks/useThrottledWebSocket.ts
import { useRef, useCallback } from 'react';

export function useThrottledUpdate(callback: (data: any) => void, fps = 30) {
  const lastUpdate = useRef(0);
  const frameId = useRef<number>();

  return useCallback((data: any) => {
    const now = Date.now();
    const interval = 1000 / fps;

    if (now - lastUpdate.current >= interval) {
      callback(data);
      lastUpdate.current = now;
    } else {
      // 使用 requestAnimationFrame 合并渲染
      cancelAnimationFrame(frameId.current!);
      frameId.current = requestAnimationFrame(() => {
        callback(data);
        lastUpdate.current = Date.now();
      });
    }
  }, [callback, fps]);
}
```

### 7.5 缓存策略

- **API 响应缓存**：使用 Zustand 的 persist 中间件 + localStorage 缓存非敏感数据
- **图片缓存**：浏览器 `Cache-Control` + ETag，已确认 Panel 图可缓存 24 小时
- **Konva.js 节点缓存**：使用 `cache()` 方法缓存静态节点为 Canvas Bitmap
- **大数据集缓存**：Scene/Panel 列表使用 IndexedDB 离线缓存

---

## 附录 A：依赖清单

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.22.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.0",
    "antd": "^5.12.0",
    "@ant-design/icons": "^5.2.0",
    "konva": "^9.3.0",
    "react-konva": "^18.2.0",
    "use-image": "^1.1.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.0",
    "react-intersection-observer": "^9.8.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0"
  }
}
```

---

*本文档为前端开发的核心规范，所有前端开发人员必须遵守。*
