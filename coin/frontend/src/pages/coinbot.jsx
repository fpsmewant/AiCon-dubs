import Head from 'next/head';
import { useCallback, useEffect, useState } from 'react';
import { Activity, ArrowLeft, ArrowUpRight, Clock3, Pause, Play, ShieldCheck, TrendingDown, TrendingUp, X } from 'lucide-react';
import { Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';

const money = value => Number.isFinite(Number(value)) ? `$${Number(value).toFixed(2)}` : '—';
const percent = value => `${Number(value || 0).toFixed(1)}%`;
const clock = value => value == null ? '—' : `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
const when = value => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

export default function CoinBotPage() {
  const [data, setData] = useState(null);
  const [config, setConfig] = useState({ max_window_spend: 20, take_profit_pct: 15, stop_loss_pct: 12 });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(async () => {
    try { setData(await api.coinbotStatus()); setError(''); }
    catch (err) { setError(err.message); }
  }, []);

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 5000);
    const ticker = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(poll); clearInterval(ticker); };
  }, [refresh]);

  useEffect(() => {
    if (data?.config) setConfig(previous => ({ ...previous, ...data.config }));
  }, [data?.config?.max_window_spend, data?.config?.take_profit_pct, data?.config?.stop_loss_pct]);

  const perform = async (label, fn) => {
    setBusy(label);
    setError('');
    try { await fn(); await refresh(); }
    catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  const market = data?.market;
  const active = Boolean(data?.enabled);
  const secondsLeft = market?.close_time ? Math.max(0, Math.floor((new Date(market.close_time).getTime() - now) / 1000)) : null;
  const observeLeft = market?.open_time ? Math.max(0, Math.floor((new Date(market.open_time).getTime() + 120000 - now) / 1000)) : 0;
  const phase = !market ? 'Waiting for a BTC window' : observeLeft ? 'Reading the market' : active ? 'Watching for an edge' : 'Ready to observe';
  const exposure = data?.exposure;
  const openLeg = exposure?.yes?.count > 0 ? { side: 'YES', ...exposure.yes } : exposure?.no?.count > 0 ? { side: 'NO', ...exposure.no } : null;
  const spent = exposure?.spent || 0;
  const chart = (data?.equity || []).map((point, index, all) => ({
    time: when(point.ts), pnl: Number((point.value - all[0].value).toFixed(2)), index,
  }));
  const trend = (data?.snapshots || []).map(point => ({ time: when(point.ts), yes: Number((100 * point.yes_bid).toFixed(0)), btc: point.btc_spot }));
  const last = chart.at(-1)?.pnl || 0;

  return <>
    <Head><title>coinBot / Coin</title><meta name="description" content="CoinBot demo BTC trading workspace"/><link rel="icon" href="/coin-logo.png" type="image/png"/></Head>
    <div className="coinbot-page">
      <header className="coinbot-topbar">
        <a href="/" className="coinbot-brand"><span className={`coinbot-avatar ${active ? 'working' : ''}`} aria-hidden="true"/>coin<span>Bot</span></a>
        <nav><a href="/"><ArrowLeft size={15}/> Trading desk</a><span className="coinbot-demo-badge"><span/> DEMO ACCOUNT</span></nav>
      </header>
      <main className="coinbot-main">
        <section className="coinbot-hero">
          <div><p className="coinbot-eyebrow">AUTONOMOUS BTC / 15-MINUTE WINDOWS</p><h1>Every window is a new decision.</h1>
            <p className="coinbot-intro">coinBot watches live odds and BTC price, spends the first two minutes gathering evidence, then chooses a side, a size, or no trade. Once started, it follows the next window automatically.</p></div>
          <div className="coinbot-hero-orb"><span className={`coinbot-avatar ${active ? 'working' : ''}`} aria-label="coinBot coin"/></div>
        </section>

        {error && <div className="coinbot-alert" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={16}/></button></div>}
        {data?.error && <div className="coinbot-alert" role="status">Market feed: {data.error}</div>}

        <section className="coinbot-status-grid">
          <article className="coinbot-panel coinbot-current"><div className="coinbot-panel-kicker"><Activity size={15}/> LIVE WINDOW <span className={market ? 'coinbot-live-dot' : ''}/></div>
            <h2>{market ? market.title || 'BTC price up in 15 minutes?' : 'Waiting for next window'}</h2>
            <p className="coinbot-market-id">{market?.ticker || data?.upcoming?.ticker || 'Searching for the next BTC market'}</p>
            <div className="coinbot-live-stats"><div><small>TIME LEFT</small><strong>{clock(secondsLeft)}</strong></div><div><small>YES / NO ASK</small><strong>{market ? `${Math.round(Number(market.yes_ask_dollars || 0) * 100)}¢ / ${Math.round(Number(market.no_ask_dollars || 0) * 100)}¢` : '—'}</strong></div><div><small>BTC SPOT</small><strong>{money(data?.snapshots?.at(-1)?.btc_spot)}</strong></div></div>
            <div className="coinbot-phase"><span className={active ? 'coinbot-phase-pulse' : ''}/><b>{phase}</b><small>{observeLeft ? `${clock(observeLeft)} left before orders are permitted` : active ? 'Orders only when the analysis clears the risk checks' : 'Start coinBot to enable demo trades'}</small></div>
            <div className="coinbot-timeline"><i style={{ width: `${market ? Math.min(100, Math.max(0, ((900 - secondsLeft) / 900) * 100)) : 0}%` }}/><span className="coinbot-observation-band"/></div><div className="coinbot-time-labels"><span>OPEN</span><span>2 MIN · RESEARCH ONLY</span><span>CLOSE</span></div>
          </article>

          <article className="coinbot-panel coinbot-controls"><div className="coinbot-panel-kicker"><ShieldCheck size={15}/> YOUR BOUNDARIES</div><h2>Set the room to trade.</h2><p>coinBot chooses if and when to trade, and how much to use within your budget.</p>
            <div className="coinbot-input-grid"><label>Max spend per window <span>$</span><input type="number" min="1" max="10000" step="1" value={config.max_window_spend} onChange={event => setConfig({ ...config, max_window_spend: Number(event.target.value) })} disabled={active}/></label>
              <label>Take profit <span>%</span><input type="number" min="1" max="100" step="1" value={config.take_profit_pct} onChange={event => setConfig({ ...config, take_profit_pct: Number(event.target.value) })} disabled={active}/></label>
              <label>Loss threshold <span>%</span><input type="number" min="1" max="100" step="1" value={config.stop_loss_pct} onChange={event => setConfig({ ...config, stop_loss_pct: Number(event.target.value) })} disabled={active}/></label></div>
            <button className={`coinbot-primary ${active ? 'coinbot-stop' : ''}`} disabled={Boolean(busy) || !data?.configured} onClick={() => perform(active ? 'stop' : 'start', active ? api.coinbotStop : () => api.coinbotStart(config))}>{active ? <><Pause size={16}/> Pause coinBot</> : <><Play size={16}/> Start coinBot</>}</button>
            {!data?.configured && <small className="coinbot-hint">Demo account credentials are needed to start.</small>}
            <small className="coinbot-hint">Demo orders only · the bot continues to the next window until paused</small>
          </article>
        </section>

        <section className="coinbot-charts">
          <article className="coinbot-panel coinbot-chart-panel"><div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">TODAY'S PERFORMANCE</p><h2>Profit &amp; loss</h2></div><b className={last >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>{last >= 0 ? '+' : ''}{money(last)}</b></div>
            <div className="coinbot-chart">{chart.length ? <ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart}><CartesianGrid stroke="#273530" vertical={false}/><XAxis dataKey="time" tick={{ fill: '#84988b', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill: '#84988b', fontSize: 10 }} axisLine={false} tickLine={false} width={45}/><Tooltip contentStyle={{ background: '#19231e', border: '1px solid #4b6551', borderRadius: 8 }} formatter={value => money(value)}/><ReferenceLine y={0} stroke="#6c7d70"/><Bar dataKey="pnl" barSize={8} radius={[3,3,0,0]}>{chart.map((point, index) => <Cell key={index} fill={point.pnl >= 0 ? '#9bdd8b' : '#ef786a'}/>)}</Bar><Line dataKey="pnl" stroke="#d9ead0" strokeWidth={2} dot={false} isAnimationActive={false}/></ComposedChart></ResponsiveContainer> : <div className="coinbot-chart-empty">The day chart will populate as account values arrive.</div>}</div>
          </article>
          <article className="coinbot-panel coinbot-chart-panel"><div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">LIVE MARKET FLOW</p><h2>YES price</h2></div><b>{market ? `${Math.round(Number(market.yes_bid_dollars || 0) * 100)}¢` : '—'}</b></div>
            <div className="coinbot-chart">{trend.length ? <ResponsiveContainer width="100%" height="100%"><ComposedChart data={trend}><CartesianGrid stroke="#273530" vertical={false}/><XAxis dataKey="time" tick={{ fill: '#84988b', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis domain={[0,100]} tick={{ fill: '#84988b', fontSize: 10 }} axisLine={false} tickLine={false} width={36}/><Tooltip contentStyle={{ background: '#19231e', border: '1px solid #4b6551', borderRadius: 8 }}/><Line dataKey="yes" stroke="#d8c26f" strokeWidth={2.5} dot={false} isAnimationActive={false}/></ComposedChart></ResponsiveContainer> : <div className="coinbot-chart-empty">Waiting for the first market observation.</div>}</div>
          </article>
        </section>

        <section className="coinbot-bottom-grid">
          <article className="coinbot-panel"><div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">OPEN EXPOSURE</p><h2>Current position</h2></div><span className="coinbot-spent">{money(spent)} / {money(data?.config?.max_window_spend)} used</span></div>
            {openLeg ? <div className="coinbot-position"><b className={openLeg.side === 'YES' ? 'coinbot-positive' : 'coinbot-negative'}>{openLeg.side === 'YES' ? <TrendingUp size={19}/> : <TrendingDown size={19}/>} {openLeg.side}</b><span>{openLeg.count} contracts · {money(openLeg.cost)} entry</span><button disabled={Boolean(busy) || observeLeft > 0} onClick={() => perform('close', api.coinbotClose)}>Close position <ArrowUpRight size={15}/></button></div> : <p className="coinbot-empty">No position in this window. Waiting is a valid decision.</p>}
            <div className="coinbot-decision"><small>LATEST DECISION</small><strong>{data?.decision?.action?.replace('_', ' ') || 'Observing'}</strong><p>{data?.decision?.reason || 'The bot will read market movement before proposing a trade.'}</p>{data?.decision?.confidence != null && <span>{percent(data.decision.confidence * 100)} confidence</span>}</div>
          </article>
          <article className="coinbot-panel"><div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">RECENT FILLS</p><h2>Trade tape</h2></div><Clock3 size={17}/></div>
            <div className="coinbot-trades">{data?.orders?.length ? data.orders.slice(0, 8).map(order => <div key={order.order_id}><time>{when(order.ts)}</time><b className={order.action === 'buy' ? 'coinbot-positive' : 'coinbot-muted'}>{order.action.toUpperCase()} {order.outcome.toUpperCase()}</b><span>{order.count} @ {Math.round((order.outcome === 'yes' ? order.yes_price : 1 - order.yes_price) * 100)}¢</span></div>) : <p className="coinbot-empty">Trades will appear here after a demo order fills.</p>}</div>
          </article>
        </section>
        <section className="coinbot-panel coinbot-rounds"><div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">LEARNING MEMORY</p><h2>Completed windows</h2></div><span>{data?.rounds?.length || 0} scored</span></div>{data?.rounds?.length ? <div className="coinbot-round-list">{data.rounds.map(round => <div key={round.ticker}><time>{when(round.closed_at)}</time><strong>{round.ticker}</strong><span>BTC {round.result?.toUpperCase()}</span><b className={round.pnl >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>{round.pnl >= 0 ? '+' : ''}{money(round.pnl)}</b><small>{round.lesson}</small></div>)}</div> : <p className="coinbot-empty">After a traded window settles, its result and lesson will be saved here for future decisions.</p>}</section>
      </main>
    </div>
  </>;
}
