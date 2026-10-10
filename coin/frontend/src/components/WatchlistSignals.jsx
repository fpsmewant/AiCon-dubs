import { motion, useReducedMotion } from 'framer-motion';
import { ArrowUpRight, Radar, Sparkles } from 'lucide-react';
import { StockSymbol } from './ui/stock-symbols';

const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);

export default function WatchlistSignals({ data, loading, error, onSelect, saved }) {
  const reduced = useReducedMotion();
  const candidates = data?.candidates || [];
  const maxReturn = Math.max(1, ...candidates.map(item => Number(item.return_20d_pct) || 0));
  return <section className="section opportunities" id="opportunities" aria-label="Watchlist opportunities">
    <div className="section-heading"><div><span className="small-label">COIN / LIVE SCREEN</span><h2>Watchlist signals</h2></div><Radar size={21} className="opportunity-radar" aria-hidden="true"/></div>
    <p className="helper-intro">Recent 20-session moves sized against your saved paper trading limits. Select a stock to research it.</p>
    {!saved ? <p className="chart-empty">Save your safety settings to calculate paper position sizes.</p> : loading ? <div className="opportunity-scanning" role="status"><span className="orbit-scan"/><span>Scanning the watchlist against your budget…</span></div> : error ? <p className="chart-empty">{error}</p> : candidates.length ? <>
      <div className="opportunity-summary"><span><Sparkles size={15}/> {candidates.length} signals in view</span><span>20D RETURN <ArrowUpRight size={14}/></span></div>
      <div className="opportunity-list">{candidates.map((item, index) => <motion.button
        key={item.symbol} type="button" className="opportunity-card" onClick={() => onSelect(item.symbol)}
        initial={reduced ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.38, delay: reduced ? 0 : index * 0.07 }}>
        <span className="opportunity-rank">{String(index + 1).padStart(2, '0')}</span>
        <span className="opportunity-main"><b><StockSymbol ticker={item.symbol}/></b><small>{item.shares} paper shares · {money(item.estimated_cost)}</small></span>
        <span className="opportunity-performance"><b>+{item.return_20d_pct}%</b><small>avg range {item.average_daily_range_pct}%</small></span>
        <span className="opportunity-meter"><motion.i initial={reduced ? false : { scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.65, delay: reduced ? 0 : 0.16 + index * 0.07 }} style={{ width: `${Math.max(5, Number(item.return_20d_pct) / maxReturn * 100)}%` }}/></span>
        <ArrowUpRight size={17} className="opportunity-open" aria-hidden="true"/>
      </motion.button>)}</div>
    </> : <p className="chart-empty">No tracked stock meets the positive-return screen and your paper size limits.</p>}
  </section>;
}
