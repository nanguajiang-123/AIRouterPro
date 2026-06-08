# 意图驱动的自智 SDN 实验平台

> 基于 React Flow + Flask/FastAPI + XCHiRL (RL) + Mininet/ODL 的全栈自智网络实验平台。
> 用户通过自然语言描述流量意图，系统自动解析 → 调用强化学习模型寻路 → 下发流表 → 前端可视化展示。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [核心工作流](#3-核心工作流)
4. [后端模块设计](#4-后端模块设计)
5. [前端模块设计](#5-前端模块设计)
6. [XCHiRL 模型集成](#6-xchirl-模型集成)
7. [API 接口设计](#7-api-接口设计)
8. [数据模型](#8-数据模型)
9. [Mininet 脚本生成与端口分配](#9-mininet-脚本生成与端口分配)
10. [流表生成与下发](#10-流表生成与下发)
11. [项目结构](#11-项目结构)
12. [部署与运行](#12-部署与运行)
13. [端到端测试流程](#13-端到端测试流程)

---

## 1. 项目概述

### 1.1 目标

构建一个 Web 应用：用户在前端编辑 GEANT 拓扑的链路属性（时延、带宽、丢包率），输入自然语言意图（如"让节点 2 到节点 5 的流量走低延迟路径"），系统通过 XCHiRL 强化学习模型计算最优路径，下发流表到 Mininet 仿真网络，并在 React Flow 画布上高亮展示路径。

### 1.2 约束

| 约束项 | 说明 |
|--------|------|
| 拓扑 | **固定为 GEANT 拓扑**（22 节点，36 条无向边），用户不可增删节点或连接 |
| 模型 | 推理使用 **XCHiRL Policy**（P4 模式，metrics dim=2），仅适用于 GEANT |
| 后端 | 必须校验前端提交拓扑与 GEANT 一致，否则返回 400 |
| 主机 | 每个交换机节点关联一个主机，IP 约定为 `10.0.0.x`（x 为节点 ID） |
| 端口 | 交换机端口按连接顺序自动分配（第 1 个邻居 → port 1，第 2 个邻居 → port 2） |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      浏览器 (React + React Flow)                      │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ TopologyCanvas   │  │  PropertyPanel   │  │  IntentPanel     │   │
│  │ (GEANT 拓扑展示)  │  │  (编辑链路属性)   │  │  (意图输入框)    │   │
│  │ 高亮路径/动画     │  │ delay/bw/loss    │  │  执行按钮       │   │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP (fetch / axios)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     后端服务 (Flask / FastAPI)                        │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ /topology    │  │ /intent      │  │ /status      │  │ /ws     │ │
│  │ 接收拓扑验证  │  │ 意图+拓扑→路径│  │ 网络状态查询  │  │ 实时性能│ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────────┘ │
│         │                 │                 │                       │
│  ┌──────▼─────────────────▼─────────────────▼──────────────┐       │
│  │                   核心逻辑层                              │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │       │
│  │  │ 拓扑校验器    │  │ 意图解析器    │  │ flow_manager   │ │       │
│  │  │ (GEANT校验)   │  │ (LLM/模拟)   │  │ ODL/ovs-ofctl │ │       │
│  │  └──────────────┘  └──────┬───────┘  └────────────────┘ │       │
│  │                           │                              │       │
│  │                    ┌──────▼───────┐                      │       │
│  │                    │ model_infer  │                      │       │
│  │                    │ (XCHiRL)     │                      │       │
│  │                    └──────────────┘                      │       │
│  └──────────────────────────────────────────────────────────┘       │
│                           │                                         │
│  ┌────────────────────────▼────────────────────────────┐            │
│  │              Mininet 脚本生成器                       │            │
│  │  ┌─────────────────┐  ┌────────────────────────────┐ │            │
│  │  │ generate_script  │  │ topology_map.json (端口映射)│ │            │
│  │  └─────────────────┘  └────────────────────────────┘ │            │
│  └─────────────────────────────────────────────────────┘            │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Mininet (WSL2)                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  GEANT 拓扑仿真网络 (22 switches + 22 hosts)                   │   │
│  │  TCLink(delay, bw, loss) × 36 条链路                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                   │  OpenFlow 1.3                   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 OpenDaylight 控制器 (Docker)                         │
│  REST API (8181)  ·  OpenFlow (6633)  ·  SSH (8101)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据流方向

```
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：编辑 & 锁定拓扑                                       │
│                                                             │
│ 用户编辑链路属性 → 点击「锁定拓扑」                             │
│     │                                                       │
│     ▼                                                       │
│ POST /topology（发送当前拓扑数据）                              │
│     │                                                       │
│     ▼                                                       │
│ 后端校验 GEANT 结构 → 生成 Mininet 脚本 → 生成 topology_map   │
│     │                        │                               │
│     ▼                        ▼                               │
│ 返回 {status: "locked"}  拉起/更新 Mininet 网络              │
│     │                                                       │
│     ▼                                                       │
│ 前端切换至锁定状态（编辑功能禁用，标记🔒）                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段二：意图执行（拓扑已锁定）                                 │
│                                                             │
│ 用户在锁定状态下输入意图文本 → 点击「执行意图」                  │
│     │                                                       │
│     ▼                                                       │
│ POST /intent {intent_text}（拓扑已在后端锁定）                 │
│     │                                                       │
│     ▼                                                       │
│ 后端解析意图 → XCHiRL 推理 → 流表生成 → ODL 下发             │
│     │                                              │        │
│     ▼                                              ▼        │
│ 返回 {path, ports, nodes}                      Mininet 执行  │
│     │                                                        │
│     ▼                                                        │
│ 前端高亮路径（React Flow 边/节点变色、动画）                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段三：解锁 & 重新编辑                                       │
│                                                             │
│ 用户点击「解锁拓扑」→ 前端恢复编辑模式                           │
│ 修改链路属性 → 再次「锁定拓扑」→ 后端重新生成脚本并重启 Mininet  │
│ 之前下发的流表在 Mininet 重启后自动清除                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心工作流

### 3.1 设计原则

采用 **"锁定/解锁"** 的双阶段交互模式：

| 阶段 | 前端状态 | 后端行为 |
|------|---------|---------|
| **编辑阶段**（🔓 未锁定） | 用户可修改链路 delay / bw / loss，可拖拽节点位置；意图输入框禁用 | 不做事 |
| **锁定阶段**（🔒 已锁定） | 链路属性编辑禁用，布局固定；意图输入框可用，可提交流意图 | 拓扑已校验、Mininet 已拉起、topology_map.json 已生成 |

**锁定/解锁机制的意义**：
- 拓扑是流规划的**前提条件**——必须先确定网络环境，才能计算路径
- 避免"编辑一半拓扑→提交意图→拓扑又变了"的竞态问题
- Mininet 脚本生成/网络拉起是重量级操作，不应每次意图执行都重复
- 解锁 → 重新锁定 = Mininet 重启 + 流表自动清理

### 3.2 阶段一：编辑 & 锁定拓扑

```
Step 1: 用户在前端修改链路属性（delay / bandwidth / loss）
    ↓ 实时更新 React Flow 边标签，所有修改本地暂存
Step 2: 用户点击「🔒 锁定拓扑」按钮
    ↓
Step 3: 前端收集当前所有节点 + 边数据 → POST /topology
    ↓
Step 4: 后端校验：
    ├─ 节点数必须为 22（0~21）
    ├─ 边集合必须与 GEANT 完全一致（仅方向允许互换）
    └─ 校验失败 → 返回 400 + 具体错误信息
    ↓
Step 5: 后端根据拓扑属性 → 生成 Mininet Python 脚本
    ├─ TCLink(delay=..., bw=..., loss=...) 设置每条链路
    ├─ 按节点 ID 升序分配端口 → 写入 topology_map.json
    └─ 输出文件：output/mn_geant.py
    ↓
Step 6: 后端拉起/更新 Mininet 网络
    ├─ 首次：sudo python output/mn_geant.py（后台运行）
    ├─ 重锁定：sudo mn -c 清理 → 重新拉起
    └─ 返回前端 { status: "locked", topology_map_summary }
    ↓
Step 7: 前端切换至锁定状态
    ├─ 所有边编辑输入框禁用（灰色）
    ├─ 按钮变为「🔓 解锁拓扑」
    ├─ 意图输入框启用
    └─ 状态栏显示 "拓扑已锁定"
```

### 3.3 阶段二：意图执行（锁定状态下）

```
前提：拓扑处于锁定状态（当前拓扑已下发到 Mininet）
    ↓
Step 1: 用户在意图输入框输入自然语言
        如 "从节点 2 到节点 5，低延迟，带宽 30Mbps"
    ↓
Step 2: 点击「▶ 执行意图」按钮
    ↓
Step 3: POST /intent 仅发送 intent_text（拓扑后端已持有）
    ↓
Step 4: 意图解析 → {src: 2, dst: 5, phi: 0.2, bw_req: 25.0}
        使用 LLM（或模拟解析函数）+ 当前锁定拓扑
    ↓
Step 5: 构建 XCHiRL 模型输入
        ├─ x [22,2]：节点 one-hot 特征
        ├─ index [2,72]：有向边 COO 索引
        ├─ features [72,3]：归一化 delay + 当前 util + 归一化 bw
        ├─ metrics [2]：phi + bw_req_norm
        └─ paths/paths_mask [K,22]：K 条候选路径
    ↓
Step 6: XCHiRL Policy 推理 → action + logits → 最佳路径节点序列
    ↓
Step 7: 利用 topology_map.json 将路径节点序列 → 每个交换机的出口端口
    ↓
Step 8: 生成 OpenFlow 流表项 → 通过 ODL RESTCONF 下发到 Mininet
    ↓
Step 9: 更新全局 utilization（在选中路径的边上增加负载）
    ↓
Step 10: 返回 {path, ports, nodes, edges, parsed_intent}
    ↓
Step 11: 前端高亮路径
    ├─ 路径上的边变色（如 #ff6b6b 红色）+ 加粗 + 动画
    └─ 路径上的节点高亮显示
```

### 3.4 阶段三：解锁 & 重新编辑

```
Step 1: 用户点击「🔓 解锁拓扑」按钮
    ↓
Step 2: 前端恢复编辑模式：
    ├─ 边属性输入框启用
    ├─ 意图输入框禁用
    ├─ 路径高亮清除
    └─ 按钮变回「🔒 锁定拓扑」
    ↓
Step 3:（后端可选）清理 Mininet 中的流表或保持网络运行
        建议：解锁时不清除 Mininet，仅在重新锁定时重启
    ↓
Step 4: 用户修改链路属性 → 再次点击「🔒 锁定拓扑」
    ↓
Step 5: 后端重新生成 Mininet 脚本 → 重启网络（旧流表自动清除）
```

### 3.5 状态转换图

```
┌──────────────┐  点击「锁定拓扑」   ┌──────────────┐
│              │ ─────────────────→ │              │
│  编辑模式    │    POST /topology   │  锁定模式     │
│  🔓 未锁定   │                    │  🔒 已锁定    │
│              │ ←───────────────── │              │
│  - 可编辑边   │  点击「解锁拓扑」    │  - 边只读     │
│  - 意图禁用   │                    │  - 意图可用   │
│  - 无路径高亮 │                    │  - 可执行意图 │
└──────────────┘                    └──────┬───────┘
                                           │
                                    ┌──────▼───────┐
                                    │  点击「执行意图」│
                                    │  POST /intent │
                                    └──────┬───────┘
                                           ▼
                                    ┌──────────────┐
                                    │  路径高亮状态  │
                                    │  (锁定模式+)  │
                                    │  - 边高亮/动画 │
                                    │  - 流信息显示  │
                                    └──────────────┘
```

### 3.6 首次运行 vs 后续运行

| 场景 | 锁定操作 | Mininet 操作 | 流表 |
|------|---------|-------------|------|
| **首次启动** | 用户编辑后锁定 | 生成脚本并拉起 | 空 |
| **重锁定（链路变更）** | 解锁→编辑→再次锁定 | `mn -c` 清理→重新拉起 | 自动清除 |
| **新增流（已锁定）** | 不操作（已锁定） | 不重启 | 仅新增下发 |
| **解锁但不重新锁定** | 解锁 | 保持运行（可选） | 保留（可选清理） |

---

## 4. 后端模块设计

### 4.1 模块划分

```
backend/
├── app.py                     # Flask/FastAPI 主入口
├── mininet_generator.py       # Mininet 脚本生成 + topology_map.json
├── model_inference.py         # XCHiRL Policy 加载与推理
├── flow_manager.py            # 流表生成 + ODL 下发
├── intent_parser.py           # 自然语言 → 结构化意图
├── topology_validator.py      # GEANT 拓扑校验
├── utils.py                   # IP 映射、端口查找等工具函数
├── config.py                  # 配置项（模型路径、ODL 地址等）
├── geant_topology.py          # GEANT 官方拓扑定义（参考）
├── requirements.txt
└── topology_map.json          # 自动生成：端口分配映射
```

### 4.2 各模块职责

#### `app.py` — 主入口

- Flask/FastAPI 应用初始化
- 路由注册：
  - `POST /topology` — 接收并校验拓扑，返回校验结果
  - `POST /intent` — 接收拓扑 + 意图 → 执行完整工作流 → 返回路径
  - `GET /status` — 返回当前网络状态（链路利用率、已下发的流）
  - `GET /api/geant-topology` — 返回标准 GEANT 拓扑供前端使用
- 全局状态：`global_utilization`（每条链路的当前利用率）

#### `mininet_generator.py` — Mininet 脚本生成

核心函数：
```python
def generate_mininet_script(topology: dict, output_path: str) -> str:
    """
    根据拓扑 JSON 生成 Mininet Python 脚本。
    使用 TCLink 设置每条链路的 delay / bw / loss。
    固定端口分配：第 1 个邻居 → port 1，第 2 个邻居 → port 2, ...
    记录 topology_map.json。
    """
```

**端口分配规则**：对每个交换机，遍历其所有邻居，按邻居节点 ID **升序**分配端口号（确保确定性），记录为 `topology_map.json`。

**`topology_map.json` 格式**：
```json
{
  "switches": {
    "0": {
      "neighbors": {
        "1": {"port": 1, "delay": 5.0, "bw": 100.0},
        "3": {"port": 2, "delay": 3.0, "bw": 80.0}
      }
    }
  },
  "edge_map": {
    "(0,1)": {"sport": 1, "dport": 1, "delay": 5.0, "bw": 100.0},
    "(1,0)": {"sport": 1, "dport": 1, "delay": 5.0, "bw": 100.0}
  }
}
```

**生成的 Mininet 脚本示例**：
```python
#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI

class GeantTopo(Topo):
    def build(self):
        # 22 个交换机
        switches = {i: self.addSwitch(f's{i}') for i in range(22)}
        # 22 个主机
        hosts = {i: self.addHost(f'h{i}', ip=f'10.0.0.{i+1}/24') for i in range(22)}
        # 链路：所有主机连接到对应交换机
        for i in range(22):
            self.addLink(hosts[i], switches[i])
        # 36 条 GEANT 链路，带 TCLink 参数
        self.addLink(switches[0], switches[1], bw=100, delay='5ms', loss=0)
        self.addLink(switches[0], switches[3], bw=80, delay='3ms', loss=0)
        # ... 其余 34 条

if __name__ == '__main__':
    topo = GeantTopo()
    net = Mininet(topo=topo, link=TCLink, controller=RemoteController)
    net.start()
    CLI(net)
    net.stop()
```

#### `model_inference.py` — XCHiRL 模型推理

核心函数：
```python
class XCHiRLInference:
    """
    封装 XCHiRL Policy 的加载与推理。
    维护全局的链路利用率状态。
    """
    
    def __init__(self, ckpt_path: str, device: str = "cpu"):
        """加载 checkpoint，初始化 Policy、拓扑索引等。"""
    
    def infer(self, src: int, dst: int, phi: float, bw_req: float) -> dict:
        """
        输入：源节点、目的节点、QoS 敏感度、带宽需求
        输出：{path: [node_ids], action: int, logits: list}
        """
    
    def update_utilization(self, path: list, bw_req: float):
        """在选中路径的每条边上减去已用带宽，更新 util。"""
    
    def get_utilization(self) -> list:
        """返回当前所有边的利用率 [E] 数组。"""
```

**内部数据流**：
```
拓扑索引 (index[2,E]) + 边特征 (features[E,3]) + 流度量 (metrics[2])
    + K 条候选路径 (paths[K,L], paths_mask[K,L])
    → Policy.forward() → action, logits
    → paths[action] → node_id 序列
```

**候选路径生成**：使用 `networkx.shortest_simple_paths()` 生成前 K 条最短路径（K=16），与训练时一致。

**边特征计算**（严格遵循模型文档）：
```python
features[:, 0] = (delay - 10.5) / 5.5           # delay_norm
features[:, 1] = 1.0 - residual_bw / capacity   # util ∈ [0,1]
features[:, 2] = (capacity - 65.0) / 20.2       # bw_norm
```

#### `flow_manager.py` — 流表管理

核心函数：
```python
def generate_flow_rules(path: list, ports: list, src_ip: str, dst_ip: str) -> list:
    """
    从节点序列 + 端口序列生成 OpenFlow 流表项列表。
    每个交换机一条流表（匹配 src_ip/dst_ip，设置 output 端口）。
    """

def install_flows_via_odl(flows: list, odl_config: dict) -> bool:
    """
    通过 ODL RESTCONF API 下发流表。
    PUT /restconf/config/opendaylight-inventory:nodes/node/{node}/...
    """

def install_flows_via_ovs(flows: list) -> bool:
    """通过 ovs-ofctl 下发流表（备选方案）。"""

def delete_all_flows(odl_config: dict) -> bool:
    """清理所有流表。"""
```

**ODL RESTCONF 流表格式**：
```xml
<input xmlns="urn:opendaylight:flow:service">
    <node>/opendaylight-inventory:nodes/node/openflow:1</node>
    <flow>
        <id>1</id>
        <match>
            <ethernet-match>
                <ethernet-type>
                    <type>2048</type>
                </ethernet-type>
            </ethernet-match>
            <ipv4-source>10.0.0.1/32</ipv4-source>
            <ipv4-destination>10.0.0.6/32</ipv4-destination>
        </match>
        <instructions>
            <instruction>
                <order>0</order>
                <apply-actions>
                    <action>
                        <order>0</order>
                        <output-action>
                            <output-node-connector>1</output-node-connector>
                        </output-action>
                    </action>
                </apply-actions>
            </instruction>
        </instructions>
    </flow>
</input>
```

#### `intent_parser.py` — 意图解析

核心函数：
```python
def parse_intent(intent_text: str, topology: dict) -> dict:
    """
    将自然语言意图解析为结构化路由需求。
    
    输入: "让节点 2 到节点 5 的流量走低延迟路径"
    输出: {
        "src": 2,
        "dst": 5,
        "phi": 0.1,         # 低 → 延迟敏感
        "bw_req": 25.0       # Mbps
    }
    
    实现方式：
        1. (推荐) 调用 LLM API（如 GPT-4 / Claude）进行结构化抽取
        2. (备选) 基于关键词的模拟解析
    """
```

**LLM Prompt 模板**：
```
你是一个 SDN 意图解析器。给定的拓扑有 22 个节点（0-21）。
从用户的自然语言描述中提取结构化信息：

用户意图: {intent_text}

返回 JSON:
{
    "src": <int, 0-21>,
    "dst": <int, 0-21>,
    "phi": <float, 0-1>,     # 0=极低延迟敏感, 1=极高带宽敏感
    "bw_req": <float>         # 带宽需求 (Mbps)
}

如果无法解析，返回 {"error": "描述信息不足"}。
```

#### `topology_validator.py` — GEANT 拓扑校验

核心函数：
```python
GEANT_EDGES = frozenset({
    (0,1), (0,3), (1,2), (1,4), (2,5), (2,22),  # ... 36 条边
})

def validate_geant_topology(topology: dict) -> tuple[bool, str]:
    """
    检查拓扑是否符合 GEANT 结构。
    
    校验规则：
    1. 节点数量必须为 22（ID 0~21）
    2. 边的集合必须与 GEANT_EDGES 完全一致
       （允许方向互换，(u,v) 等同于 (v,u)）
    3. 每条边必须包含 delay, bandwidth, loss 属性
    
    返回：(is_valid, error_message)
    """
```

#### `utils.py` — 工具函数

```python
def host_ip(node_id: int) -> str:
    """返回节点对应主机的 IP：10.0.0.{node_id+1}"""

def get_egress_port(topology_map: dict, src: int, dst: int) -> int:
    """从 topology_map.json 查找 src→dst 的出端口号"""

def path_to_ports(topology_map: dict, path: list) -> list:
    """将节点序列 [2, 1, 4, 5] 转换为端口序列 [port1, port2, ...]"""
```

#### `geant_topology.py` — GEANT 参考拓扑

定义 GEANT 的 22 个节点和 36 条无向边的完整列表，作为前端标准拓扑的源数据和后端校验的基准。

GEANT 节点名称映射（用于显示）：
```
0:  "Dublin",   1: "London",   2: "Amsterdam",  3: "Frankfurt",
4:  "Paris",    5: "Brussels", 6: "Luxembourg", 7: "Copenhagen",
8:  "Hamburg",  9: "Berlin",  10: "Vienna",    11: "Prague",
12: "Munich",  13: "Zurich",  14: "Milan",     15: "Geneva",
16: "Bordeaux", 17: "Madrid", 18: "Barcelona", 19: "Lisbon",
20: "Rome",     21: "Athens"
```

---

## 5. 前端模块设计

### 5.1 技术栈

| 技术 | 用途 |
|------|------|
| React 18 + Vite | 框架与构建 |
| React Flow (xyflow) | 拓扑画布（节点/边展示、交互） |
| Tailwind CSS / Ant Design | UI 组件与样式（可选） |
| axios | HTTP 请求 |

### 5.2 组件树

```
App
├── TopologyCanvas          # React Flow 拓扑画布（主区域）
│   ├── SwitchNode          # 自定义交换机节点（矩形）
│   ├── HostNode            # 自定义主机节点（圆形）
│   ├── GeantEdge           # 自定义边（显示 delay/bw/loss 标签）
│   └── PathHighlighter     # 路径高亮逻辑（颜色/动画）
├── PropertyPanel           # 边属性编辑侧边栏
│   ├── DelayInput          # 锁定状态下禁用
│   ├── BandwidthInput      # 锁定状态下禁用
│   └── LossInput           # 锁定状态下禁用
├── Toolbar                 # 顶部工具栏
│   ├── LockButton          # 🔒 锁定 / 🔓 解锁切换按钮
│   └── StatusIndicator     # 锁定状态指示灯
├── IntentPanel             # 意图输入与执行
│   ├── InputArea           # 自然语言输入框（锁定状态下启用）
│   └── ExecuteButton       # 执行意图按钮（锁定状态下可用）
└── StatusBar               # 网络状态/错误信息显示
```

### 5.3 组件职责

#### `TopologyCanvas.jsx`

- 使用 React Flow 渲染固定 GEANT 拓扑（22 个交换机节点 + 22 个主机节点）
- **节点布局**：预计算位置（基于 GEANT 地理坐标或预设布局），用户可拖拽调整
- **自定义节点**：
  - `SwitchNode`：矩形，深色背景，显示节点名称（如 "s0: Dublin"），支持选中
  - `HostNode`：圆形，浅色背景，显示主机名（如 "h0: 10.0.0.1"）
- **自定义边**：显示 `delay/bw/loss` 标签，点击边弹出 `PropertyPanel`
- **路径高亮**：收到后端返回的路径后，改变相关边和节点的颜色、增加动画效果

**布局策略**：由于 GEANT 拓扑固定，推荐使用**预计算坐标**直接定位节点（从 `geant_topology.py` 导出的坐标），避免自动布局算法的不确定性。首次加载时应用一次布局，之后用户可拖拽微调。

#### `PropertyPanel.jsx`

- 侧边栏组件，当用户点击一条边时显示
- 编辑字段：`delay (ms)`、`bandwidth (Mbps)`、`loss (%)`
- 每个字段有输入框和 +/- 步进按钮
- **锁定状态下所有输入框禁用**（灰色背景、只读），解锁后可编辑
- 修改即时更新 React Flow 中的边标签
- 存储拓扑数据的 state 集中管理，锁定/解锁时发往后端

#### `LockButton`（工具栏组件）

- **锁定态** 🔒：按钮显示"锁定拓扑"，点击后:
  1. 收集当前所有边属性 → POST `/topology`
  2. 收到成功响应后切换全局状态为 `locked: true`
  3. 边编辑禁用，意图输入框启用
  4. 按钮变为"解锁拓扑"
- **解锁态** 🔓：按钮显示"解锁拓扑"，点击后:
  1. 切换全局状态为 `locked: false`
  2. 边编辑恢复，意图输入框禁用
  3. 清除路径高亮
  4. 按钮变回"锁定拓扑"
- **加载态** ⏳：按钮显示加载动画，禁止重复点击

#### `IntentPanel.jsx`

- **仅在锁定状态下启用**（`locked === true` 时显示可用）
- 文本输入框：用户输入自然语言意图
- "执行意图"按钮：发送 `POST /intent`（仅携带 intent_text，拓扑后端已持有）
- 输入框 placeholder：锁定状态下显示"输入自然语言意图..."，未锁定状态下显示"请先锁定拓扑"
- 加载状态（loading spinner）
- 结果显示：
  - 成功：画布高亮路径 + 显示路径信息（节点序列、端口序列、解析结果）
  - 失败：显示错误提示

### 5.4 React Flow 实现要点

```jsx
// 核心结构
import { ReactFlow, useNodesState, useEdgesState, addEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// 节点定义（交换机）
const SwitchNode = ({ data }) => (
  <div style={{
    width: 80, height: 40,
    background: data.highlighted ? '#ff6b6b' : '#333',
    color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    borderRadius: 4, border: '2px solid #000',
    fontFamily: 'monospace', fontSize: 12
  }}>
    {data.label}
  </div>
);

// 边定义
const edgeTypes = {
  geant: GeantEdge,
};

// 路径高亮
useEffect(() => {
  if (highlightedPath) {
    setEdges(eds => eds.map(e => ({
      ...e,
      animated: highlightedPath.includes(e.id),
      style: highlightedPath.includes(e.id)
        ? { stroke: '#ff6b6b', strokeWidth: 3 }
        : { stroke: '#999', strokeWidth: 1 },
    })));
  }
}, [highlightedPath]);
```

### 5.5 状态管理

```
全局状态（顶层 App 或 Context）：
{
  // ── 拓扑数据 ──
  topology: {
    nodes: [{id, label, type, position}],
    edges: [{id, source, target, delay, bandwidth, loss}]
  },

  // ── 锁定状态 ──
  locked: false,                  // true = 锁定，false = 编辑
  topologyLockedVersion: null,    // 当前锁定拓扑的 hash/时间戳

  // ── 路径高亮 ──
  highlightedPath: {
    nodes: [id, id, ...],
    edges: [{source, target}, ...],
    ports: [port, port, ...]
  } | null,

  // ── 执行记录 ──
  flowHistory: [
    { id, intent, parsedIntent, path, ports, timestamp }
  ],

  // ── 网络状态 ──
  networkStatus: {
    utilization: [...],
    flows: [...],
    mininetRunning: false
  },

  // ── UI 状态 ──
  loading: boolean,
  error: string | null
}
```

---

## 6. XCHiRL 模型集成

### 6.1 模块位置

`backend/model_inference.py`

### 6.2 初始化流程

```python
# 启动时加载
ckpt_path = Config.XCHIRL_CKPT_PATH  # e.g., "./network-rl/best.pt"
device = "cuda" if torch.cuda.is_available() else "cpu"

inferrer = XCHiRLInference(ckpt_path, device)

# 内部执行：
# 1. torch.load(ckpt_path) → data["actor_state_dict"], data["hparams"]
# 2. 创建 Policy 实例
# 3. 加载 GEANT 拓扑（固定节点数 N=22，边数 E=72 有向边）
# 4. 构建 index [2, 72] 有向边 COO
# 5. 初始化 features [72, 3]（delay_norm, util=0, bw_norm）
```

### 6.3 推理流程

```python
def infer(self, src: int, dst: int, phi: float, bw_req: float) -> dict:
    # 1. 构建 x [22, 2]：节点 one-hot
    x = torch.zeros(22, 2)
    x[src, 0] = 1.0
    x[dst, 1] = 1.0
    
    # 2. 构建 metrics [2]：[phi, bw_req_norm]
    metrics = torch.tensor([phi, (bw_req - 65.0) / 20.2])
    
    # 3. 生成 K 条候选路径 paths [K, 22], paths_mask [K, 22]
    paths_list = list(nx.shortest_simple_paths(G, src, dst, weight=None))[:K]
    
    # 4. 更新 features 中的 util（使用 self.current_utilization）
    
    # 5. 调用 Policy
    action, logits = self.policy.forward(x, index, features, metrics, paths, paths_mask)
    
    # 6. 转换为节点序列
    path_nodes = paths[action][paths_mask[action]].tolist()
    
    # 7. 更新 utilization
    self.update_utilization(path_nodes, bw_req)
    
    return {
        "path": path_nodes,
        "action": action,
        "logits": logits.tolist(),
        "k_paths": [p.tolist() for p in paths]
    }
```

### 6.4 全局利用率维护

```python
class XCHiRLInference:
    def __init__(self, ...):
        # features[:, 1] = util，初始全 0
        self.utilization = [0.0] * E  # [72]
        
    def update_utilization(self, path: list, bw_req: float):
        """沿路径更新双向边的利用率"""
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            # 查找有向边索引
            eid_fwd = self.edge_to_idx[(u, v)]
            eid_bwd = self.edge_to_idx[(v, u)]
            capacity = self.edge_capacity[(u, v)]
            # 更新 util = 1.0 - residual_bw / capacity
            new_util = 1.0 - (capacity - bw_req) / capacity
            self.utilization[eid_fwd] = min(1.0, self.utilization[eid_fwd] + new_util)
            self.utilization[eid_bwd] = min(1.0, self.utilization[eid_bwd] + new_util)
            # 更新 features
            self.features[eid_fwd, 1] = self.utilization[eid_fwd]
            self.features[eid_bwd, 1] = self.utilization[eid_bwd]
```

---

## 7. API 接口设计

### 7.1 `POST /topology` — 锁定拓扑（校验 + 生成 Mininet）

> 前端点击「锁定拓扑」时调用。

**请求体**：
```json
{
  "nodes": [
    {"id": 0, "label": "Dublin", "type": "switch", "position": [100, 200]},
    {"id": 1, "label": "London", "type": "switch", "position": [200, 100]},
    ...
  ],
  "edges": [
    {"source": 0, "target": 1, "delay": 5.0, "bandwidth": 100.0, "loss": 0.0},
    {"source": 0, "target": 3, "delay": 3.0, "bandwidth": 80.0, "loss": 0.1},
    ...
  ]
}
```

**成功响应** `200`：
```json
{
  "status": "locked",
  "message": "Topology locked. Mininet script generated and network started.",
  "topology_version": "20260608T120000Z",
  "summary": {
    "switches": 22,
    "edges": 36,
    "mininet_script": "output/mn_geant.py",
    "topology_map": "output/topology_map.json"
  }
}
```

**失败响应** `400`：
```json
{
  "status": "invalid",
  "error": "拓扑校验失败：Edge (0, 22) 不属于 GEANT 拓扑",
  "detail": "GEANT 拓扑仅有 36 条边，请在画布上检查连接"
}
```

### 7.2 `POST /intent` — 意图执行（拓扑已锁定）

> 前提：拓扑已通过 `POST /topology` 锁定。拓扑数据后端已持有，请求体仅需要意图文本。

**请求体**：
```json
{
  "intent": "让节点 2 到节点 5 的流量走低延迟路径",
  "topology_version": "20260608T120000Z"
}
```

> `topology_version` 可选，用于后端校验前端锁定的拓扑版本是否与后端一致。

**成功响应** `200`：
```json
{
  "status": "success",
  "path": [2, 1, 3, 5],
  "ports": [3, 2, 1],
  "nodes": [
    {"id": 2, "name": "Amsterdam"},
    {"id": 1, "name": "London"},
    {"id": 3, "name": "Frankfurt"},
    {"id": 5, "name": "Brussels"}
  ],
  "edges": [
    {"source": 2, "target": 1},
    {"source": 1, "target": 3},
    {"source": 3, "target": 5}
  ],
  "parsed_intent": {
    "src": 2,
    "dst": 5,
    "phi": 0.1,
    "bw_req": 25.0
  },
  "message": "Flow rules installed successfully via ODL"
}
```

**失败响应** `400` / `409` / `500`：
```json
{
  "status": "error",
  "error": "拓扑未锁定：请先锁定拓扑后再执行意图",
  "code": "TOPOLOGY_NOT_LOCKED"
}
```

```json
{
  "status": "error",
  "error": "意图解析失败：无法提取源/目的节点",
  "detail": "用户意图描述不够明确，请补充节点信息"
}
```

### 7.3 `GET /status` — 网络状态

**响应**：
```json
{
  "utilization": [
    {"edge": [0, 1], "util": 0.25, "bw_used": 25.0, "capacity": 100.0},
    ...
  ],
  "active_flows": [
    {"id": "flow-001", "path": [2, 1, 3, 5], "status": "installed"},
    ...
  ],
  "network": {
    "mininet_running": true,
    "odl_connected": true,
    "switches": 22,
    "hosts": 22
  }
}
```

### 7.4 `GET /api/geant-topology` — 标准 GEANT 拓扑

**响应**：标准 GEANT 拓扑，包含预计算节点坐标、节点名称、默认边属性。

前端可通过此接口获取初始化数据，替代硬编码。

---

## 8. 数据模型

### 8.1 拓扑相关

```python
@dataclass
class TopologyNode:
    id: int                    # 0-21
    label: str                 # "Dublin"
    type: Literal["switch", "host"]
    position: tuple[float, float]  # 预计算 x, y 坐标

@dataclass
class TopologyEdge:
    source: int
    target: int
    delay: float               # ms
    bandwidth: float           # Mbps
    loss: float                # % (0-100)
```

### 8.2 意图相关

```python
@dataclass
class ParsedIntent:
    src: int                   # 0-21
    dst: int                   # 0-21
    phi: float                 # 0-1
    bw_req: float              # Mbps

@dataclass
class IntentResult:
    status: str                # "success" | "error"
    path: list[int]            # 节点 ID 序列
    ports: list[int]           # 出口端口序列
    edges: list[tuple[int, int]]
    parsed_intent: ParsedIntent
    message: str
```

### 8.3 流表相关

```python
@dataclass
class FlowRule:
    switch_id: int             # 交换机节点 ID
    flow_id: str               # 唯一标识
    priority: int              # 流表优先级
    match_src_ip: str          # 源 IP
    match_dst_ip: str          # 目的 IP
    output_port: int           # 出端口
    hard_timeout: int = 0      # 硬超时（0=永不过期）
    idle_timeout: int = 0      # 空闲超时
```

---

## 9. Mininet 脚本生成与端口分配

### 9.1 端口分配规则

确定性端口分配：对每个交换机，按邻居节点 ID **升序排序**，依次分配端口 1, 2, 3, ...

示例（节点 0 的邻居为 1, 3, 5）：
| 邻居 | 排序后 | 分配端口 |
|------|--------|---------|
| 1    | 1      | 1       |
| 3    | 3      | 2       |
| 5    | 5      | 3       |

### 9.2 `topology_map.json` 结构

```json
{
  "switches": {
    "0": {
      "neighbors": {
        "1": {"port": 1, "delay": 5.0, "bw": 100.0, "loss": 0.0},
        "3": {"port": 2, "delay": 3.0, "bw": 80.0, "loss": 0.1},
        "5": {"port": 3, "delay": 2.0, "bw": 90.0, "loss": 0.0}
      },
      "host_connected": true,
      "host_port": 4
    }
  },
  "edge_map": {
    "(0,1)": {"sport": 1, "dport": 1, "delay": 5.0, "bw": 100.0},
    "(1,0)": {"sport": 1, "dport": 1, "delay": 5.0, "bw": 100.0}
  },
  "hosts": {
    "0": {"switch": 0, "port": 4, "ip": "10.0.0.1"},
    "1": {"switch": 1, "port": 3, "ip": "10.0.0.2"}
  },
  "metadata": {
    "generated_at": "2026-06-08T12:00:00",
    "topology": "GEANT",
    "num_switches": 22,
    "num_edges": 36
  }
}
```

### 9.3 Mininet 脚本关键点

```python
# TCLink 参数设置
self.addLink(s1, s2,
    bw=100,                    # Mbps
    delay='5ms',               # 时延字符串
    loss=0,                    # 丢包率 %
    use_htb=True               # 使用 HTB 队列
)

# 所有交换机使用 OpenFlow 1.3
net = Mininet(topo=topo, link=TCLink,
    controller=RemoteController,
    switch=OVSSwitch,
    protocol='OpenFlow13'
)

# 清理旧网络的命令
# sudo mn -c
# sudo pkill -f "mininet"
```

---

## 10. 流表生成与下发

### 10.1 主机 IP 约定

| 节点 ID | 主机名 | IP 地址 | MAC 地址 |
|---------|--------|---------|----------|
| 0 | h0 | 10.0.0.1/24 | 00:00:00:00:00:01 |
| 1 | h1 | 10.0.0.2/24 | 00:00:00:00:00:02 |
| ... | ... | ... | ... |
| 21 | h21 | 10.0.0.22/24 | 00:00:00:00:00:16 |

### 10.2 流表匹配规则

对于路径 `[src_node, n1, n2, ..., dst_node]`：

| 交换机 | 匹配源 IP | 匹配目的 IP | 动作 |
|--------|-----------|------------|------|
| src_node | h_src_ip | h_dst_ip | output=port_to_n1 |
| n1 | h_src_ip | h_dst_ip | output=port_to_n2 |
| ... | ... | ... | ... |
| dst_node | h_src_ip | h_dst_ip | output=port_to_host_dst |

### 10.3 ODL RESTCONF 下发

```
PUT http://{ODL_HOST}:8181/restconf/config/opendaylight-inventory:nodes/node/openflow:{switch_id}/flow-node-inventory:table/0/flow/{flow_id}
Headers: Authorization: Basic YWRtaW46YWRtaW4=
Content-Type: application/xml
```

### 10.4 `ovs-ofctl` 备选方案

当 ODL 不可用时，直接使用 ovs-ofctl 在 Mininet 内下发：

```bash
ovs-ofctl add-flow s0 \
    "ip,nw_src=10.0.0.3,nw_dst=10.0.0.6,actions=output:1"
```

```python
def install_flows_via_ovs(flows: list):
    for flow in flows:
        cmd = (
            f"ovs-ofctl add-flow s{flow.switch_id} "
            f"\"ip,nw_src={flow.match_src_ip},"
            f"nw_dst={flow.match_dst_ip},"
            f"actions=output:{flow.output_port}\""
        )
        subprocess.run(cmd, shell=True, check=True)
```

---

## 11. 项目结构

```
sdn-planner/
├── README.md                      # 本架构方案文档
├── CLAUDE.md                      # 项目说明（AI 辅助开发用）

├── backend/                       # 后端服务
│   ├── app.py                     # Flask/FastAPI 主入口
│   ├── config.py                  # 全局配置（模型路径、ODL 地址等）
│   ├── requirements.txt           # Python 依赖
│   ├── geant_topology.py          # GEANT 拓扑定义（节点、边、坐标）
│   ├── topology_validator.py      # 拓扑校验器
│   ├── intent_parser.py           # 自然语言意图解析器
│   ├── model_inference.py         # XCHiRL Policy 推理封装
│   ├── mininet_generator.py       # Mininet 脚本生成器
│   ├── flow_manager.py            # 流表生成与下发
│   ├── utils.py                   # 工具函数
│   └── topology_map.json          # 端口分配映射（自动生成，不提交）

├── frontend/                      # 前端应用（React + Vite）
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                # 主应用组件
│       ├── App.css
│       ├── api/
│       │   └── client.js          # 后端 API 客户端
│       ├── components/
│       │   ├── TopologyCanvas.jsx  # React Flow 拓扑画布
│       │   ├── SwitchNode.jsx      # 交换机自定义节点
│       │   ├── HostNode.jsx        # 主机自定义节点
│       │   ├── GeantEdge.jsx       # 自定义边（带属性标签）
│       │   ├── PropertyPanel.jsx   # 链路属性编辑面板
│       │   ├── IntentPanel.jsx     # 意图输入与执行面板
│       │   └── StatusBar.jsx       # 状态栏
│       └── hooks/
│           └── useTopology.js      # 拓扑状态管理 Hook

├── network-rl/                    # XCHiRL 模型（独立子项目）
│   ├── api introduction.md        # 模型推理接口文档
│   ├── best.pt                    # 训练好的 checkpoint
│   ├── xchirl/                    # 模型包（encoders, scorers, env...）
│   ├── train/                     # 训练代码
│   ├── scripts/                   # 脚本工具
│   └── pyproject.toml

├── docker-compose.yml             # ODL 控制器容器
├── start-odl.sh                   # ODL 启动脚本
├── config.py                      # 全局配置
└── .env                           # 环境变量（ODL IP/端口）
```

---

## 12. 部署与运行

### 12.1 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.12+ |
| Node.js | 18+ |
| Mininet | 最新（WSL2 Ubuntu 24.04） |
| OpenDaylight | Carbon / Sulfur（Docker） |
| PyTorch | 2.x（与 CUDA 版本匹配） |

### 12.2 后端启动

```bash
# 1. 创建虚拟环境
cd backend
python -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
export ODL_HOST="localhost"
export ODL_PORT=8181
export ODL_USER="admin"
export ODL_PASS="admin"
export XCHIRL_CKPT="../network-rl/best.pt"
export DEVICE="cpu"  # 或 "cuda"

# 4. 启动后端
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 12.3 前端启动

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 12.4 ODL 启动

```bash
docker compose up -d
# 等待 ~60s 确保 Karaf 完全启动

# 安装 ODL 特性
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-restconf'
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-openflowplugin-flow-services-ui'
```

### 12.5 requirements.txt（参考）

```
# Web
flask>=3.0
flask-cors>=4.0

# 或 FastAPI
# fastapi>=0.109
# uvicorn[standard]>=0.27

# ML / RL
torch>=2.0
numpy>=1.24
networkx>=3.1

# ODL REST
requests>=2.31

# 意图解析（可选 LLM）
# openai>=1.0
# langchain>=0.1

# Mininet 相关（运行后端的 WSL 环境）
# 注意：Mininet 本身不在 Python 依赖中，仅在生成的脚本中 import
```

---

## 13. 端到端测试流程

### 13.1 完整测试

```bash
# ════════════════════════════════════════════
# 前置条件：启动基础设施
# ════════════════════════════════════════════

# Step 1: 启动 ODL（Docker）
cd /path/to/sdn-planner
docker compose up -d
# 等待 60s 确保 Karaf 完全启动

# Step 2: 启动后端
cd backend
source .venv/bin/activate
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Step 3: 启动前端（新终端）
cd frontend
npm run dev
# 打开浏览器 → http://localhost:5173


# ════════════════════════════════════════════
# 测试场景 1：编辑拓扑 → 锁定 → 执行意图
# ════════════════════════════════════════════

# Step 4: 画布初始显示 GEANT 拓扑（22 节点 + 36 条边）

# Step 5: 点击一条边（如节点 2 ↔ 节点 1）
#         → 右侧 PropertyPanel 显示
#         修改 delay: 5ms → 50ms（大幅增加延迟）

# Step 6: 点击「🔒 锁定拓扑」
#         → 按钮变为加载态
#         → POST /topology 发送拓扑数据
#         → 后端校验通过 → 生成 Mininet 脚本 → 拉起网络
#         → 前端切换为锁定状态（边编辑禁用）
#         → 按钮变为「🔓 解锁拓扑」
#         → 意图输入框启用

# Step 7: 在意图输入框输入
#         "从节点 2 到节点 5，低延迟，带宽 30Mbps"

# Step 8: 点击「▶ 执行意图」
#         → POST /intent {intent: "..."}
#         → 后端解析意图 → XCHiRL 推理 → 下发流表
#         → 返回路径 [2, 0, 4, 6, 5]（绕开了 Step 5 设置的高延迟链路）
#         → 前端路径高亮（红色动画边）

# Step 9: 验证流表
ovs-ofctl dump-flows s2     # 应看到 10.0.0.3→10.0.0.6 的流表

# Step 10: 连通性测试
#         mininet> h2 ping -c 3 h5


# ════════════════════════════════════════════
# 测试场景 2：解锁 → 修改拓扑 → 重新锁定
# ════════════════════════════════════════════

# Step 11: 点击「🔓 解锁拓扑」
#          → 编辑恢复 → 路径高亮清除

# Step 12: 将之前修改的链路 delay 改回 5ms
#          将另一条链路 bw 改为 1Mbps

# Step 13: 再次点击「🔒 锁定拓扑」
#          → 后端重新生成脚本 → 重启 Mininet（旧流表自动清除）

# Step 14: 执行相同的意图
#          → 路径可能不同（因为带宽限制，模型避开 1Mbps 链路）


# ════════════════════════════════════════════
# 测试场景 3：未锁定状态下尝试执行意图
# ════════════════════════════════════════════

# Step 15: 解锁 → 意图输入框置灰禁用
#          → 尝试点击执行 → 无反应或提示"请先锁定拓扑"


# ════════════════════════════════════════════
# 测试场景 4：并行多流
# ════════════════════════════════════════════

# Step 16: 锁定拓扑 → 执行第一条流（2→5）
#          → 高亮路径 → 利用率更新

# Step 17: 输入第二条意图 "从节点 0 到节点 8，高带宽"
#          → XCHiRL 在更新后的利用率上推理
#          → 第二条路径可能避开第一条流占用的链路
#          → 两条路径同时高亮显示（不同颜色）
```

### 13.2 测试场景

| 场景 | 输入 | 预期行为 |
|------|------|---------|
| 默认拓扑 | 不修改链路属性，输入意图 | 使用模型默认路径 |
| 高延迟链路 | 将某条链路的 delay 设为 100ms | 模型应避开该链路 |
| 低带宽链路 | 将某条链路的 bw 设为 1Mbps | 模型应避开（无法满足 bw_req） |
| 高丢包率 | 将某条链路的 loss 设为 50% | 模型虽不考虑 loss，但真实网络会丢包 |
| 非法拓扑 | 增删一条边 | 返回 400 错误 |
| 并行多流 | 先后输入两个不同源/目的 | 利用率更新，后续流量避开拥塞链路 |

### 13.3 调试命令

```bash
# 查看 Mininet 网络状态
sudo ovs-ofctl show s0

# 查看交换机流表
sudo ovs-ofctl dump-flows s0

# 测试连通性
sudo mn -c  # 清理
sudo python mn_geant.py  # 手动启动 Mininet

# ODL REST 调试
curl -u admin:admin http://localhost:8181/restconf/operational/network-topology:network-topology

# 查看 ODL 日志
docker logs odl-controller --tail 100
```

---

## 附录

### A. GEANT 拓扑（36 条无向边）

```
(0,1),  (0,3),  (0,5),  (1,2),  (1,4),  (2,5),  (2,8),
(2,22), (3,4),  (3,6),  (3,7),  (4,5),  (4,6),  (7,8),
(7,9),  (9,10), (9,11), (10,11), (10,12), (11,12), (11,13),
(12,14), (13,14), (13,15), (15,16), (15,17), (16,18),
(17,18), (17,19), (18,20), (20,21)
```

注：节点 22 是特殊节点（外联网关），如果模型中 N=22，则节点范围为 0~21，实际使用时应确认版本。

### B. 模型归一化常数

```python
DELAY_MU, DELAY_SIG = 10.5, 5.5    # delay z-score
BW_MU, BW_SIG = 65.0, 20.2         # bandwidth z-score
# phi ∈ [0, 1] — 不做变换
# util ∈ [0, 1] — 不做 z-score
```

### C. 端口分配示例（节点 0）

按邻居 ID 升序排序，分配连续端口：
| 邻居 ID | 排序顺序 | 端口号 |
|---------|---------|--------|
| 1 | 1st | 1 |
| 3 | 2nd | 2 |
| 5 | 3rd | 3 |

主机连接使用最大端口（端口 4）。
