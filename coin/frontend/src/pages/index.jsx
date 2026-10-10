import Head from 'next/head';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUpRight, ArrowDownRight, ArrowRight, Mic, RefreshCw, ShieldCheck, ShieldX } from 'lucide-react';
import { api } from '../services/api';
import { PriceChart } from '../components/MarketCharts';
import WatchlistSignals from '../components/WatchlistSignals';
import PortfolioPanel from '../components/PortfolioPanel';
import CoinSpinner from '../components/CoinSpinner';
import VoiceGuide from '../components/VoiceGuide';
import NewsPanel from '../components/NewsPanel';
import RiskConfig from '../components/RiskConfig';
import InkOrbitFeatures from '../components/ui/ink-orbit-features';
import { MeshGradientSVG } from '../components/ui/shader-svg';
import { StockSymbol } from '../components/ui/stock-symbols';
const initialMandate = { allocated_capital: 10000, risk_style: 'balanced', max_loss_per_trade: 100, max_daily_loss: 300, max_position_size: 2000, auto_execution_mode: 'recommend_approve' };
const initialNewsFilters = { countries: 'us', symbols: 'AAPL,MSFT,NVDA,SPY,QQQ,TSLA' };
const money = value => value != null && Number.isFinite(Number(value)) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value)) : '—';
const pct = value => value == null ? '—' : (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
const stamp = value => value ? new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }) : 'Awaiting data';
export default function Dashboard() {
  const analysisRun = useRef(0);
  const restoredSection = useRef(false);
  const [market, setMarket] = useState(null);
  const [marketError, setMarketError] = useState('');
  const [account, setAccount] = useState(null);
  const [accountError, setAccountError] = useState('');
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioError, setPortfolioError] = useState('');
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [mandate, setMandate] = useState(initialMandate);
  const [saved, setSaved] = useState(false);
  const [symbol, setSymbol] = useState('AAPL');
  const [proposal, setProposal] = useState(null);
  const [bullArgument, setBullArgument] = useState('');
  const [bearArgument, setBearArgument] = useState('');
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState('');
  const [opportunities, setOpportunities] = useState(null);
  const [opportunityError, setOpportunityError] = useState('');
  const [opportunityLoading, setOpportunityLoading] = useState(false);
  const [verdict, setVerdict] = useState(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [news, setNews] = useState(null);
  const [newsFilters, setNewsFilters] = useState(initialNewsFilters);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState('');
  const [analysisPhase, setAnalysisPhase] = useState('idle');
  const [debateSources, setDebateSources] = useState({});
  const [newsFlashOpen, setNewsFlashOpen] = useState(false);

  useEffect(() => {
    const clean = symbol.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.\-]{0,11}$/.test(clean)) return;
    const timer = setTimeout(() => api.prefetch(clean).catch(() => {}), 250);
    return () => clearTimeout(timer);
  }, [symbol]);

  const refreshAccount = useCallback(async () => {
    try {
      setAccount(await api.account());
      setAccountError('');
    } catch (error) {
      setAccountError(error.message);
    }
  }, []);

  const refreshPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try { setPortfolio(await api.portfolio()); setPortfolioError(''); }
    catch (error) { setPortfolioError(error.message); }
    finally { setPortfolioLoading(false); }
  }, []);

  useEffect(() => {
    refreshPortfolio();
    const timer = setInterval(refreshPortfolio, 30000);
    return () => clearInterval(timer);
  }, [refreshPortfolio]);

  useEffect(() => {
    refreshAccount();
    api.mandate().then((data) => { setMandate(data); setSaved(true); }).catch(() => {});
    const timer = setInterval(refreshAccount, 30000);
    return () => clearInterval(timer);
  }, [refreshAccount]);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try { const data = await api.market(); if (active) { setMarket(data); setMarketError(''); } }
      catch (error) { if (active) setMarketError(error.message); }
    };
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const refreshNews = useCallback(async (force = false, filters = newsFilters) => {
    setNewsLoading(true); setNewsError('');
    try { setNews(await api.syncNews(filters.countries, filters.symbols, force)); }
    catch (error) {
      setNewsError(error.message);
      try { setNews(await api.news(filters.countries, filters.symbols)); } catch {}
    } finally { setNewsLoading(false); }
  }, [newsFilters]);

  useEffect(() => { refreshNews(false, initialNewsFilters); }, []); // initial sync; backend cache prevents repeat network calls

  useEffect(() => {
    if (restoredSection.current || !portfolio || newsLoading || (saved && opportunityLoading)) return;
    restoredSection.current = true;
    const id = window.location.hash.slice(1);
    if (id === 'positions' || id === 'research') {
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: 'instant', block: 'start' }));
    }
  }, [portfolio, newsLoading, saved, opportunityLoading]);

  async function updateNewsFilters(next) {
    setNewsFilters(next); setNewsError('');
    try { setNews(await api.news(next.countries, next.symbols)); }
    catch (error) { setNewsError(error.message); }
  }

  useEffect(() => {
    let active = true;
    setHistory([]); setHistoryError('');
    api.history(symbol).then(data => { if (active) setHistory(data.bars); })
      .catch(error => { if (active) setHistoryError(error.message); });
    return () => { active = false; };
  }, [symbol]);

  useEffect(() => {
    if (!saved || !account) return;
    let active = true;
    setOpportunityLoading(true); setOpportunityError('');
    api.opportunities().then(data => { if (active) setOpportunities(data); })
      .catch(error => { if (active) setOpportunityError(error.message); })
      .finally(() => { if (active) setOpportunityLoading(false); });
    return () => { active = false; };
  }, [saved, account]);

  const selectSymbol = value => {
    analysisRun.current += 1;
    if (busy === 'analyze') setBusy('');
    setSymbol(value); setProposal(null); setBullArgument(''); setBearArgument('');
    setVerdict(null); setStatus(''); setAnalysisPhase('idle'); setDebateSources({});
  };

  const updateMandate = (key, value) => {
    setMandate((current) => ({ ...current, [key]: value }));
    setSaved(false);
    setVerdict(null);
    setStatus('');
  };

  async function saveMandate(event) {
    event.preventDefault();
    setBusy('mandate'); setMessage('');
    try {
      const next = await api.saveMandate(mandate);
      setMandate(next); setSaved(true);
      if (proposal) setVerdict((await api.validate(proposal)).verdict);
      setMessage('Mandate saved. Your limits are active.');
    } catch (error) { setMessage(error.message); }
    finally { setBusy(''); }
  }

  async function analyze(event) {
    event.preventDefault();
    const run = ++analysisRun.current;
    setBusy('analyze'); setAnalysisPhase('fetching'); setMessage(''); setProposal(null); setVerdict(null); setStatus(''); setBullArgument(''); setBearArgument('');
    try {
      const selectedSymbol = symbol.trim().toUpperCase();
      let state = await api.prefetch(selectedSymbol);
      for (let tries = 0; tries < 150 && state.status === 'running'; tries++) {
        if (run !== analysisRun.current) return;
        setAnalysisPhase(state.price ? 'debating' : 'fetching');
        if (state.sources) setDebateSources(state.sources);
        if (state.bull) setBullArgument(state.bull);
        if (state.bear) setBearArgument(state.bear);
        await new Promise(resolve => setTimeout(resolve, 750));
        state = await api.debateState(selectedSymbol);
      }
      if (run !== analysisRun.current) return;
      if (state.status !== 'complete') throw new Error('The analyst debate did not finish. Please retry.');
      setDebateSources(state.sources || {});
      setBullArgument(state.bull); setBearArgument(state.bear);
      setAnalysisPhase('judging');
      const next = await api.analyze(selectedSymbol);
      if (run !== analysisRun.current) return;
      setProposal(next);
      if (saved) {
        const checked = (await api.validate(next)).verdict;
        if (run !== analysisRun.current) return;
        setVerdict(checked);
        setAnalysisPhase(checked.passed ? 'ready' : 'blocked');
        if (mandate.auto_execution_mode === 'bounded_autopilot' && checked.passed) {
          const result = await api.execute(next, false);
          setStatus(result.status); setVerdict(result.verdict);
          setMessage(result.status === 'submitted' ? `Autopilot paper order submitted: ${result.order.id}` : 'Autopilot blocked by your safety settings.');
          await refreshAccount();
          await refreshPortfolio();
        }
      } else { setAnalysisPhase('ready'); setMessage('Save your mandate to see a firewall verdict.'); }
    } catch (error) { if (run === analysisRun.current) { setAnalysisPhase('error'); setMessage(error.message); } }
    finally { if (run === analysisRun.current) setBusy(''); }
  }

  async function submit() {
    if (!proposal || !verdict?.passed) return;
    setBusy('execute'); setMessage('');
    try {
      const result = await api.execute(proposal, mandate.auto_execution_mode === 'recommend_approve');
      setVerdict(result.verdict);
      setStatus(result.status);
      setMessage(result.status === 'submitted' ? `Paper order submitted: ${result.order.id}` :
        result.status === 'rejected' ? 'Risk limits changed or account data moved. Order blocked.' :
        result.status === 'observed' ? 'Observe mode recorded the recommendation without submitting an order.' :
        'Waiting for your approval.');
      await refreshAccount();
      await refreshPortfolio();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(''); }
  }

  async function deployGuided(trade) {
    if (!saved || mandate.auto_execution_mode === 'observe' || busy) return;
    setBusy('execute'); setMessage('');
    try {
      const result = await api.execute(trade, true);
      setStatus(result.status);
      setMessage(result.status === 'submitted' ? `Paper order submitted: ${result.order.id}` :
        result.verdict?.rejected_reasons?.join(' Â· ') || 'Your safety settings blocked this order.');
      setVoiceOpen(false);
      await refreshAccount();
      await refreshPortfolio();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(''); }
  }

  const mode = mandate.auto_execution_mode;
  const canSubmit = saved && proposal && verdict?.passed && mode !== 'observe' && status !== 'submitted';

  const quotes = market?.quotes || [];
  const selected = quotes.find(q => q.symbol === symbol);
  const goToSection = (event, id) => {
    event.preventDefault();
    window.history.pushState(null, '', `#${id}`);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return <>
    <Head><title>Coin / Trading desk</title><meta name="description" content="Paper trading, market research and measured risk." /><link rel="icon" href="/coin-logo.png" type="image/png"/></Head>
    <header className="masthead"><a className="wordmark" href="/"><CoinSpinner/>coin<span>/</span></a><nav aria-label="Main navigation"><a href="#research" onClick={event => goToSection(event, 'research')}>Trading desk</a><a href="#positions" onClick={event => goToSection(event, 'positions')}>Portfolio</a><a href="/coinbot">coinBot</a></nav><span className="paper-tag">PAPER ACCOUNT</span><button className="voice-trigger" onClick={() => setVoiceOpen(true)} aria-label="Open voice guide"><Mic size={15}/><span>Ask Coin</span></button><button className="icon-button" onClick={() => { refreshAccount(); refreshPortfolio(); }} aria-label="Refresh account"><RefreshCw size={16}/></button></header>
    <section className="market-tape" aria-label="Market ticker"><div className="tape-label"><i className={marketError ? 'dot warning' : 'dot'}/>{marketError ? 'FEED OFFLINE' : market ? market.is_open ? 'MARKET OPEN' : 'MARKET CLOSED' : 'CONNECTING'}</div><div className="tape-window"><div className="tape-track">{[0, 1].map(copy => <div className="tape-group" key={copy} aria-hidden={copy === 1}>{quotes.length ? quotes.map(q => <span className="tape-quote" key={q.symbol}><b>{q.symbol}</b><span>{money(q.price)}</span><em className={q.change_pct < 0 ? 'down' : 'up'}>{pct(q.change_pct)}</em></span>) : <span className="tape-quote">{marketError || 'Fetching market prices...'}</span>}</div>)}</div></div></section>
    <div className="news-flash"><span>MARKET NEWS FLASH</span><button onClick={() => setNewsFlashOpen(value => !value)} aria-expanded={newsFlashOpen}>{news?.articles?.[0]?.title || 'Waiting for market stories'} <ArrowRight size={14}/></button>{news?.articles?.[0]?.sentiment_score != null && <b className={news.articles[0].sentiment_score < 0 ? 'down' : 'up'}>{news.articles[0].sentiment_score > 0 ? '+' : ''}{news.articles[0].sentiment_score.toFixed(2)}</b>}</div>
    {newsFlashOpen && <div className="news-flash-panel">{(news?.articles || []).slice(0, 4).map(article => <a key={article.uuid} href={article.url} target="_blank" rel="noreferrer">{article.title}<small>{article.sentiment_score != null ? `${article.sentiment_score > 0 ? '+' : ''}${article.sentiment_score.toFixed(2)} ${article.sentiment_score >= 0 ? 'Bullish' : 'Bearish'}` : 'Market news'}</small></a>)}</div>}
    <main className="desk">
      <div className="page-heading"><div><span className="eyebrow">WORKSPACE / 01</span><h1>The trading desk.</h1></div><div className="feed-note">MARKET FEED / 30s refresh<br/>{marketError ? 'Stale data / reconnecting' : market ? 'Fetched ' + stamp(market.fetched_at) : 'Connecting to market feed'}</div></div>
      {accountError && <div role="alert" className="notice">Account sync unavailable. {accountError}</div>}
      <section className="account-strip" aria-label="Account overview">{[['Account balance', account?.equity], ['Buying power', account?.buying_power], ['Unrealized P&L', account?.unrealized_pl]].map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong className={label === 'Unrealized P&L' ? Number(value) < 0 ? 'down' : 'up' : ''}>{money(value)}</strong></div>)}<div className="metric account-source"><span>CONNECTED BROKER</span><strong>Paper account <span className={accountError ? 'down' : 'up'}>+</span></strong><small>{accountError ? 'Sync interrupted' : account ? 'Connected' : 'Connecting...'}</small></div></section>
      <div className="workspace-grid"><div className="primary-column">
        <section className="section" id="research"><div className="section-heading"><h2><span>01</span> Research</h2><span className="small-label">TWO-SIDED ANALYSIS</span></div><form onSubmit={analyze} className="symbol-form"><label className="symbol-input"><span>SYMBOL</span><input aria-label="Stock symbol" value={symbol} maxLength={12} onChange={e => selectSymbol(e.target.value.toUpperCase())}/></label><div className="selected-quote"><strong>{money(selected?.price)}</strong><span className={selected?.change_pct < 0 ? 'down' : 'up'}>{pct(selected?.change_pct)}</span></div><button className="primary-button" disabled={!!busy || !symbol.trim()}>{busy === 'analyze' ? 'Analyzing...' : 'View AI Debate'}<ArrowRight size={16}/></button></form>
        <InkOrbitFeatures ticker={symbol} phase={analysisPhase} sources={debateSources} bull={bullArgument} bear={bearArgument} proposal={proposal} verdict={verdict} values={history.map(bar => Number(bar.close))}/>
        {busy === 'analyze' && <div className="coin-thinking-banner"><MeshGradientSVG compact ticker={symbol} mood="thinking"/><span><b>Coin is {analysisPhase === 'fetching' ? 'gathering market signals' : analysisPhase === 'judging' ? 'weighing both cases' : 'debating both sides'}.</b><small>Prices → news → memory → debate → decision</small></span></div>}
        <div className="debate-grid">{[['Bull case', bullArgument, true], ['Bear case', bearArgument, false]].map(([title, text, positive]) => <article className="thesis" key={title}><h3 className={positive ? 'up' : 'down'}>{positive ? <ArrowUpRight size={18}/> : <ArrowDownRight size={18}/>} {title}</h3><p>{text || (positive ? 'The opportunity, the catalysts, and the case for entering.' : 'The downside, the uncertainty, and the case for staying out.')}</p>{!text && <span className="small-label">{busy === 'analyze' ? 'ANALYST WORKING...' : 'AWAITING ANALYSIS'}</span>}</article>)}</div>
        <div className="judge"><div><span className="small-label">JUDGE'S ASSESSMENT</span><p>{proposal?.judge_summary || 'Choose a stock. The bull and bear results will appear as each analyst finishes; the judge follows both.'}</p></div><div className="confidence"><strong>{proposal ? Math.round(proposal.confidence_score * 100) + '%' : '—'}</strong><span>confidence</span></div></div></section>
        <section className="section"><div className="section-heading"><h2><span>02</span> Order review</h2><span className="small-label">{proposal ? proposal.symbol + ' / ' + proposal.side.toUpperCase() + ' / ' + proposal.qty + (proposal.qty === 1 ? ' SHARE' : ' SHARES') : 'NO PROPOSAL'}</span></div><div className="order-prices">{[['Entry limit', proposal?.target_entry_price], ['Profit Target', proposal?.take_profit_price], ['Safety Stop', proposal?.stop_loss_price]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{money(value)}</strong></div>)}</div>
        <div className={'firewall ' + (verdict ? verdict.passed ? 'passed' : 'rejected' : '')}><div className="firewall-title">{verdict && !verdict.passed ? <ShieldX size={19}/> : <ShieldCheck size={19}/>}<span>Risk Firewall Verdict: <b>{verdict ? verdict.passed ? 'PASSED' : 'REJECTED' : 'PENDING'}</b></span></div>{verdict?.rejected_reasons?.map(reason => <span className="violation" key={reason}>{reason}</span>)}{!verdict && <p>{proposal ? 'Save your risk mandate to validate this trade.' : 'A proposal is required to check your limits.'}</p>}</div>
        <div className="execution-row"><p>{status === 'submitted' ? 'Paper order submitted.' : mode === 'observe' ? 'Observe mode. Orders are disabled.' : 'Your limits are checked again before submission.'}</p><button className="primary-button" onClick={submit} disabled={!canSubmit || !!busy}>{busy === 'execute' ? 'Submitting...' : mode === 'recommend_approve' ? 'One-Click Approve' : 'Execute paper trade'}<ArrowRight size={16}/></button></div>{proposal && <div className="order-risk-note">Estimated upside {proposal.estimated_upside_pct}% · downside {proposal.estimated_downside_pct}%. A stop may fill at a different price.</div>}</section>
        <NewsPanel data={news} filters={newsFilters} loading={newsLoading} error={newsError} onFilters={updateNewsFilters} onRefresh={refreshNews}/>
        <PriceChart history={history} symbol={symbol} error={historyError}/>
        <WatchlistSignals data={opportunities} loading={opportunityLoading} error={opportunityError} onSelect={selectSymbol} saved={saved}/>
        <PortfolioPanel data={portfolio} loading={portfolioLoading} error={portfolioError} onRefresh={refreshPortfolio}/>
      </div><aside>
        <section className="section watchlist"><div className="section-heading"><h2>Market watch</h2><span className="small-label">LIVE</span></div><div className="watch-head"><span>SYMBOL / LAST TRADE</span><span>PRICE / CHANGE</span></div>{quotes.map(q => <button className={'watch-row ' + (symbol === q.symbol ? 'selected' : '')} key={q.symbol} onClick={() => selectSymbol(q.symbol)}><span><b><StockSymbol ticker={q.symbol}/></b><small>{stamp(q.as_of)}</small></span><span><b>{money(q.price)}</b><small className={q.change_pct < 0 ? 'down' : 'up'}>{pct(q.change_pct)}</small></span></button>)}{!quotes.length && <p className="market-status">{marketError || 'Loading market prices...'}</p>}{market && !market.is_open && <div className="market-status">Next open: {stamp(market.next_open)}</div>}</section>
        <RiskConfig mandate={mandate} saved={saved} busy={busy} onChange={updateMandate} onSave={saveMandate}/>
      </aside></div><footer><b>coin /</b><span>Paper trading. Real market data.</span><span>USD / US EQUITIES</span></footer>
    </main><VoiceGuide open={voiceOpen} busy={busy} canDeploy={saved && mode !== 'observe'} onClose={() => setVoiceOpen(false)} onSelectSymbol={selectSymbol} onDeploy={deployGuided}/>{message && <div role="status" className="toast"><span>{message}</span><button onClick={() => setMessage('')} aria-label="Dismiss notification">Close</button></div>}
  </>;
}
