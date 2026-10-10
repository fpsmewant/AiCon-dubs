async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch {
    throw new Error('Connection to Coin was interrupted. Check that the local servers are running, then retry.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail :
    response.status >= 500 ? 'The server could not finish the request. The model provider may be busy; please retry.' : `Request failed (${response.status})`);
  return data;
}

export const api = {
  market: () => request('/market'),
  account: () => request('/account'),
  portfolio: () => request('/portfolio'),
  mandate: () => request('/mandate'),
  saveMandate: (mandate) => request('/mandate', { method: 'POST', body: JSON.stringify(mandate) }),
  analyze: (symbol) => request(`/analyze/${encodeURIComponent(symbol)}`, { method: 'POST' }),
  prefetch: (symbol) => request(`/prefetch/${encodeURIComponent(symbol)}`, { method: 'POST' }),
  debateState: (symbol) => request(`/debate-state/${encodeURIComponent(symbol)}`),
  mention: (text) => request('/mention', { method: 'POST', body: JSON.stringify({ text }) }),
  ask: (text) => request('/ask', { method: 'POST', body: JSON.stringify({ text }) }),
  debate: (symbol, side) => request(`/debate/${side}/${encodeURIComponent(symbol)}`, { method: 'POST' }),
  judge: (symbol, bull_argument, bear_argument) => request('/judge', { method: 'POST', body: JSON.stringify({ symbol, bull_argument, bear_argument }) }),
  history: (symbol) => request(`/history/${encodeURIComponent(symbol)}`),
  opportunities: () => request('/opportunities'),
  news: (countries = 'us', symbols = '') => request(`/news?countries=${encodeURIComponent(countries)}&symbols=${encodeURIComponent(symbols)}`),
  syncNews: (countries = 'us', symbols = '', force = false) => request('/news/sync', { method: 'POST', body: JSON.stringify({ countries, symbols, force }) }),
  transcribe: async (blob) => {
    const form = new FormData();
    form.append('recording', blob, `question.${blob.type.includes('ogg') ? 'ogg' : 'webm'}`);
    let response;
    try { response = await fetch('/api/voice/transcribe', { method: 'POST', body: form }); }
    catch { throw new Error('Voice upload was interrupted. Check that the local servers are running.'); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Voice transcription failed.');
    return data;
  },
  guide: (prompt, filters = {}) => request('/guide', { method: 'POST', body: JSON.stringify({ prompt, countries: filters.countries || '', symbols: filters.symbols || '' }) }),
  validate: (proposal) => request('/validate', { method: 'POST', body: JSON.stringify(proposal) }),
  execute: (proposal, approved) => request('/execute', { method: 'POST', body: JSON.stringify({ proposal, approved }) }),
  coinbotStatus: () => request('/coinbot/status'),
  coinbotStart: (config) => request('/coinbot/start', { method: 'POST', body: JSON.stringify(config) }),
  coinbotStop: () => request('/coinbot/stop', { method: 'POST' }),
  coinbotClose: () => request('/coinbot/close', { method: 'POST' }),
};
