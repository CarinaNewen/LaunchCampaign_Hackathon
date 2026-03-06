// ── Tag Input ──────────────────────────────────────────────────────────────
function initTagInput(wrapperId, inputId) {
  const wrapper = document.getElementById(wrapperId);
  const input = document.getElementById(inputId);
  const tags = [];

  wrapper.addEventListener('click', () => input.focus());

  function renderTag(value) {
    const v = value.trim();
    if (!v || tags.includes(v)) return;
    tags.push(v);
    const tag = document.createElement('div');
    tag.className = 'tag';
    tag.innerHTML = `<span>${v}</span><button type="button">×</button>`;
    tag.querySelector('button').addEventListener('click', () => {
      const idx = tags.indexOf(v);
      if (idx > -1) tags.splice(idx, 1);
      tag.remove();
    });
    wrapper.insertBefore(tag, input);
  }

  function addTag(value) {
    const v = value.trim().replace(/,$/, '').trim();
    renderTag(v);
    input.value = '';
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); addTag(input.value); }
    if (e.key === 'Backspace' && input.value === '' && tags.length) {
      const last = wrapper.querySelectorAll('.tag');
      if (last.length) {
        const lastTag = last[last.length - 1];
        const idx = tags.indexOf(lastTag.querySelector('span').textContent);
        if (idx > -1) tags.splice(idx, 1);
        lastTag.remove();
      }
    }
  });

  input.addEventListener('input', () => {
    if (input.value.endsWith(',')) addTag(input.value);
  });

  function setTags(values) {
    tags.splice(0, tags.length);
    wrapper.querySelectorAll('.tag').forEach(el => el.remove());
    (Array.isArray(values) ? values : []).forEach(value => renderTag(String(value).trim()));
    input.value = '';
  }

  return { getTags: () => [...tags], setTags };
}

const tagInputs = {
  benefits:        initTagInput('benefitsWrapper',       'benefitsInput'),
  interests:       initTagInput('interestsWrapper',      'interestsInput'),
  trendingFormats: initTagInput('trendingFormatsWrapper','trendingFormatsInput'),
  trendingTopics:  initTagInput('trendingTopicsWrapper', 'trendingTopicsInput'),
  nicheTrends:     initTagInput('nicheTrendsWrapper',    'nicheTrendsInput'),
};

// ── Platform "Other" field ─────────────────────────────────────────────────
document.querySelectorAll('input[name="platform"]').forEach(radio => {
  radio.addEventListener('change', () => {
    document.getElementById('platformOtherField').style.display =
      radio.value === 'Other' && radio.checked ? 'block' : 'none';
  });
});

// ── Viral Examples ─────────────────────────────────────────────────────────
function addViralRow(description = '', views = '') {
  const list = document.getElementById('viralList');
  const row = document.createElement('div');
  row.className = 'viral-row';
  row.innerHTML = `
    <input type="text" placeholder="e.g. before vs after using a planner" />
    <input type="text" class="views" placeholder="Views (opt.)" />
    <button type="button" class="btn-icon viral-remove" title="Remove">×</button>`;
  const inputs = row.querySelectorAll('input');
  inputs[0].value = description;
  inputs[1].value = views;
  row.querySelector('.viral-remove').addEventListener('click', () => row.remove());
  list.appendChild(row);
}

document.getElementById('addViral').addEventListener('click', () => addViralRow());

