import { useState } from 'react';
import TopologyView from './components/TopologyView';
import PlanForm from './components/PlanForm';
import './App.css';

function App() {
  const [highlightedPath, setHighlightedPath] = useState(null);

  return (
    <div className="app">
      <header className="app-header">
        <h1>SDN Controller</h1>
        <span className="status">OpenDaylight · Mininet</span>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <PlanForm onPathFound={setHighlightedPath} />
        </aside>

        <main className="main">
          <TopologyView highlightedPath={highlightedPath} />
        </main>
      </div>
    </div>
  );
}

export default App;
