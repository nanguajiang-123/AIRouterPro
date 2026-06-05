# CLAUDE.md — SDN Control Platform

## Project Overview

Smart SDN Control Platform: a web app where users input source/destination/scenario (natural language), a LangGraph agent parses the intent, fetches network topology from ODL, calls a **reinforcement-learning routing model** (`network-rl` / XCHiRL) to compute the optimal path, and installs flow rules into a Mininet emulated network via the OpenDaylight (ODL) controller. The React frontend polls topology state every 3 seconds and visualizes it with Cytoscape.js.

**Architecture:**
```
Browser (React) → FastAPI + LangGraph Agent → ODL REST API (8181) → Mininet (OpenFlow 6633)
                                        ↕
                          XCHiRL Policy (./network-rl/)
```

## Code Style & Conventions

- **Concise & readable** — Prefer flat structures over deep nesting. Use early returns, guard clauses, and descriptive names. No docstrings for trivial getters/setters.
- **Unified formatting** — Python: `ruff` (line-length 100). TypeScript/JS: `prettier` (single quotes, trailing commas, 100 width). All code must pass linting before commit.
- **Layered architecture** — Strict separation:
  - `backend/app/routers/` — HTTP routes (thin, no business logic)
  - `backend/app/agent/` — LangGraph nodes, tools, state (business logic)
  - `backend/app/models/` — Pydantic schemas (data contracts)
  - `frontend/src/components/` — React presentation components
  - `frontend/src/api/` — API client functions
- **Type hints required** for all Python and TypeScript function signatures.
- **No circular imports** — `models/` must not import from `agent/` or `routers/`.

## Project Structure

```
sdn-planner/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── agent/               # 🤖 LangGraph agent (nodes, tools, graph, state)
│   │   │   ├── graph.py         # LangGraph definition & compiled graph
│   │   │   ├── nodes.py         # Individual node functions (intent_parser, topology_fetcher, router_llm, flow_installer)
│   │   │   ├── tools.py         # ODL REST API client, XCHiRL model wrapper
│   │   │   └── state.py         # AgentState dataclass
│   │   ├── routers/
│   │   │   ├── topology.py      # GET /api/topology
│   │   │   └── plan.py          # POST /api/plan
│   │   └── models/
│   │       └── schemas.py       # Pydantic request/response models
│   ├── requirements.txt
│   └── Dockerfile (optional)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TopologyView.tsx
│   │   │   └── PlanForm.tsx
│   │   ├── api/
│   │   │   └── client.ts        # Axios API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── network-rl/                  # 🧠 RL routing model (XCHiRL)
│   ├── api introduction.md      # Model inference API docs (read this for integration)
│   ├── train/                   # PPO training loop
│   ├── xchirl/                  # Package: encoders, scorers, env, baselines
│   └── scripts/                 # Evaluation & analysis scripts
├── docker-compose.yml           # ODL controller container
└── .env                         # ODL controller IP & port config
```

## Key File Locations

| Concern | Path |
|---------|------|
| **LangGraph agent** | `backend/app/agent/` |
| **Routing model (XCHiRL)** | `network-rl/` |
| **Model inference API** | `network-rl/api introduction.md` |
| **ODL REST client** | `backend/app/agent/tools.py` |
| **API routes** | `backend/app/routers/` |
| **Pydantic schemas** | `backend/app/models/schemas.py` |
| **FastAPI entry** | `backend/app/main.py` |
| **Docker Compose (ODL)** | `docker-compose.yml` |
| **Environment config** | `.env` |

## Integration with XCHiRL Routing Model

The pathfinding model lives in `./network-rl/` (a standalone RL project). The agent in `backend/app/agent/` calls it via the interface documented in `network-rl/api introduction.md`.

**Quick reference for the model API:**

```python
# Policy.forward(x, index, features, metrics, paths, paths_mask) -> (action, logits)
#   x:          [N, 2]        node one-hot [is_src, is_dst]
#   index:      [2, E]        directed edge COO
#   features:   [E, 3]        edge features [delay_norm, util, bw_norm]
#   metrics:    [2]           flow metrics [phi, bw_req_norm]
#   paths:      [K, L]        candidate path node IDs
#   paths_mask: [K, L]        valid node mask
#   returns:    action (int), logits (Tensor[K])
```

For full details on normalization constants, checkpoint structure, and usage example, see `network-rl/api introduction.md`.

## Running the Platform

```bash
# 1. Start ODL controller
docker compose up -d
# Wait ~60s for Karaf to fully start

# 2. Install ODL features (one-time, persists via volume)
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-restconf'
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-openflowplugin-flow-services-ui'
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-dlux-core'
docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-dluxapps-topology'

# 3. Start backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. Start frontend
cd frontend && npm install && npm run dev

# 5. Start Mininet (separate terminal)
sudo mn --controller=remote,ip=$(hostname -I | awk '{print $1}'),port=6633 --topo=single,3 --mac

# 6. Open browser
# Frontend: http://localhost:5173
# ODL Web UI: http://<WSL2_IP>:8181/index.html (admin/admin)
```

## OpenDaylight Notes

- ODL listens on ports: REST API **8181**, OpenFlow **6633**, SSH **8101**
- Default credentials: `admin` / `admin`
- OVS in Mininet must use OpenFlow 1.3 protocol:
  ```
  ovs-vsctl set bridge s1 protocols=OpenFlow13
  ```
- RESTCONF inventory endpoint: `GET /restconf/operational/opendaylight-inventory:nodes`
- RESTCONF topology endpoint: `GET /restconf/operational/network-topology:network-topology`
- All commands must run inside WSL (Windows Subsystem for Linux) Ubuntu 24.04.