document.getElementById('viralList').addEventListener('click', (e) => {
  if (e.target.classList.contains('viral-remove')) {
    const rows = document.querySelectorAll('.viral-row');
    if (rows.length > 1) e.target.closest('.viral-row').remove();
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────
function v(id) { return document.getElementById(id).value.trim(); }
function setV(id, value) { document.getElementById(id).value = String(value ?? '').trim(); }

function setPlatform(platformValue) {
  const platform = (platformValue || '').trim();
  const radios = document.querySelectorAll('input[name="platform"]');
  let matched = false;
  radios.forEach((radio) => {
    const isMatch = radio.value === platform;
    radio.checked = isMatch;
    if (isMatch) matched = true;
  });
  if (!matched && platform) {
    document.getElementById('p-other').checked = true;
    setV('platformOther', platform);
    document.getElementById('platformOtherField').style.display = 'block';
    return;
  }
  document.getElementById('platformOtherField').style.display = platform === 'Other' ? 'block' : 'none';
}

function applyStructuredFormData(data) {
  setV('productName',     data.product?.name        || '');
  setV('productCategory', data.product?.category    || '');
  setV('productDesc',     data.product?.description || '');
  setV('productWebsite',  data.product?.website     || '');
  tagInputs.benefits.setTags(data.product?.benefits || []);

  setV('ageRange',   data.audience?.age        || '');
  setV('lifestyle',  data.audience?.lifestyle  || '');
  setV('painPoint',  data.audience?.pain_point || '');
  tagInputs.interests.setTags(data.audience?.interests || []);

  setV('followerSize',  data.creator?.followers || '');
  setV('creatorNiche',  data.creator?.niche     || '');
  setV('contentStyle',  data.creator?.style     || '');

  setPlatform(data.platform || '');
  tagInputs.trendingFormats.setTags(data.global_trends?.formats || []);
  tagInputs.trendingTopics.setTags(data.global_trends?.topics   || []);
  tagInputs.nicheTrends.setTags(data.niche_trends || []);

  const list = document.getElementById('viralList');
  list.innerHTML = '';
  const examples = Array.isArray(data.viral_examples) ? data.viral_examples : [];
  if (!examples.length) addViralRow();
  examples.forEach(item => addViralRow(String(item), ''));
}

function convertCampaignInputToFormData(campaignInput) {
  const globalTrends = Array.isArray(campaignInput.global_trends) ? campaignInput.global_trends : [];
  return {
    product: {
      name: campaignInput.product_info || '',
      category: '', description: '', benefits: [], website: '',
    },
    audience: {
      age: '', lifestyle: campaignInput.target_audience || '',
      interests: [], pain_point: '',
    },
    creator: {
      followers: '', niche: campaignInput.creator_profile || '', style: '',
    },
    platform: campaignInput.platform || '',
    global_trends: { formats: globalTrends, topics: [] },
    niche_trends: Array.isArray(campaignInput.niche_trends)  ? campaignInput.niche_trends  : [],
    viral_examples: Array.isArray(campaignInput.viral_examples) ? campaignInput.viral_examples : [],
  };
}

function setJsonStatus(message) {
  document.getElementById('jsonApplyStatus').textContent = message;
}

document.getElementById('applyJsonBtn').addEventListener('click', () => {
  const raw = v('pasteJsonInput');
  if (!raw) { setJsonStatus('Paste JSON first.'); return; }
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.campaign_input && typeof parsed.campaign_input === 'object') {
      applyStructuredFormData(convertCampaignInputToFormData(parsed.campaign_input));
    } else {
      applyStructuredFormData(parsed);
    }
    setJsonStatus('JSON applied. You can generate now.');
  } catch (error) {
    setJsonStatus(`Invalid JSON: ${error.message || error}`);
  }
});

// ── Payload Builder ────────────────────────────────────────────────────────
function collectViralExamples() {
  const viralRows = document.querySelectorAll('.viral-row');
  const viralExamples = [];
  viralRows.forEach(row => {
    const inputs = row.querySelectorAll('input');
    const desc  = inputs[0].value.trim();
    const views = inputs[1].value.trim();
    if (desc) viralExamples.push(views ? `${desc} (${views} views)` : desc);
  });
  return viralExamples;
}

function buildSwarmPayload() {
  const platformChecked = document.querySelector('input[name="platform"]:checked');
  const platform = platformChecked
    ? (platformChecked.value === 'Other' ? v('platformOther') || 'Other' : platformChecked.value)
    : '';

  const productInfoParts = [
    v('productName'),
    v('productCategory') ? `(${v('productCategory')})` : '',
    v('productDesc'),
    tagInputs.benefits.getTags().length ? `Benefits: ${tagInputs.benefits.getTags().join(', ')}` : '',
    v('productWebsite') ? `Website: ${v('productWebsite')}` : '',
  ].filter(Boolean);

  const audienceParts = [
    v('ageRange')   ? `Age: ${v('ageRange')}`             : '',
    v('lifestyle')  ? `Lifestyle: ${v('lifestyle')}`      : '',
    tagInputs.interests.getTags().length ? `Interests: ${tagInputs.interests.getTags().join(', ')}` : '',
    v('painPoint')  ? `Pain point: ${v('painPoint')}`     : '',
  ].filter(Boolean);

  const creatorParts = [
    v('followerSize') ? `Followers: ${v('followerSize')}` : '',
    v('creatorNiche') ? `Niche: ${v('creatorNiche')}`     : '',
    v('contentStyle') ? `Style: ${v('contentStyle')}`     : '',
  ].filter(Boolean);

  return {
    campaign_input: {
      product_info:    productInfoParts.join(' | ') || 'Unknown product',
      target_audience: audienceParts.join(' | ')    || 'General short-form audience',
      creator_profile: creatorParts.join(' | ')     || 'Creator details not provided',
      platform:        platform                     || 'TikTok',
      global_trends: [
        ...tagInputs.trendingFormats.getTags(),
        ...tagInputs.trendingTopics.getTags(),
      ],
      niche_trends:    tagInputs.nicheTrends.getTags(),
      viral_examples:  collectViralExamples(),
    },
    max_rounds: 3,
  };
}
