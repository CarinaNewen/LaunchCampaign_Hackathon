// ── API + Modal wiring ─────────────────────────────────────────────────────

let lastRun = null;
let activeRunId = null;
let runPollTimer = null;
let runPollToken = 0;
let lastRenderedRunKey = '';

function getApiBase() {
  const configuredBase = window.localStorage.getItem('SWARM_API_BASE');
  const pageOrigin = (window.location && window.location.origin && window.location.origin !== 'null')
    ? window.location.origin : '';
  return configuredBase
    ? configuredBase
    : pageOrigin || 'http://127.0.0.1:8000';
}

function openLoading(runId) {
  activeRunId = runId || null;

  const dashboard = document.getElementById('swarmDashboard');
  const loading   = document.getElementById('outputLoading');
  const fallback  = document.getElementById('outputYamlFallback');
  const body      = document.getElementById('outputModalBody');
  const modalBox  = document.getElementById('outputModalBox');

  stopSwarmGraph();
  setSwarmGraphExpanded(false);

  if (dashboard) dashboard.style.display = 'none';
  if (loading) loading.style.display = '';
  if (fallback) fallback.style.display = 'none';
  if (body) body.classList.remove('pre-only');
  if (modalBox) modalBox.classList.remove('has-dashboard');

  resetKillButtons();
  setKillControlsVisible(!!activeRunId);

  document.getElementById('outputModal').classList.add('open');
}

function clearRunPolling() {
  if (runPollTimer) {
    clearTimeout(runPollTimer);
    runPollTimer = null;
  }
}

function setSubmitButtonLoading(isLoading) {
  const submitBtn = document.querySelector('.btn-submit');
  if (!submitBtn) return;
  if (!submitBtn.getAttribute('data-label')) {
    submitBtn.setAttribute('data-label', submitBtn.textContent);
  }
  if (isLoading) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Generating…';
    return;
  }
  submitBtn.disabled = false;
  submitBtn.textContent = submitBtn.getAttribute('data-label') || 'Generate Brief →';
}

function setShowStrategyReady(isReady) {
  const showBtn = document.getElementById('showStrategyBtn');
  if (!showBtn) return;
  showBtn.disabled = !isReady;
  showBtn.classList.toggle('ready', !!isReady);
}

function setKillControlsVisible(isVisible) {
  const controls = document.getElementById('swarmAgentControls');
  if (!controls) return;
  controls.classList.toggle('is-hidden', !isVisible);
}

function openLiveDashboard(run) {
  const dashboard = document.getElementById('swarmDashboard');
  const loading   = document.getElementById('outputLoading');
  const fallback  = document.getElementById('outputYamlFallback');
  const body      = document.getElementById('outputModalBody');
  const modalBox  = document.getElementById('outputModalBox');

  stopSwarmGraph();
  setSwarmGraphExpanded(false);

  if (loading) loading.style.display = 'none';
  if (dashboard) dashboard.style.display = '';
  if (fallback) fallback.style.display = 'none';
  if (body) body.classList.remove('pre-only');
  if (modalBox) modalBox.classList.add('has-dashboard');
  resetKillButtons();
  setKillControlsVisible(!!activeRunId);
  setShowStrategyReady(false);
  renderLiveRun(run);
  document.getElementById('outputModal').classList.add('open');
}

function renderLiveRun(run) {
  const events = Array.isArray(run && run.event_history) ? run.event_history : [];
  const ideas  = Array.isArray(run && run.ideas) ? run.ideas : [];
  const runKey = `${run && run.run_id ? run.run_id : 'unknown'}:${events.length}:${ideas.length}`;
  const shouldRerenderGraph = runKey !== lastRenderedRunKey;

  renderSwarmFeed(run || {});
  renderMetrics(run || {});

  if (shouldRerenderGraph) {
    runSwarmGraph(run || {}, {
      instant: true,
      onReveal(revealIndex) {
        updateFeedReveal(revealIndex);
      },
    });
    lastRenderedRunKey = runKey;
  } else {
    updateFeedReveal(events.length - 1);
  }
}

function scheduleRunPolling(runId, apiBase, token, startedAtMs) {
  const POLL_INTERVAL_MS = 650;
  const POLL_TIMEOUT_MS = 120000;

  runPollTimer = setTimeout(async () => {
    if (token !== runPollToken) return;
    if (Date.now() - startedAtMs > POLL_TIMEOUT_MS) {
      activeRunId = null;
      setKillControlsVisible(false);
      openError(new Error('Run timed out while waiting for live updates.'));
      setSubmitButtonLoading(false);
      return;
    }
    try {
      const getUrl = new URL(`/swarm/run/${runId}`, apiBase).toString();
      const res = await fetch(getUrl);
      if (!res.ok) {
        throw new Error(`Polling failed (${res.status}).`);
      }
      const run = await res.json();
      renderLiveRun(run);

      if (run.final_output) {
        lastRun = run;
        activeRunId = null;
        setKillControlsVisible(false);
        setShowStrategyReady(true);
        clearRunPolling();
        return;
      }
    } catch (error) {
      // Keep polling unless a newer run replaced this token.
      if (token !== runPollToken) return;
    }

    if (token === runPollToken) {
      scheduleRunPolling(runId, apiBase, token, startedAtMs);
    }
  }, POLL_INTERVAL_MS);
}

