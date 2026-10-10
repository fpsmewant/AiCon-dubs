import Head from 'next/head';
import { useCallback, useEffect, useState } from 'react';
import {
  Activity, ArrowLeft, ArrowUpRight, Clock3, Pause, Play,
  ShieldCheck, Sparkles, TrendingUp, X,
} from 'lucide-react';
import {
  Area, AreaChart, Bar, CartesianGrid, ComposedChart, Line,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { StockSymbol, stockIdentity } from '../components/ui/stock-symbols';
import { api } from '../services/api';

const money = value => Number.isFinite(Number(value)) && value != null
  ? `$${Number(value).toFixed(2)}` : '—';
const signedMoney = value => `${Number(value) >= 0 ? '+' : '−'}${money(Math.abs(Number(value)))}`;
const when = value => value
  ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
const dateTime = value => value
  ? new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

export default function CoinBotPage() {
  const [data, setData] = useState(null);
  const [config, setConfig] = useState({
    max_trade_budget: 1000, take_profit_pct: 3, stop_loss_pct: 1.5,
  });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      setData(await api.coinbotStatus());
      setError('');
    } catch (cause) {
      setError(cause.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 5000);
    return () => clearInterval(poll);
  }, [refresh]);

  useEffect(() => {
    if (data?.config) setConfig(previous => ({ ...previous, ...data.config }));
  }, [data?.config?.max_trade_budget, data?.config?.take_profit_pct, data?.config?.stop_loss_pct]);

  const perform = async (label, action) => {
    setBusy(label);
    setError('');
    try {
      await action();
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy('');
    }
  };

  const active = Boolean(data?.enabled);
  const quote = data?.quotes?.find(item => item.symbol === data?.selected);
  const chart = (data?.chart || []).map(point => ({
    time: when(point.ts), price: Number(point.price),
  }));
  const performance = (data?.performance || []).map(point => ({
    time: when(point.ts), pnl: Number(point.pnl),
    gain: Math.max(0, Number(point.pnl)), loss: Math.min(0, Number(point.pnl)),
  }));
  const pnl = performance.at(-1)?.pnl || 0;
  const position = data?.positions?.find(item => item.filled_qty > 0);
  const phase = ({
    paused: 'Paused', market_closed: 'Market closed', observing: 'Learning the tape',
    scanning: 'Watching for an edge', thinking: 'Weighing the evidence',
    managing_position: 'Managing a position', stale_data: 'Waiting for fresh prices',
    risk_limit: 'Risk limit reached',
  })[data?.phase] || 'Connecting to market';

  return <>
    <Head>
      <title>coinBot / Coin</title>
      <meta name="description" content="CoinBot US stock paper trading workspace" />
      <link rel="icon" href="/coin-logo.png" type="image/png" />
    </Head>
    <div className="coinbot-page">
      <header className="coinbot-topbar">
        <a href="/" className="coinbot-brand">
          <span className={`coinbot-avatar ${active ? 'working' : ''}`} aria-hidden="true" />
          coin<span>Bot</span>
        </a>
        <nav><a href="/"><ArrowLeft size={16} /> Trading desk</a></nav>
      </header>

      <main className="coinbot-main">
        <section className="coinbot-hero">
          <div>
            <p className="coinbot-eyebrow"><Sparkles size={13} /> YOUR MARKET SCOUT</p>
            <h1>Meet the market. Make your move.</h1>
            <p className="coinbot-intro">
              coinBot watches a small circle of US stocks, learns from its own paper trades,
              and moves only when price, context, and your risk settings agree.
            </p>
          </div>
          <div className="coinbot-hero-orb">
            <span className={`coinbot-avatar ${active ? 'working' : ''}`} aria-label="coinBot coin" />
          </div>
        </section>

        {error && <div className="coinbot-alert" role="alert">
          {error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={16} /></button>
        </div>}
        {data?.error && <div className="coinbot-alert" role="status">Market check: {data.error}</div>}

        <section className="coinbot-status-grid">
          <article className="coinbot-panel coinbot-current">
            <div className="coinbot-panel-kicker"><Activity size={15} /> MARKET PULSE</div>
            <h2>{stockIdentity(data?.selected).name} <span className="coinbot-symbol">{data?.selected}</span></h2>
            <p>US equities · Alpaca IEX prices · paper trading</p>
            <div className="coinbot-live-stats">
              <div><small>LATEST TRADE</small><strong>{money(quote?.price)}</strong></div>
              <div><small>SESSION MOVE</small><strong className={quote?.change_pct >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>
                {quote?.change_pct == null ? '—' : `${quote.change_pct >= 0 ? '+' : ''}${quote.change_pct.toFixed(2)}%`}
              </strong></div>
              <div><small>AS OF</small><strong>{dateTime(quote?.as_of)}</strong></div>
            </div>
            <div className="coinbot-phase">
              <span className={active ? 'coinbot-phase-pulse' : ''} />
              <b>{!data?.market_open && data?.last_tick && data?.phase !== 'market_closed'
                ? `Market closed · ${phase.toLowerCase()}` : phase}</b>
              <small>{!data?.market_open && data?.next_open
                ? `Next session ${new Date(data.next_open).toLocaleString()}`
                : active ? 'CoinBot can wait; no trade is forced.' : 'Start when you are ready.'}</small>
            </div>
          </article>

          <article className="coinbot-panel coinbot-controls">
            <div className="coinbot-panel-kicker"><ShieldCheck size={15} /> YOUR BOUNDARIES</div>
            <h2>Give it room, with limits.</h2>
            <p>Set the most coinBot may use for one trade. It chooses whether to enter and how much to spend.</p>
            <div className="coinbot-input-grid">
              <label>Max per trade <span>$</span>
                <input type="number" min="1" max="100000" step="1"
                  value={config.max_trade_budget} disabled={active}
                  onChange={event => setConfig({ ...config, max_trade_budget: Number(event.target.value) })} />
              </label>
              <label>Profit target <span>%</span>
                <input type="number" min="0.1" max="25" step="0.1"
                  value={config.take_profit_pct} disabled={active}
                  onChange={event => setConfig({ ...config, take_profit_pct: Number(event.target.value) })} />
              </label>
              <label>Safety stop <span>%</span>
                <input type="number" min="0.1" max="20" step="0.1"
                  value={config.stop_loss_pct} disabled={active}
                  onChange={event => setConfig({ ...config, stop_loss_pct: Number(event.target.value) })} />
              </label>
            </div>
            <button className={`coinbot-primary ${active ? 'coinbot-stop' : ''}`}
              disabled={Boolean(busy) || !data?.configured}
              onClick={() => perform(active ? 'stop' : 'start', active ? api.coinbotStop : () => api.coinbotStart(config))}>
              {active ? <><Pause size={16} /> Pause coinBot</> : <><Play size={16} /> Start coinBot</>}
            </button>
            <small className="coinbot-hint">
              Paper account · whole shares · profit and stop orders stay at the broker, including overnight.
            </small>
          </article>
        </section>

        <section className="coinbot-watchlist coinbot-panel">
          <div className="coinbot-panel-heading">
            <div><p className="coinbot-eyebrow">THE SHORTLIST</p><h2>Stocks with a pulse</h2></div>
            <span>Tap a symbol to view its chart</span>
          </div>
          <div className="coinbot-stock-list">
            {(data?.symbols || ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMD']).map(symbol => {
              const item = data?.quotes?.find(row => row.symbol === symbol);
              return <button key={symbol} className={data?.selected === symbol ? 'selected' : ''}
                onClick={() => perform('select', () => api.coinbotSelect(symbol))}>
                <StockSymbol ticker={symbol} size={18} />
                <small>{stockIdentity(symbol).name}</small>
                <strong>{money(item?.price)}</strong>
                <em className={item?.change_pct >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>
                  {item?.change_pct == null ? '—' : `${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}%`}
                </em>
              </button>;
            })}
          </div>
        </section>

        <section className="coinbot-charts">
          <article className="coinbot-panel">
            <div className="coinbot-panel-heading">
              <div><p className="coinbot-eyebrow">PRICE TAPE</p><h2>{data?.selected} · recent IEX trades</h2></div>
              <TrendingUp size={17} />
            </div>
            <div className="coinbot-chart">
              {chart.length > 1 ? <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart}>
                  <defs><linearGradient id="coinbot-price-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#679dff" stopOpacity={0.26} />
                    <stop offset="100%" stopColor="#679dff" stopOpacity={0} />
                  </linearGradient></defs>
                  <CartesianGrid stroke="#283a55" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: '#7e94b1', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={28} />
                  <YAxis domain={['auto', 'auto']} tick={{ fill: '#7e94b1', fontSize: 10 }} axisLine={false} tickLine={false} width={57} />
                  <Tooltip contentStyle={{ background: '#152238', border: '1px solid #365071', borderRadius: 8 }} formatter={value => money(value)} />
                  <Area dataKey="price" type="monotone" stroke="#77aaff" strokeWidth={2.5} fill="url(#coinbot-price-fill)" dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer> : <div className="coinbot-chart-empty">Collecting the latest stock chart.</div>}
            </div>
            <small className="coinbot-hint">Outside market hours, this chart shows the latest available session.</small>
          </article>
          <article className="coinbot-panel">
            <div className="coinbot-panel-heading">
              <div><p className="coinbot-eyebrow">TODAY'S JOURNAL</p><h2>Paper profit &amp; loss</h2></div>
              <b className={pnl >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>{signedMoney(pnl)}</b>
            </div>
            <div className="coinbot-chart">
              {performance.length > 1 ? <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={performance}>
                  <CartesianGrid stroke="#283a55" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: '#7e94b1', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={28} />
                  <YAxis tick={{ fill: '#7e94b1', fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
                  <Tooltip content={({ active: shown, payload, label }) => shown && payload?.length
                    ? <div className="coinbot-tooltip">{label} · {signedMoney(payload.find(item => item.dataKey === 'pnl')?.value || 0)}</div>
                    : null} />
                  <ReferenceLine y={0} stroke="#6d85a5" />
                  <Bar dataKey="gain" fill="#72ccb9" barSize={4} isAnimationActive={false} />
                  <Bar dataKey="loss" fill="#e98191" barSize={4} isAnimationActive={false} />
                  <Line dataKey="pnl" type="monotone" stroke="#82c3da" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer> : <div className="coinbot-chart-empty">The journal draws as coinBot observes and trades.</div>}
            </div>
          </article>
        </section>

        <section className="coinbot-bottom-grid">
          <article className="coinbot-panel">
            <div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">RIGHT NOW</p><h2>Position &amp; decision</h2></div></div>
            {position ? <div className="coinbot-position">
              <StockSymbol ticker={position.symbol} size={18} />
              <span>{position.filled_qty} shares · entry {money(position.entry_price)}<br />
                Target {money(position.target_price)} · stop {money(position.stop_price)}</span>
              <button disabled={Boolean(busy)} onClick={() => perform('close', api.coinbotClose)}>
                Close <ArrowUpRight size={15} />
              </button>
            </div> : <p className="coinbot-empty">No open coinBot position. Waiting is a decision, too.</p>}
            <div className="coinbot-decision">
              <small>LATEST DECISION</small>
              <strong>{data?.decision?.action || 'Observing'}</strong>
              <p>{data?.decision?.reason || 'coinBot is reading the market before it acts.'}</p>
              {data?.decision?.confidence != null && <span>{Math.round(data.decision.confidence * 100)}% confidence</span>}
            </div>
          </article>
          <article className="coinbot-panel">
            <div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">PAPER ORDER TAPE</p><h2>Recent trades</h2></div><Clock3 size={17} /></div>
            <div className="coinbot-trades">
              {data?.orders?.length ? data.orders.slice(0, 8).map(trade => <div key={trade.order_id}>
                <time>{when(trade.ts)}</time><StockSymbol ticker={trade.symbol} size={14} />
                <span>{trade.qty} shares · {trade.status}</span>
              </div>) : <p className="coinbot-empty">Orders appear here after coinBot submits them.</p>}
            </div>
          </article>
        </section>

        <section className="coinbot-panel coinbot-lessons">
          <div className="coinbot-panel-heading"><div><p className="coinbot-eyebrow">LEARNING MEMORY</p><h2>What past trades taught us</h2></div><span>{data?.lessons?.length || 0} scored</span></div>
          {data?.lessons?.length ? <div className="coinbot-lesson-list">
            {data.lessons.map((lesson, index) => <div key={`${lesson.symbol}-${index}`}>
              <StockSymbol ticker={lesson.symbol} size={15} />
              <strong className={lesson.pnl >= 0 ? 'coinbot-positive' : 'coinbot-negative'}>{signedMoney(lesson.pnl)}</strong>
              <span>{lesson.lesson}</span><time>{when(lesson.exit_time)}</time>
            </div>)}
          </div> : <p className="coinbot-empty">Closed trades become lessons for future decisions.</p>}
        </section>
      </main>
    </div>
  </>;
}
