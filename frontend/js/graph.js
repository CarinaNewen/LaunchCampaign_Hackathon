// ── Swarm Idea Graph ───────────────────────────────────────────────────────

let swarmGraphCancelled = false;
let swarmGraphController = null;

const GRAPH_AGENT_LABELS = {
  trend_scout: 'Trend Analysis',
  audience_psychologist: 'Audience Strategy',
  creator_fit: 'Creator Alignment',
  hook_smith: 'Hook Optimization',
  format_composer: 'Format Planning',
  critic_mutator: 'Quality Review',
};

function setSwarmGraphExpanded(expanded) {
  const wrap      = document.querySelector('.swarm-graph-wrap');
  const toggleBtn = document.getElementById('swarmGraphToggle');
  const modalBox  = document.getElementById('outputModalBox');
  const dashboard = document.getElementById('swarmDashboard');
  if (!wrap || !toggleBtn || !modalBox || !dashboard) return;

  wrap.classList.toggle('expanded', expanded);
  modalBox.classList.toggle('graph-expanded', expanded);
  dashboard.classList.toggle('graph-expanded', expanded);
  toggleBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  toggleBtn.textContent = expanded ? 'Collapse' : 'Expand';
  toggleBtn.title = expanded ? 'Collapse graph' : 'Expand graph';

  requestAnimationFrame(() => {
    if (swarmGraphController && typeof swarmGraphController.redraw === 'function') {
      swarmGraphController.redraw();
    }
  });
}

function stopSwarmGraph() {
  swarmGraphCancelled = true;
  if (swarmGraphController && typeof swarmGraphController.destroy === 'function') {
    swarmGraphController.destroy();
  }
  swarmGraphController = null;
}

