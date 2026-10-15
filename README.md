# Travel Agent 智能旅行规划助手

这是一个面向学习和面试展示的 AI 旅行规划项目。项目采用前后端分离架构，前端负责收集用户旅行需求和展示结果，后端负责调用大模型、地图工具和 LangGraph 工作流生成结构化行程。

当前版本已将核心规划链路改写为 LangGraph 工作流，同时保留原有 HelloAgents 相关代码作为对照参考，方便学习不同 Agent 架构的实现方式。

## 项目亮点

- 前后端分离：Vue 3 + TypeScript 前端，FastAPI 后端。
- LangGraph 工作流：将旅行规划拆分为景点搜索、天气查询、酒店搜索、行程生成、结果校验和修复等节点。
- LangChain 模型集成：通过 `langchain-openai` 接入 OpenAI 兼容模型。
- 高德地图 MCP 工具：用于 POI 搜索、天气查询、路线规划等地图能力。
- 结构化输出：使用 Pydantic 模型约束最终返回的 `TripPlan`。
- 结果页能力完整：支持每日行程、预算、天气、地图标记、景点图片、编辑行程和导出 PDF/图片。

## 技术栈

### 后端

- Python 3.10+
- FastAPI
- LangGraph
- LangChain / langchain-openai
- Pydantic
- HelloAgents
- 高德地图 MCP 服务 `amap-mcp-server`
- Uvicorn

### 前端

- Vue 3
- TypeScript
- Vite
- Ant Design Vue
- Axios
- 高德地图 JavaScript API
- html2canvas
- jsPDF

## 项目结构

```text
helloagents-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── trip_planner_agent.py      # 原 HelloAgents 版本，作为学习对照
│   │   ├── api/
│   │   │   ├── main.py                    # FastAPI 应用入口
│   │   │   └── routes/
│   │   │       ├── trip.py                # 行程规划 API
│   │   │       ├── map.py                 # 地图相关 API
│   │   │       └── poi.py                 # POI 与图片相关 API
│   │   ├── graphs/
│   │   │   └── trip_graph.py              # LangGraph 行程规划工作流
│   │   ├── models/
│   │   │   └── schemas.py                 # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── amap_service.py            # 高德地图 MCP 封装
│   │   │   ├── llm_service.py             # 原 LLM 服务封装
│   │   │   └── unsplash_service.py        # 景点图片服务
│   │   └── config.py                      # 环境变量与配置管理
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── api.ts                     # 前端 API 调用
│   │   ├── types/
│   │   │   └── index.ts                   # TypeScript 类型定义
│   │   └── views/
│   │       ├── Home.vue                   # 旅行需求表单页
│   │       └── Result.vue                 # 行程结果展示页
│   ├── package.json
│   └── vite.config.ts
├── LANGGRAPH_REWRITE.md                   # LangGraph 改写说明
└── README.md
```

## 当前架构

前端提交旅行需求后，后端通过 FastAPI 接收请求，并交给 LangGraph 工作流生成行程。

```text
Vue 表单
  -> POST /api/trip/plan
  -> FastAPI
  -> LangGraphTripPlanner
      -> search_attractions
      -> get_weather
      -> search_hotels
      -> generate_plan
      -> validate_plan
      -> repair_plan, 当校验失败时触发一次
  -> TripPlanResponse
  -> Vue 结果页展示
```

核心实现位于：

```text
backend/app/graphs/trip_graph.py
```

API 入口位于：

```text
backend/app/api/routes/trip.py
```

## LangGraph 工作流说明

`TripGraphState` 是整个工作流的状态对象，保存以下信息：

- 用户原始请求 `TripRequest`
- 景点搜索结果
- 天气查询结果
- 酒店搜索结果
- 大模型原始输出
- 校验后的 `TripPlan`
- 错误信息
- 修复次数

工作流节点职责：

```text
search_attractions  搜索目的地相关景点
get_weather         查询目的地天气
search_hotels       搜索住宿相关信息
generate_plan       调用大模型生成结构化行程
validate_plan       使用 Pydantic 校验 TripPlan
repair_plan         当 JSON 或字段校验失败时修复输出
```

