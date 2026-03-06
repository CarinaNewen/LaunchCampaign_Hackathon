// ── Strategy Overlay ────────────────────────────────────────────────────────

function openStrategyOverlay(run) {
  const overlay = document.getElementById('strategyOverlay');
  const content = document.getElementById('strategyContent');
  const meta    = document.getElementById('strategyMeta');

  const out      = run.final_output || {};
  const concepts = out.content_concepts || [];

  const pills = [
    run.run_id        ? `ID: ${run.run_id.slice(0, 8)}…`        : null,
    run.round_number != null ? `${run.round_number} rounds`     : null,
    concepts.length   ? `${concepts.length} concepts`           : null,
  ].filter(Boolean);

  meta.innerHTML = pills.map(t => `<span class="st-pill">${t}</span>`).join('');
  content.innerHTML = renderStrategyContent(run);
  overlay.classList.add('open');
}

function renderStrategyContent(run) {
  const out      = run.final_output || {};
  const concepts = out.content_concepts      || [];
  const hooks    = out.hook_library          || [];
  const formats  = out.recommended_formats   || [];
  const plan     = out.posting_experiment_plan || [];

  // ── Hero: Strategy Summary ──────────────────────────────────────────────
  const summaryHtml = out.strategy_summary ? `
    <section class="st-hero">
      <div class="st-hero-label">Strategy Summary</div>
      <p class="st-hero-text">${escHtml(out.strategy_summary)}</p>
    </section>` : '';

  // ── Content Concepts grid ───────────────────────────────────────────────
  const conceptsHtml = concepts.length ? `
    <section class="st-section">
      <h3 class="st-section-title">
        Content Concepts
        <span class="st-count">${concepts.length}</span>
      </h3>
      <div class="st-concepts-grid">
        ${concepts.map((c, i) => `
          <div class="st-concept-card">
            <div class="st-concept-num">${String(i + 1).padStart(2, '0')}</div>
            <div class="st-concept-main">
              <h4 class="st-concept-title">${escHtml(c.title || 'Untitled concept')}</h4>
              ${c.description ? `<p class="st-concept-desc">${escHtml(c.description)}</p>` : ''}
              ${c.hook ? `<blockquote class="st-concept-hook">${escHtml(c.hook)}</blockquote>` : ''}
              <div class="st-concept-footer">
                ${c.source_agent   ? `<span class="st-tag agent">${escHtml(c.source_agent)}</span>` : ''}
                ${c.round_created != null ? `<span class="st-tag round">R${c.round_created}</span>` : ''}
              </div>
            </div>
          </div>`).join('')}
      </div>
    </section>` : '';

  // ── Bottom three columns ────────────────────────────────────────────────
  const bottomHtml = (hooks.length || formats.length || plan.length) ? `
    <section class="st-bottom">
      ${hooks.length ? `
        <div class="st-bottom-col">
          <h4 class="st-col-title hooks">Hook Library</h4>
          <ul class="st-col-list">
            ${hooks.map(h => `<li>${escHtml(String(h))}</li>`).join('')}
          </ul>
        </div>` : ''}
      ${formats.length ? `
        <div class="st-bottom-col">
          <h4 class="st-col-title formats">Recommended Formats</h4>
          <ul class="st-col-list">
            ${formats.map(f => `<li>${escHtml(String(f))}</li>`).join('')}
          </ul>
        </div>` : ''}
      ${plan.length ? `
        <div class="st-bottom-col">
          <h4 class="st-col-title plan">Posting Plan</h4>
          <ol class="st-col-list ordered">
            ${plan.map(s => `<li>${escHtml(String(s))}</li>`).join('')}
          </ol>
        </div>` : ''}
    </section>` : '';

  return summaryHtml + conceptsHtml + bottomHtml;
}

// ── Plain-text version used for copying ────────────────────────────────────
function getOutputText(run) {
  const out      = run.final_output || {};
  const concepts = out.content_concepts      || [];
  const hooks    = out.hook_library          || [];
  const formats  = out.recommended_formats   || [];
  const plan     = out.posting_experiment_plan || [];

  const conceptText = concepts.length
    ? concepts.map((idea, idx) => [
        `${idx + 1}. ${idea.title || 'Untitled concept'}`,
        `   Description: ${idea.description || ''}`,
        `   Hook: ${idea.hook || ''}`,
        `   Source: ${idea.source_agent || ''}`,
      ].join('\n')).join('\n\n')
    : 'No concepts generated.';

  return [
    `Run ID: ${run.run_id || '-'}`,
    `Rounds: ${run.round_number || 0}`,
    '',
    'STRATEGY SUMMARY',
    out.strategy_summary || 'No summary generated.',
    '',
    'CONTENT CONCEPTS',
    conceptText,
    '',
    'HOOK LIBRARY',
    hooks.length   ? hooks.map(h => `- ${h}`).join('\n')   : '- None',
    '',
    'RECOMMENDED FORMATS',
    formats.length ? formats.map(f => `- ${f}`).join('\n') : '- None',
    '',
    'POSTING / EXPERIMENT PLAN',
    plan.length    ? plan.map(s => `- ${s}`).join('\n')    : '- None',
  ].join('\n');
}

// ── HTML-escape helper ──────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