function resetKillButtons() {
  document.querySelectorAll('.agent-kill-btn').forEach((btn) => {
    btn.disabled = false;
    btn.classList.remove('killed');
    btn.textContent = btn.getAttribute('data-label') || btn.textContent;
  });
  // Cache original labels on first call
  document.querySelectorAll('.agent-kill-btn').forEach((btn) => {
    if (!btn.getAttribute('data-label')) {
      btn.setAttribute('data-label', btn.textContent);
    }
  });
}

document.getElementById('killRandomBtn').addEventListener('click', () => {
  const alive = Array.from(document.querySelectorAll('.agent-kill-btn[data-agent]')).filter(
    (b) => !b.classList.contains('killed') && !b.disabled
  );
  if (!alive.length || !activeRunId) return;
  const pick = alive[Math.floor(Math.random() * alive.length)];
  pick.click();
});

document.querySelectorAll('.agent-kill-btn[data-agent]').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const agentName = btn.getAttribute('data-agent');
    if (!agentName || !activeRunId || btn.disabled) return;

    btn.disabled = true;
    btn.textContent = 'Stopping…';

    try {
      const url = new URL(`/swarm/run/${activeRunId}/kill/${agentName}`, getApiBase()).toString();
      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        btn.classList.add('killed');
        btn.textContent = btn.getAttribute('data-label') + ' — stopped';
      } else {
        btn.disabled = false;
        btn.textContent = btn.getAttribute('data-label') || agentName;
      }
    } catch (_) {
      btn.disabled = false;
      btn.textContent = btn.getAttribute('data-label') || agentName;
    }
  });
});

