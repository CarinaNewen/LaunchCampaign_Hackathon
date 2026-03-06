// ── Swarm Activity Feed ────────────────────────────────────────────────────

const AGENT_DISPLAY_NAMES = {
  trend_scout: 'Trend Analysis',
  audience_psychologist: 'Audience Strategy',
  creator_fit: 'Creator Alignment',
  hook_smith: 'Hook Optimization',
  format_composer: 'Format Planning',
  critic_mutator: 'Quality Review',
};

const ACTION_DISPLAY_NAMES = {
  propose: 'Proposal',
  mutate: 'Refinement',
  merge: 'Synthesis',
  critique: 'Review',
  score: 'Scoring',
  finalize: 'Finalization',
};

function renderSwarmFeed(run) {
  const feedEl = document.getElementById('swarmFeed');
  feedEl.innerHTML = '';
  const events = run.event_history || [];

  events.forEach((ev) => {
    const li = document.createElement('li');
    li.className = 'swarm-feed-item';

    const dot = document.createElement('div');
    dot.className = 'swarm-dot ' + (ev.action_type || 'critique');
    li.appendChild(dot);

    const box = document.createElement('div');

    const meta = document.createElement('div');
    meta.className = 'meta';

    const agentPill = document.createElement('span');
    agentPill.className = 'swarm-pill';
    agentPill.textContent = AGENT_DISPLAY_NAMES[ev.agent_name] || 'Agent';
    meta.appendChild(agentPill);

    const typePill = document.createElement('span');
    typePill.className = 'swarm-pill';
    typePill.textContent = ACTION_DISPLAY_NAMES[ev.action_type] || 'Action';
    meta.appendChild(typePill);

    if (ev.round_number) {
      const r = document.createElement('span');
      r.className = 'swarm-pill';
      r.textContent = 'R' + ev.round_number;
      meta.appendChild(r);
    }

    const details = ev.payload || {};
    const thought = typeof details.thought === 'string' ? details.thought.trim() : '';
    const happened = typeof details.happened === 'string' ? details.happened.trim() : '';

    const msg = document.createElement('div');
    msg.className = 'msg';

    if (thought || happened) {
      if (thought) {
        const thoughtEl = document.createElement('div');
        thoughtEl.className = 'event-detail';
        const thoughtLabel = document.createElement('strong');
        thoughtLabel.textContent = 'Thought: ';
        thoughtEl.appendChild(thoughtLabel);
        thoughtEl.appendChild(document.createTextNode(thought));
        msg.appendChild(thoughtEl);
      }
      if (happened) {
        const happenedEl = document.createElement('div');
        happenedEl.className = 'event-detail';
        const happenedLabel = document.createElement('strong');
        happenedLabel.textContent = 'Happened: ';
        happenedEl.appendChild(happenedLabel);
        happenedEl.appendChild(document.createTextNode(happened));
        msg.appendChild(happenedEl);
      }
    } else {
      msg.textContent = ev.message || 'Action completed.';
    }

    box.appendChild(meta);
    box.appendChild(msg);
    li.appendChild(box);
    feedEl.appendChild(li);
  });
}

function updateFeedReveal(revealIndex) {
  const feedEl = document.getElementById('swarmFeed');
  if (!feedEl) return;
  const items = feedEl.querySelectorAll('.swarm-feed-item');
  let lastRevealed = null;

  items.forEach((li, i) => {
    const isRevealed = i <= revealIndex;
    li.classList.toggle('revealed', isRevealed);
    if (isRevealed) lastRevealed = li;
  });

  if (lastRevealed) {
    const wrap = feedEl.closest('.swarm-feed-wrap');
    if (wrap) lastRevealed.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
}
