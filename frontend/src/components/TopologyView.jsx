import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { fetchTopology } from '../api/client';

const SWITCH_STYLE = {
  shape: 'round-rectangle',
  width: 60,
  height: 40,
  backgroundColor: '#000',
  borderColor: '#000',
  borderWidth: 2,
  color: '#fff',
  label: 'data(label)',
  fontSize: 12,
  textValign: 'center',
  textHalign: 'center',
  fontFamily: 'monospace',
  fontWeight: 'bold',
};

const HOST_STYLE = {
  shape: 'ellipse',
  width: 36,
  height: 36,
  backgroundColor: '#fff',
  borderColor: '#000',
  borderWidth: 2,
  color: '#000',
  label: 'data(label)',
  fontSize: 10,
  textValign: 'bottom',
  textHalign: 'center',
  fontFamily: 'monospace',
};

const LINK_STYLE = {
  width: 2,
  lineColor: '#000',
  targetArrowColor: '#000',
  curveStyle: 'bezier',
};

const HIGHLIGHTED_LINK = {
  width: 4,
  lineColor: '#000',
  targetArrowColor: '#000',
  lineStyle: 'dashed',
};

export default function TopologyView({ highlightedPath }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [error, setError] = useState(null);

  // ── 初始化 Cytoscape ──
  useEffect(() => {
    if (!containerRef.current) return;

    cyRef.current = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node[type="switch"]',
          style: SWITCH_STYLE,
        },
        {
          selector: 'node[type="host"]',
          style: HOST_STYLE,
        },
        {
          selector: 'edge',
          style: LINK_STYLE,
        },
        {
          selector: 'edge.highlighted',
          style: HIGHLIGHTED_LINK,
        },
      ],
      layout: { name: 'grid', rows: 1 },
      wheelSensitivity: 0.3,
      minZoom: 0.3,
      maxZoom: 3,
    });

    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, []);

  // ── 轮询拓扑 ──
  useEffect(() => {
    let timer;

    async function poll() {
      try {
        const data = await fetchTopology();
        setError(null);
        updateGraph(data);
      } catch (err) {
        setError(err.message || 'Failed to fetch topology');
      }
      timer = setTimeout(poll, 3000);
    }

    poll();
    return () => clearTimeout(timer);
  }, []);

  // ── 高亮路径 ──
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.edges().removeClass('highlighted');
    if (highlightedPath && highlightedPath.length > 1) {
      for (let i = 0; i < highlightedPath.length - 1; i++) {
        cy.edges(`[source="${highlightedPath[i]}"][target="${highlightedPath[i + 1]}"]`)
          .union(cy.edges(`[source="${highlightedPath[i + 1]}"][target="${highlightedPath[i]}"]`))
          .addClass('highlighted');
      }
    }
  }, [highlightedPath]);

  function updateGraph(data) {
    const cy = cyRef.current;
    if (!cy) return;

    const nodes = data?.nodes ?? [];
    const links = data?.links ?? [];

    const cyNodes = nodes.map((n) => ({
      group: 'nodes',
      data: { id: n.id, label: n.name || n.id, type: n.type || 'switch' },
    }));

    const cyEdges = links.map((l, i) => ({
      group: 'edges',
      data: {
        id: `e${i}`,
        source: l.source,
        target: l.target,
        label: l.bandwidth ? `${l.bandwidth}M` : '',
      },
    }));

    cy.json({ elements: [...cyNodes, ...cyEdges] });

    // 自动布局：交换机居中，主机环绕
    const switchNodes = cy.nodes('[type="switch"]');
    const hostNodes = cy.nodes('[type="host"]');

    if (switchNodes.length === 1) {
      const s = switchNodes.first();
      s.position({ x: 300, y: 200 });
      const angleStep = (2 * Math.PI) / Math.max(hostNodes.length, 1);
      hostNodes.forEach((h, i) => {
        h.position({
          x: 300 + 160 * Math.cos(angleStep * i - Math.PI / 2),
          y: 200 + 160 * Math.sin(angleStep * i - Math.PI / 2),
        });
      });
    } else {
      cy.layout({ name: 'cose', animate: false, nodeRepulsion: 8000 }).run();
    }

    cy.fit(undefined, 40);
  }

  return (
    <div className="topology-wrapper">
      <div ref={containerRef} className="topology-canvas" />
      {error && <div className="topology-error">{error}</div>}
    </div>
  );
}