这样设计的好处是：流程显式、状态可追踪、错误可恢复，比单个黑盒 Agent 更适合工程化和面试讲解。

## 环境变量

后端需要配置以下变量：

```env
AMAP_API_KEY=你的高德地图 Web 服务 API Key
LLM_API_KEY=你的大模型 API Key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_ID=gpt-4o-mini
```

前端需要配置：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_WEB_JS_KEY=你的高德地图 Web JS API Key
```

## 后端启动

项目根目录下已推荐使用 `.venv` 虚拟环境。

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r backend\requirements.txt
```

启动后端：

```powershell
python backend\run.py
```

也可以不激活虚拟环境，直接运行：

```powershell
.\.venv\Scripts\python.exe backend\run.py
```

后端默认地址：

```text
http://localhost:8000
```

API 文档：

```text
http://localhost:8000/docs
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:5173
```

## 主要 API

```text
POST /api/trip/plan        生成旅行计划
GET  /api/trip/health      检查旅行规划服务
GET  /api/map/poi          搜索 POI
GET  /api/map/weather      查询天气
POST /api/map/route        规划路线
GET  /api/poi/photo        获取景点图片
```

## 前端页面说明

首页 `Home.vue`：

- 输入目的地城市
- 选择开始日期和结束日期
- 自动计算旅行天数
- 选择交通方式
- 选择住宿偏好
- 勾选旅行偏好
- 填写额外需求
- 提交生成旅行计划

结果页 `Result.vue`：

- 展示行程概览
- 展示预算明细
- 展示每日景点、餐饮和酒店
- 展示天气信息
- 使用高德地图展示景点标记和路线
- 支持编辑景点顺序和内容
- 支持导出图片和 PDF

## 面试讲解思路

可以从以下角度介绍这个项目：

1. 项目是一个 AI Travel Planner，采用 Vue + FastAPI 的前后端分离架构。
2. 原版本使用 HelloAgents 顺序调用多个 Agent，新版本将核心流程改成 LangGraph 状态机。
3. LangGraph 将复杂任务拆成多个节点，每个节点只负责一个明确职责。
4. LangChain 负责接入 OpenAI 兼容模型，LangGraph 负责任务编排和状态流转。
5. 使用 Pydantic 对 LLM 输出做结构化校验，避免错误 JSON 直接返回前端。
6. 非空输出校验失败时进入 `repair_plan` 修复一次；超时或修复仍失败会明确返回服务错误，避免将占位数据当作成功行程。
7. 前端结果页不仅展示文本，还结合地图、图片、预算和导出能力，形成完整用户体验。

一句话总结：

```text
这个项目展示了如何把一个普通旅行规划应用，升级为可观测、可校验、可恢复的 LangGraph 多步骤 Agent 工作流。
```

## 学习路线

建议按以下顺序阅读代码：

1. `frontend/src/views/Home.vue`：理解用户输入如何形成请求。
2. `frontend/src/services/api.ts`：理解前端如何调用后端。
3. `backend/app/models/schemas.py`：理解请求和响应数据结构。
4. `backend/app/api/routes/trip.py`：理解 API 如何调用规划器。
5. `backend/app/graphs/trip_graph.py`：重点阅读 LangGraph 工作流。
6. `frontend/src/views/Result.vue`：理解结果如何展示、编辑和导出。

## 常见问题

### 模型响应超时

在 `backend/.env` 设置 `LLM_TIMEOUT=120`（每次模型调用的读取等待时间，秒）及 `LLM_MAX_RETRIES=0`。
修改后重启后端。连接超时单独设为10秒，SDK默认不再自动重试；前端规划等待时间为10分钟，包含地图查询和必要的输出修复。
服务日志使用 `trip` 请求编号记录生成/修复阶段、提示词字符数和调用耗时，不打印密钥或完整提示词。
模型超时返回 HTTP 504，模型调用或输出失败返回 HTTP 502，不再返回占位行程或将空输出送入修复节点。
仅非空但格式或行程约束错误的输出修复一次；无效请求日期或日期与天数不匹配会在调用模型前返回 HTTP 422。
更长等待不能保证上游模型可用；仍超时时可缩短旅行天数，或检查模型服务与网络。