document.getElementById('strategyForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  setSubmitButtonLoading(true);

  try {
    clearRunPolling();
    runPollToken += 1;
    const token = runPollToken;
    lastRenderedRunKey = '';
    lastRun = null;
    const payload = buildSwarmPayload();
    const apiBase = getApiBase();

    // Step 1: create the run immediately to get a run_id for kill buttons
    const startUrl = new URL('/swarm/start', apiBase).toString();
    const startRes = await fetch(startUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!startRes.ok) {
      const errorText = await startRes.text();
      throw new Error(`Start failed (${startRes.status}): ${errorText}`);
    }
    const startedRun = await startRes.json();
    activeRunId = startedRun.run_id;
    openLiveDashboard(startedRun);

    // Step 2: execute rounds in the background while we poll live state.
    const runUrl = new URL(`/swarm/run/${startedRun.run_id}`, apiBase).toString();
    const executionPromise = fetch(runUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    executionPromise
      .then(async (response) => {
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Request failed (${response.status}): ${errorText}`);
        }
        return response.json();
      })
      .then((run) => {
        if (token !== runPollToken) return;
        lastRun = run;
        renderLiveRun(run);
        setShowStrategyReady(true);
        activeRunId = null;
        setKillControlsVisible(false);
        clearRunPolling();
        setSubmitButtonLoading(false);
      })
      .catch((error) => {
        if (token !== runPollToken) return;
        clearRunPolling();
        activeRunId = null;
        setKillControlsVisible(false);
        openError(error);
        setSubmitButtonLoading(false);
      });

    scheduleRunPolling(startedRun.run_id, apiBase, token, Date.now());

  } catch (err) {
    lastRun = null;
    activeRunId = null;
    setKillControlsVisible(false);
    clearRunPolling();
    openError(err);
    setSubmitButtonLoading(false);
  }
});

function openDashboard(run) {
  const dashboard = document.getElementById('swarmDashboard');
  const loading   = document.getElementById('outputLoading');
  const fallback  = document.getElementById('outputYamlFallback');
  const body      = document.getElementById('outputModalBody');
  const modalBox  = document.getElementById('outputModalBox');
  const showBtn   = document.getElementById('showStrategyBtn');

  loading.style.display   = 'none';
  dashboard.style.display = '';
  fallback.style.display  = 'none';
  body.classList.remove('pre-only');
  modalBox.classList.add('has-dashboard');
  setSwarmGraphExpanded(false);

  // Reset strategy button state
  showBtn.disabled = true;
  showBtn.classList.remove('ready');
  setKillControlsVisible(!!activeRunId);

  renderSwarmFeed(run);
  renderMetrics(run);

  const eventCount = (run.event_history || []).length;

  // No animation needed — enable immediately
  if (eventCount === 0) {
    showBtn.disabled = false;
    showBtn.classList.add('ready');
  }

  runSwarmGraph(run, {
    onReveal(revealIndex) {
      updateFeedReveal(revealIndex);
      // Animation finished — enable Show Strategy
      if (eventCount > 0 && revealIndex >= eventCount - 1) {
        showBtn.disabled = false;
        showBtn.classList.add('ready');
      }
    },
  });

  document.getElementById('outputModal').classList.add('open');
}

function openError(err) {
  const dashboard = document.getElementById('swarmDashboard');
  const loading   = document.getElementById('outputLoading');
  const fallback  = document.getElementById('outputYamlFallback');
  const body      = document.getElementById('outputModalBody');
  const modalBox  = document.getElementById('outputModalBox');

  loading.style.display   = 'none';
  dashboard.style.display = 'none';
  fallback.style.display  = '';
  fallback.textContent    = `Could not generate output.\n\n${err.message || err}`;
  body.classList.add('pre-only');
  modalBox.classList.remove('has-dashboard');
  clearRunPolling();
  setShowStrategyReady(false);
  setKillControlsVisible(false);
  setSwarmGraphExpanded(false);

  document.getElementById('outputModal').classList.add('open');
}

function renderMetrics(run) {
  const coverageEl       = document.getElementById('metricCoverage');
  const consensusEl      = document.getElementById('metricConsensus');
  const contradictionsEl = document.getElementById('metricContradictions');
  const eventsPerMinEl   = document.getElementById('metricEventsPerMin');
  if (!coverageEl || !consensusEl || !contradictionsEl || !eventsPerMinEl) return;

  const events = Array.isArray(run.event_history) ? run.event_history : [];
  const totalAgents = Object.keys(run.agent_statuses || {}).length;
  const activeAgents = new Set(events.map((ev) => ev.agent_name).filter(Boolean)).size;
  const coverage = totalAgents > 0 ? Math.round((activeAgents / totalAgents) * 100) : 0;
  const contradictions = events.filter((ev) => ev.action_type === 'critique').length;
  const consensus = Math.max(0, Math.min(100, 100 - contradictions * 10));
  const eventsPerMinute = getEventsPerMinute(events);

  coverageEl.textContent = `${coverage}%`;
  consensusEl.textContent = `${consensus}%`;
  contradictionsEl.textContent = String(contradictions);
  eventsPerMinEl.textContent = formatEventsPerMinute(eventsPerMinute);
}

function getEventsPerMinute(events) {
  if (!events.length) return 0;
  const timestamps = events
    .map((ev) => Date.parse(ev.created_at || ''))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b);

  if (timestamps.length < 2) return events.length;

  const elapsedMs = timestamps[timestamps.length - 1] - timestamps[0];
  if (elapsedMs <= 0) return events.length;
  return (events.length / elapsedMs) * 60000;
}

function formatEventsPerMinute(value) {
  if (!Number.isFinite(value) || value <= 0) return '0';
  if (value >= 100) return String(Math.round(value));
  return value.toFixed(1).replace(/\.0$/, '');
}

// ── Modal close ────────────────────────────────────────────────────────────
document.getElementById('closeModal').addEventListener('click', closeModal);
document.getElementById('outputModal').addEventListener('click', (e) => {
  if (e.target === document.getElementById('outputModal')) closeModal();
});

function closeModal() {
  runPollToken += 1;
  clearRunPolling();
  activeRunId = null;
  setKillControlsVisible(false);
  stopSwarmGraph();
  setSwarmGraphExpanded(false);
  document.getElementById('outputModal').classList.remove('open');
}

// ── Show Strategy button ────────────────────────────────────────────────────
document.getElementById('showStrategyBtn').addEventListener('click', () => {
  if (lastRun) openStrategyOverlay(lastRun);
});

// ── Generate Video (modal footer) ──────────────────────────────────────────
document.getElementById('generateVideoModalBtn').addEventListener('click', () => {
  // TODO: implement video generation
});

// ── Strategy overlay close ────────────────────────────────────────────────
document.getElementById('closeStrategy').addEventListener('click', closeStrategyOverlay);
document.getElementById('strategyOverlay').addEventListener('click', (e) => {
  if (e.target === document.getElementById('strategyOverlay')) closeStrategyOverlay();
});

function closeStrategyOverlay() {
  document.getElementById('strategyOverlay').classList.remove('open');
}

// ── Generate Video (strategy overlay) ────────────────────────────────────
document.getElementById('generateVideoBtn').addEventListener('click', () => {
  // TODO: implement video generation
});

// ── Copy (strategy overlay) ───────────────────────────────────────────────
document.getElementById('copyStrategyBtn').addEventListener('click', () => {
  const text = lastRun ? getOutputText(lastRun) : '';
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copyStrategyBtn');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
});

// ── Copy (modal) ────────────────────────────────────────────────────────────
document.getElementById('copyBtn').addEventListener('click', () => {
  const text = lastRun
    ? getOutputText(lastRun)
    : (document.getElementById('outputYamlFallback').textContent || '');

  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copyBtn');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
});
