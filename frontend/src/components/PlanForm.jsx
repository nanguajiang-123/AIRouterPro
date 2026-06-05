import { useState } from 'react';
import { submitPlan } from '../api/client';

export default function PlanForm({ onPathFound }) {
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [scenario, setScenario] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!source.trim() || !target.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await submitPlan({
        source: source.trim(),
        target: target.trim(),
        scenario: scenario.trim() || null,
      });
      setResult(data);

      if (data?.path && onPathFound) {
        onPathFound(data.path);
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setSource('');
    setTarget('');
    setScenario('');
    setResult(null);
    setError(null);
    if (onPathFound) onPathFound(null);
  }

  return (
    <div className="plan-form">
      <h3 className="form-title">Path Planning</h3>

      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label htmlFor="source">Source</label>
          <input
            id="source"
            type="text"
            placeholder="e.g. h1"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            required
          />
        </div>

        <div className="form-row">
          <label htmlFor="target">Target</label>
          <input
            id="target"
            type="text"
            placeholder="e.g. h3"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            required
          />
        </div>

        <div className="form-row">
          <label htmlFor="scenario">Scenario</label>
          <textarea
            id="scenario"
            rows={3}
            placeholder="e.g. Minimize delay, bandwidth >= 10 Mbps"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Planning...' : 'Plan Path'}
          </button>
          <button type="button" className="btn-secondary" onClick={handleReset}>
            Reset
          </button>
        </div>
      </form>

      {error && <div className="msg error">{error}</div>}

      {result && (
        <div className="msg success">
          <strong>Path:</strong>{' '}
          {Array.isArray(result.path) ? result.path.join(' → ') : result.path}
          {result.message && <div className="msg-detail">{result.message}</div>}
        </div>
      )}
    </div>
  );
}