function runSwarmGraph(run, opts) {
  stopSwarmGraph();

  const onReveal = (opts && opts.onReveal) || function() {};
  const instant = !!(opts && opts.instant);
  const container = document.getElementById('swarmGraph');
  const ideas      = run.ideas        || [];
  const lineageData = run.lineage     || {};
  const events     = run.event_history || [];

  if (!ideas.length) return;
  if (typeof window.cytoscape !== 'function') {
    showGraphUnavailable('Graph unavailable: Cytoscape failed to load.');
    return;
  }

  const AGENT_COLORS = {
    trend_scout:           '#60a5fa',
    audience_psychologist: '#22c55e',
    creator_fit:           '#14b8a6',
    hook_smith:            '#f97316',
    format_composer:       '#a855f7',
    critic_mutator:        '#eab308',
  };
  const DEFAULT_COLOR = '#9fb0c3';

  function buildNodeLabel(idea) {
    const roundNumber = Number(idea.round_created) || 0;
    const roundLabel = roundNumber > 0 ? `R${roundNumber}` : 'R?';
    const agentLabel = GRAPH_AGENT_LABELS[idea.source_agent] || 'Swarm Node';
    return `${roundLabel} ${agentLabel}`.slice(0, 28);
  }

  const children = new Set(Object.keys(lineageData || {}));
  const rootId   = ideas.find((i) => !children.has(i.idea_id))?.idea_id || null;
  const endIds   = new Set(
    (run.final_output && run.final_output.content_concepts || []).slice(0, 3).map((c) => c.idea_id)
  );

  const cyNodes = ideas.map((idea) => {
    const isStart = idea.idea_id === rootId;
    const isEnd   = endIds.has(idea.idea_id);
    const color   = AGENT_COLORS[idea.source_agent] || DEFAULT_COLOR;
    return {
      data: {
        id:          idea.idea_id,
        label:       buildNodeLabel(idea),
        agent:       idea.source_agent || '',
        round:       idea.round_created || 0,
        color,
        isStart,
        isEnd,
        borderColor: isStart ? '#22c55e' : (isEnd ? '#eab308' : color),
        borderWidth: (isStart || isEnd) ? 3 : 0,
      }
    };
  });

  const cyEdges = [];
  Object.entries(lineageData).forEach(([childId, parents]) => {
    (parents || []).forEach((pid) => {
      cyEdges.push({ data: { id: `${pid}->${childId}`, source: pid, target: childId } });
    });
  });

  const eventOrder = [];
  events.forEach((ev, idx) => {
    (ev.idea_ids || []).forEach((id) => eventOrder.push({ eventIndex: idx, ideaId: id }));
  });
  const revealByEvent = [];
  for (let i = 0; i <= events.length; i++) {
    revealByEvent.push(new Set(eventOrder.filter((o) => o.eventIndex < i).map((o) => o.ideaId)));
  }

  let cy;
  try {
    cy = window.cytoscape({
      container,
      elements: [],
      style: [
        {
          selector: 'node',
          style: {
            'background-color':   'data(color)',
            'label':              'data(label)',
            'color':              '#e6edf6',
            'text-valign':        'bottom',
            'text-halign':        'center',
            'font-size':          '11px',
            'font-family':        'ui-sans-serif, system-ui, sans-serif',
            'text-margin-y':      8,
            'width':              28,
            'height':             28,
            'border-width':       'data(borderWidth)',
            'border-color':       'data(borderColor)',
            'text-outline-color': '#0b0f14',
            'text-outline-width': 2,
          }
        },
        { selector: 'node[?isStart]', style: { 'background-color': '#22c55e' } },
        { selector: 'node[?isEnd]',   style: { 'background-color': '#eab308' } },
        {
          selector: 'edge',
          style: {
            'width':               2,
            'line-color':          'rgba(96, 165, 250, 0.5)',
            'target-arrow-color':  'rgba(96, 165, 250, 0.7)',
            'target-arrow-shape':  'triangle',
            'curve-style':         'bezier',
            'arrow-scale':         0.8,
          }
        }
      ],
      layout: { name: 'preset' },
      userZoomingEnabled:  true,
      userPanningEnabled:  true,
      boxSelectionEnabled: false,
    });
  } catch (error) {
    showGraphUnavailable(`Graph unavailable: ${error && error.message ? error.message : 'failed to initialize.'}`);
    return;
  }

  let revealIndex   = 0;
  let rafId         = null;
  let animStart     = 0;
  const revealInterval = instant ? 0 : 520;
  let revealedNodes = new Set();
  let revealedEdges = new Set();

  function updateGraph(upToEventIndex) {
    const visibleIds = revealByEvent[Math.min(upToEventIndex, revealByEvent.length - 1)];

    cyNodes.forEach((node) => {
      if (visibleIds.has(node.data.id) && !revealedNodes.has(node.data.id)) {
        cy.add(node);
        revealedNodes.add(node.data.id);
      }
    });

    cyEdges.forEach((edge) => {
      const edgeId = edge.data.id;
      if (!revealedEdges.has(edgeId) &&
          revealedNodes.has(edge.data.source) &&
          revealedNodes.has(edge.data.target)) {
        cy.add(edge);
        revealedEdges.add(edgeId);
      }
    });

    if (revealedNodes.size > 0) {
      try {
        cy.layout({
          name: 'dagre',
          rankDir: 'TB',
          nodeSep: 60,
          rankSep: 80,
          edgeSep: 20,
          animate: true,
          animationDuration: 300,
          fit: true,
          padding: 40,
        }).run();
      } catch (error) {
        // Layout plugin failed/missing. Keep graph stable and non-fatal.
        showGraphUnavailable(
          `Graph layout unavailable: ${error && error.message ? error.message : 'dagre layout failed.'}`
        );
      }
    }
  }

  function tick(t) {
    if (swarmGraphCancelled) return;
    if (!animStart) animStart = t;
    const elapsed    = t - animStart;
    const nextReveal = Math.floor(elapsed / revealInterval) + 1;
    if (nextReveal > revealIndex && revealIndex < revealByEvent.length) {
      revealIndex = nextReveal;
      updateGraph(revealIndex);
    }
    onReveal(revealIndex);
    if (revealIndex < revealByEvent.length - 1 || elapsed < 8000) {
      rafId = requestAnimationFrame(tick);
    }
  }

  function handleResize() { cy.resize(); cy.fit(40); }

  swarmGraphCancelled = false;
  updateGraph(0);
  window.addEventListener('resize', handleResize);

  swarmGraphController = {
    redraw()  { cy.resize(); cy.fit(40); },
    destroy() {
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      window.removeEventListener('resize', handleResize);
      cy.destroy();
    },
  };

  if (instant) {
    const finalIndex = Math.max(0, revealByEvent.length - 1);
    updateGraph(finalIndex);
    onReveal(finalIndex);
    return;
  }

  rafId = requestAnimationFrame(tick);
}

function showGraphUnavailable(message) {
  const container = document.getElementById('swarmGraph');
  if (!container) return;
  container.innerHTML = '';
  const note = document.createElement('div');
  note.className = 'swarm-graph-unavailable';
  note.textContent = message;
  container.appendChild(note);
}

// Graph expand/collapse toggle
document.getElementById('swarmGraphToggle').addEventListener('click', () => {
  const wrap = document.querySelector('.swarm-graph-wrap');
  const isExpanded = !!(wrap && wrap.classList.contains('expanded'));
  setSwarmGraphExpanded(!isExpanded);
});
