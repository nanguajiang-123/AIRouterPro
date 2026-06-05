from __future__ import annotations

from typing import Optional

import httpx
import networkx as nx

from config import settings
from app.logger import log

# ──────────────────────────────────────────────────────────────────────
#  ODL REST API 客户端
# ──────────────────────────────────────────────────────────────────────

_ODL_AUTH = (settings.odl_north_user, settings.odl_north_pass)
_ODL_BASE = settings.odl_north_base_url
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _odl_get(path: str) -> dict:
    """向 ODL 北向接口发起 GET 请求。返回反序列化后的 JSON。"""
    url = f"{_ODL_BASE}{path}"
    log.debug("ODL GET {}", url)
    try:
        with httpx.Client(auth=_ODL_AUTH, timeout=_TIMEOUT) as c:
            resp = c.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        log.warning("ODL GET {} → HTTP {}", url, e.response.status_code)
        return {}
    except httpx.RequestError as e:
        log.error("ODL request failed: {}", e)
        return {}


def _odl_put(path: str, body: dict) -> bool:
    """向 ODL 北向接口发起 PUT 请求。返回是否成功。"""
    url = f"{_ODL_BASE}{path}"
    log.debug("ODL PUT {}", url)
    try:
        with httpx.Client(auth=_ODL_AUTH, timeout=_TIMEOUT) as c:
            resp = c.put(url, json=body)
            resp.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        log.warning("ODL PUT {} → HTTP {}", url, e.response.status_code)
        return False
    except httpx.RequestError as e:
        log.error("ODL PUT request failed: {}", e)
        return False


def fetch_inventory() -> dict:
    """获取 ODL 已知的所有节点（交换机）。"""
    return _odl_get("/restconf/operational/opendaylight-inventory:nodes")


def fetch_topology() -> dict:
    """获取 ODL 的网络拓扑数据。"""
    return _odl_get("/restconf/operational/network-topology:network-topology")


def to_graph(nodes_data: dict, topo_data: dict) -> nx.Graph:
    """将 ODL inventory + topology 转为 networkx 无向图。"""
    g = nx.Graph()

    # 节点：从 inventory 中取交换机
    switches = nodes_data.get("nodes", {}).get("node", [])
    for sw in switches:
        nid = sw["id"]
        g.add_node(nid, type="switch")
        # 端口作为边端点
        for conn in sw.get("node-connector", []):
            pid = conn["id"]
            g.add_node(pid, type="port")
            g.add_edge(nid, pid, weight=1)

    # 链路：从 topology 中取连接
    topologies = topo_data.get("network-topology", {}).get("topology", [])
    for topo in topologies:
        for node in topo.get("node", []):
            node_id = node.get("node-id", "")
            tps = node.get("termination-point", [])
            for tp in tps:
                tp_id = tp.get("tp-id", "")
                g.add_edge(node_id, tp_id, weight=1)

    return g


def to_frontend_topology(nodes_data: dict, topo_data: dict) -> dict:
    """聚合 inventory + topology 为前端所需的 {nodes, links} 格式。"""
    nodes: list[dict] = []
    links: list[dict] = []
    seen_nodes: set = set()

    # 交换机节点
    switches = nodes_data.get("nodes", {}).get("node", [])
    for sw in switches:
        nid = sw["id"]
        nodes.append({"id": nid, "name": nid, "type": "switch"})
        seen_nodes.add(nid)

    # 拓扑中的节点（可能包含主机信息）
    topologies = topo_data.get("network-topology", {}).get("topology", [])
    for topo in topologies:
        for node in topo.get("node", []):
            node_id = node.get("node-id", "")
            if node_id not in seen_nodes:
                label = node_id.split(":")[-1] if ":" in node_id else node_id
                nodes.append({"id": node_id, "name": label, "type": "host"})
                seen_nodes.add(node_id)

    # 拓扑中的边
    for topo in topologies:
        for node in topo.get("node", []):
            nid = node.get("node-id", "")
            for tp in node.get("termination-point", []):
                tpid = tp.get("tp-id", "")
                # 尝试从主机 → 交换机方向建立连接
                links.append({"source": nid, "target": tpid})

    return {"nodes": nodes, "links": links}


# ──────────────────────────────────────────────────────────────────────
#  XCHiRL 寻路模型包装器
# ──────────────────────────────────────────────────────────────────────

# 归一化常量（与 network-rl/api introduction.md 保持一致）
DELAY_MU, DELAY_SIG = 10.5, 5.5
BW_MU, BW_SIG = 65.0, 20.2


