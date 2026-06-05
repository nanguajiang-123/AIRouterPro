

# 智能 SDN 控制平台技术方案（FastAPI + React + LangGraph）

## 1. 项目概述

构建一个 Web 应用，用户通过前端界面输入源、目标、场景描述（自然语言），后端 Agent 利用 LangGraph 工作流解析意图、获取当前网络拓扑、调用寻路大模型计算最优路径，并通过 ODL 控制器将流表下发到 Mininet 仿真网络。前端采用轮询方式定期获取拓扑状态，以 React 图表库展示网络拓扑图。

ODL控制器北向接口和南向接口的相关ip和监听端口在.env文件中

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器 (React)                        │
│  - 拓扑可视化 (Cytoscape.js / React Flow)                   │
│  - 表单输入 (源、目标、场景描述)                              │
│  - 轮询 GET /api/topology (每隔 3 秒)                        │
│  - POST /api/plan 提交规划请求                               │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端服务 (FastAPI)                          │
│  - 路由: /api/topology, /api/plan                           │
│  - 依赖: LangGraph Agent                                     │
│  - 工具: 调用 ODL REST API                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  OpenDaylight 控制器 (Docker)                 │
│  - REST API (8181)   - OpenFlow (6633)                      │
└─────────────────────────────────────────────────────────────┘
                              │ OpenFlow
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mininet 仿真网络 (WSL2)                    │
└─────────────────────────────────────────────────────────────┘
```

## 3. 后端技术栈（Python）

- **FastAPI**：异步 Web 框架，自动生成 OpenAPI 文档。
- **LangGraph**：编排 Agent 工作流（意图解析 → 拓扑获取 → 路径规划 → 流表下发）。
- **httpx / requests**：调用 ODL REST API。
- **Pydantic**：定义请求/响应数据模型。
- **Uvicorn**：ASGI 服务器。

## 4. 前端技术栈（React）

- **React 18** + **TypeScript**：组件化开发。
- **Vite**：构建工具，快速热更新。
- **Axios**：HTTP 客户端。
- **Cytoscape.js** 或 **React Flow**：网络拓扑可视化（推荐 Cytoscape.js，成熟稳定）。
- **Ant Design / Material-UI**：UI 组件库（可选，用于表单和布局）。

## 5. 后端接口设计

### 5.1 获取网络拓扑（轮询）

- **端点**：`GET /api/topology`
- **响应格式**：
```json
{
  "nodes": [
    { "id": "openflow:1", "name": "s1", "type": "switch" },
    { "id": "h1", "name": "h1", "type": "host" },
    ...
  ],
  "links": [
    { "source": "h1", "target": "openflow:1", "port": 1 },
    { "source": "openflow:1", "target": "openflow:2", "bandwidth": 100, "delay": 5 }
  ]
}
```

- **实现**：从 ODL 的 `opendaylight-inventory:nodes` 和 `network-topology` 聚合数据。

### 5.2 提交路径规划请求

- **端点**：`POST /api/plan`
- **请求体**：
```json
{
  "source": "h1",
  "target": "h3",
  "scenario": "要求延迟最小，带宽不低于 10Mbps"
}
```
- **响应**：
```json
{
  "status": "success",
  "path": ["openflow:1", "openflow:2", "openflow:3"],
  "message": "Flows installed successfully."
}
```

- **处理流程**：调用 LangGraph Agent 执行完整工作流，阻塞等待完成（超时 30 秒）。

## 6. LangGraph Agent 工作流设计（续用之前的节点设计）

- **State**：包含 `user_input`, `source`, `target`, `intent_constraints`, `topology`, `planned_path`, `flows`, `error`。
- **节点**：
  1. `intent_parser`：用 LLM 提取结构化信息（可先简单用规则，后续接入轻量模型）。
  2. `topology_fetcher`：调用 `get_topology()` 工具。
  3. `router_llm`：调用您的寻路大模型（HTTP 或本地）。
  4. `flow_installer`：将路径转为流表并调用 ODL API 下发。
- **图**：顺序执行，任一步骤出错则终止并返回错误。

## 7. 前端实现要点

### 7.1 拓扑轮询

```tsx
useEffect(() => {
  const interval = setInterval(async () => {
    const res = await axios.get('/api/topology');
    setTopologyData(res.data);
  }, 3000);
  return () => clearInterval(interval);
}, []);
```

### 7.2 可视化组件（Cytoscape.js）

```tsx
import CytoscapeComponent from 'react-cytoscapejs';

const elements = [
  { data: { id: 's1', label: 's1' } },
  { data: { id: 'h1', label: 'h1' } },
  { data: { source: 'h1', target: 's1' } }
];

return <CytoscapeComponent elements={elements} style={{ width: '100%', height: '600px' }} />;
```

### 7.3 表单提交

```tsx
const handleSubmit = async (e) => {
  e.preventDefault();
  const response = await axios.post('/api/plan', { source, target, scenario });
  alert(`路径: ${response.data.path.join(' → ')}`);
};
```

## 8. 项目结构

```
sdn-planner/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── agent/
│   │   │   ├── graph.py         # LangGraph 定义
│   │   │   ├── nodes.py         # 各节点实现
│   │   │   ├── tools.py         # ODL 调用工具
│   │   │   └── state.py         # State 定义
│   │   ├── routers/
│   │   │   ├── topology.py      # /api/topology
│   │   │   └── plan.py          # /api/plan
│   │   └── models/
│   │       └── schemas.py       # Pydantic 模型
│   ├── requirements.txt
│   └── Dockerfile (可选)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TopologyView.tsx
│   │   │   └── PlanForm.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── docker-compose.yml (可选，用于启动后端和 ODL)
```

## 9. 部署与运行

### 9.1 后端启动
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 9.2 前端启动
```bash
cd frontend
npm install
npm run dev
```

### 9.3 代理配置（解决跨域）
在 `vite.config.ts` 中配置代理：
```ts
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}
```

## 10. 扩展与优化

- **提升实时性**：后期可将拓扑轮询改为 WebSocket 推送，由后端在拓扑变化时主动推送。
- **意图解析增强**：接入 GPT-3.5 或本地小模型（如 Qwen-1.8B）进行更准确的场景理解。
- **流表批量下发**：使用 ODL 的 `sal-flow-batch` 等批量接口提高效率。
- **前端缓存**：对拓扑数据进行 Redux 或 Zustand 管理，避免频繁重绘。

## 11. 风险与应对

| 风险 | 应对 |
|------|------|
| ODL 响应慢导致前端轮询超时 | 后端增加缓存，减少对 ODL 的直接调用频率 |
| 大模型推理耗时（>10s） | 将规划任务异步化，前端轮询任务状态 |
| 前端拓扑图性能（节点过多） | 限制显示节点数量，或使用虚拟滚动 |
| 跨域问题 | 使用 Vite 代理或后端配置 CORS 中间件 |

## 12. 后续工作

1. 实现 `backend/app/agent/tools.py` 中的 ODL REST 调用。
2. 实现 `router_llm_node` 中与您的寻路大模型的集成。
3. 前端完成拓扑图交互（点击节点显示详情、高亮路径等）。
4. 编写单元测试和集成测试。

---

**这份技术方案可以立即开始编码。** 如果需要具体代码片段（例如 `tools.py` 中完整的 ODL 拓扑获取函数、或 `plan.py` 路由的完整实现），请告知，我可以提供详细代码。
