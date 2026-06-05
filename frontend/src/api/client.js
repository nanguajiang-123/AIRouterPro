import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

/** GET /api/topology — 当前网络拓扑 */
export async function fetchTopology() {
  const { data } = await api.get('/topology');
  return data;
}

/** POST /api/plan — 提交路径规划请求 */
export async function submitPlan({ source, target, scenario }) {
  const { data } = await api.post('/plan', { source, target, scenario });
  return data;
}

export default api;