### 多轮对话、历史会话与联网检索

首页生成行程时创建后端会话；结果页可继续发送需求，例如“第二天换成博物馆，其他日期不变”或“博物馆几点开放，需要预约吗”。
首页的“查看历史会话”与结果页下拉框可恢复历史记录，刷新或重启后端后仍可读取。
旧版浏览器行程可点击“将当前行程保存为会话”迁移。手动编辑保存后也会同步至后端，并重算预算。

在 `backend/.env` 配置 `TAVILY_API_KEY`，然后重启后端。检索工具通过 LangChain 工具绑定由模型按需调用，
提供开放时间、预约要求及出行公告的参考来源，不代为预约或购票。信息来自搜索摘要时会注明待核实；
缺少密钥或检索失败不会编造规则。当前模型必须支持 OpenAI 兼容的工具调用（tool_calls）。

新增 API：

```text
POST  /api/conversations                  创建会话（request 为原 TripRequest，plan 可用于迁移已有行程）
GET   /api/conversations                  会话列表
GET   /api/conversations/{id}             恢复会话及行程
POST  /api/conversations/{id}/messages     {content, expected_version}
PATCH /api/conversations/{id}/plan         {plan, expected_version}
```

SQLite 默认保存在 `backend/data/`，包含会话快照、LangGraph checkpoints 和一小时的搜索缓存，已加入 Git 忽略。
可用 `CONVERSATION_DATA_DIR` 自定义目录。当前面向本地单用户、单后端实例；未加入账户鉴权，历史接口展示本实例的全部会话。
相同会话的更新串行执行，版本过期返回 HTTP 409；新城市或新日期范围应另建会话。
对话失败时保留原行程；超长对话向模型提供最近十二条消息及持久化需求约束，数据库保存完整可见历史。

更新依赖与运行测试：

```powershell
uv pip install --python .\.venv\Scripts\python.exe -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_conversation*.py"
```

### 高德 MCP 出现 `Event loop is closed` 或工具数量为 0

当前高德服务使用官方 MCP Python SDK 管理 stdio 会话，在事件循环关闭前退出会话和子进程。
`amap-mcp-server==0.1.11` 固定依赖 `mcp==1.8.1`，与较新的 Pydantic 存在导入兼容问题，
因此子进程使用 `uvx --with pydantic==2.10.6 amap-mcp-server==0.1.11`。
该版本限制仅作用于 uvx 的独立环境，不影响后端的 Pydantic。

在项目根目录运行真实 MCP 测试（需要网络和有效的 Web 服务 Key）：

```powershell
.\.venv\Scripts\python.exe backend\test_amap_mcp.py
```

测试会列出工具并查询杭州景点和天气。启动或工具调用失败会明确报错，不再将空工具列表打印为初始化成功。
修改后停止旧后端，再从 `backend` 目录运行 `..\.venv\Scripts\python.exe run.py`。

本地回归测试不需要高德密钥或网络：

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_amap_mcp.py
```

### 为什么保留 HelloAgents 代码？

保留 `backend/app/agents/trip_planner_agent.py` 是为了学习对比。你可以比较两种实现：

- HelloAgents 版本：更像顺序调用多个 Agent。
- LangGraph 版本：更像显式状态机，适合复杂工作流。

### 为什么需要 Pydantic 校验？

LLM 输出具有不确定性，可能出现字段缺失、类型错误或 JSON 格式错误。Pydantic 可以把“模型输出”约束成前端可安全使用的数据结构。

### 模型失败后会返回 fallback 吗？

当前接口不再用 fallback 隐藏模型超时或无效输出，而是返回明确错误；已有会话行程保持不变。fallback 构造函数保留作测试和历史参考。

## License

CC BY-NC-SA 4.0