class RoutingModel:
    """XCHiRL 路由策略模型包装器。加载 .pt 后直接调 forward() 选路径。"""

    def __init__(self):
        self._policy = None  # Policy 实例，加载后赋值

    def is_loaded(self) -> bool:
        return self._policy is not None

    def load(self, ckpt_path: str) -> None:
        """加载 .pt checkpoint，构造并初始化 Policy 对象。"""
        try:
            import torch
            from xchirl.utils.make_component_ppo import make_encoder
            from xchirl.modules.encoders import PathPooler
            from xchirl.modules.scorers import KPathScorer

            data = torch.load(ckpt_path, weights_only=False, map_location="cpu")
            hp = data.get("hparams", {})

            hidden_dim = hp.get("hidden_dim", 256)
            layer_num = hp.get("layer_num", 4)
            kind = hp.get("encoder_kind", "film_gnn")
            heads = hp.get("heads", 1)

            encoder = make_encoder(hidden_dim, layer_num, kind=kind, heads=heads)
            pooler = PathPooler(hidden_dim=hidden_dim)
            scorer = KPathScorer(hidden_dim=hidden_dim)

            sd = data["actor_state_dict"]
            encoder.load_state_dict(sd, strict=False)
            pooler.load_state_dict(sd, strict=False)
            scorer.load_state_dict(sd, strict=False)

            encoder.eval()
            pooler.eval()
            scorer.eval()

            self._policy = _Policy(encoder, pooler, scorer)
            log.info("XCHiRL model loaded (dim={}, kind={}, layers={})",
                     hidden_dim, kind, layer_num)
        except Exception as e:
            log.warning("Failed to load XCHiRL model: {}, fallback to shortest-path", e)

    def select_path(
        self, graph: nx.Graph, src: str, dst: str, k: int = 16
    ) -> list[str]:
        if self.is_loaded():
            return self._rl_select(graph, src, dst, k)
        return self._fallback_shortest(graph, src, dst)

    # ── private ─────────────────────────────────────────────────────

    @staticmethod
    def _fallback_shortest(graph: nx.Graph, src: str, dst: str) -> list[str]:
        try:
            path = nx.shortest_path(graph, source=src, target=dst)
            log.info("Fallback shortest path: {} → ... → {} ({} hops)", src, dst, len(path))
            return path
        except nx.NetworkXNoPath:
            log.warning("No path between {} and {}", src, dst)
            return []

    def _rl_select(self, graph: nx.Graph, src: str, dst: str, k: int) -> list[str]:
        """使用 RL 模型选择最优路径。"""
        import torch
        import networkx as _nx

        log.info("RL select path: {} → {} (k={})", src, dst, k)

        # 1. 构建有向边索引 [2, E]
        edge_list = list(graph.edges())
        if not edge_list:
            return self._fallback_shortest(graph, src, dst)
        E = len(edge_list)
        # 每条无向边拆两条有向边
        index_list = []
        for u, v in edge_list:
            index_list.append((u, v))
            index_list.append((v, u))
        index = torch.tensor(index_list, dtype=torch.long).t().contiguous()  # [2, 2E]

        # 2. 边特征 [2E, 3]
        features = torch.zeros(2 * E, 3)
        for i, (u, v) in enumerate(edge_list):
            d = float(graph[u][v].get("delay", 10))
            bw = float(graph[u][v].get("bandwidth", 100))
            for offset in (i, i + E):
                features[offset, 0] = (d - DELAY_MU) / DELAY_SIG
                features[offset, 1] = 0.0  # util（初始 0）
                features[offset, 2] = (bw - BW_MU) / BW_SIG

        # 3. 节点 & 节点特征
        node_list = sorted(graph.nodes())
        node_to_idx = {n: i for i, n in enumerate(node_list)}
        N = len(node_list)
        x = torch.zeros(N, 2)
        x[node_to_idx.get(src, 0), 0] = 1.0
        x[node_to_idx.get(dst, min(1, N - 1)), 1] = 1.0

        # 4. 流度量 [2]（phi 后续会从 intent_constraints 传入）
        metrics = torch.tensor([0.5, (25.0 - BW_MU) / BW_SIG])

        # 5. K 候选路径
        try:
            path_list = list(_nx.shortest_simple_paths(graph, src, dst, weight=None))[:k]
        except (_nx.NetworkXNoPath, _nx.NodeNotFound):
            return self._fallback_shortest(graph, src, dst)
        if not path_list:
            return self._fallback_shortest(graph, src, dst)

        L = N
        K = len(path_list)
        paths = torch.full((K, L), -1, dtype=torch.long)
        mask = torch.zeros(K, L, dtype=torch.bool)
        for ki, p in enumerate(path_list):
            idxs = [node_to_idx[n] for n in p]
            paths[ki, :len(idxs)] = torch.tensor(idxs)
            mask[ki, :len(idxs)] = True

        # 6. 推理
        action, logits = self._policy.forward(x, index, features, metrics, paths, mask)
        selected = path_list[action]
        log.info("RL selected path #{}: {} ({} hops)", action, selected, len(selected))
        return list(selected)


class _Policy:
    """迷你推理策略（对应 api introduction.md 的 Policy 类）。"""

    def __init__(self, encoder, pooler, scorer):
        self.encoder = encoder
        self.pooler = pooler
        self.scorer = scorer

    def forward(self, x, index, features, metrics, paths, paths_mask):
        import torch

        with torch.no_grad():
            h = self.encoder(x, index, features, metrics)
            h = self.pooler(h, paths, paths_mask)
            logits = self.scorer(h, metrics)
            return int(logits.argmax(dim=-1).item()), logits


_routing_model: Optional[RoutingModel] = None


def get_routing_model() -> RoutingModel:
    global _routing_model
    if _routing_model is None:
        _routing_model = RoutingModel()
        if settings.xchirl_model_abs_path:
            _routing_model.load(settings.xchirl_model_abs_path)
    return _routing_model


# ──────────────────────────────────────────────────────────────────────
#  ODL 流表下发
# ──────────────────────────────────────────────────────────────────────


def install_flows(path: list[str]) -> bool:
    """在 ODL 上沿路径安装流表项。（待实际实现）"""
    if not path or len(path) < 2:
        log.warning("Cannot install flows: invalid path")
        return False

    log.info("Installing flows along: {} → ... → {}", path[0], path[-1])
    # TODO: 构造 FlowNodeInventory 并 PUT 到 ODL
    # 当前为占位实现
    return True
