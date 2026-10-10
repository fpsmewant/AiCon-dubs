import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowDownRight, ArrowUpRight, Clock3, RefreshCw } from 'lucide-react';
import { StockSymbol } from './ui/stock-symbols';

const money = value => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value));
const workingStatuses = new Set(['new', 'accepted', 'pending_new', 'partially_filled', 'held', 'calculated', 'accepted_for_bidding']);
const statusLabel = status => String(status || 'unknown').replaceAll('_', ' ');

export default function PortfolioPanel({ data, loading, error, onRefresh }) {
  const positions = data?.positions || [];
  const orders = data?.orders || [];
  const working = orders.filter(order => workingStatuses.has(order.status));
  const recent = orders.filter(order => !workingStatuses.has(order.status)).slice(0, 5);
  const chartData = positions.map(position => ({ symbol: position.symbol, value: Math.abs(Number(position.market_value)) }));

  return <section className="section portfolio-panel" id="positions" aria-label="Paper portfolio">
    <div className="section-heading"><div><span className="small-label">PAPER ACCOUNT</span><h2>Portfolio & orders</h2></div><button type="button" className="portfolio-refresh" onClick={onRefresh} disabled={loading} aria-label="Refresh portfolio"><RefreshCw size={15}/>{loading ? 'Syncing' : 'Refresh'}</button></div>
    {error && <p role="alert" className="portfolio-error">{error}</p>}
    <div className="portfolio-stats"><div><small>OPEN POSITIONS</small><b>{positions.length}</b></div><div><small>WORKING ORDERS</small><b>{working.length}</b></div><div><small>ORDERS IN VIEW</small><b>{orders.length}</b></div></div>
    {positions.length > 0 && <div className="portfolio-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData}><XAxis dataKey="symbol" tick={{fill:'#8b9097',fontSize:11}} axisLine={false} tickLine={false}/><YAxis hide/><Tooltip contentStyle={{background:'#191c20',border:'1px solid #34383d'}} formatter={money}/><Bar dataKey="value" fill="#d8ed88"/></BarChart></ResponsiveContainer></div>}
    <div className="portfolio-group"><h3>Open positions <span>{positions.length}</span></h3>{positions.length ? positions.map(position => <div className="portfolio-row" key={position.symbol}><StockSymbol ticker={position.symbol}/><span>{position.qty} shares</span><strong>{money(position.market_value)}</strong><span className={Number(position.unrealized_pl) < 0 ? 'down' : 'up'}>{Number(position.unrealized_pl) < 0 ? <ArrowDownRight size={14}/> : <ArrowUpRight size={14}/>} {money(position.unrealized_pl)}</span></div>) : <p className="portfolio-empty">{loading && !data ? 'Loading your paper portfolio…' : 'No filled holdings yet. Accepted orders appear below until they fill.'}</p>}</div>
    <div className="portfolio-group"><h3>Working orders <span>{working.length}</span></h3>{working.length ? working.map(order => <OrderRow key={order.id} order={order}/>) : <p className="portfolio-empty">No orders are waiting for a fill.</p>}</div>
    {recent.length > 0 && <div className="portfolio-group"><h3>Recent activity</h3>{recent.map(order => <OrderRow key={order.id} order={order}/>)}</div>}
  </section>;
}

function OrderRow({ order }) {
  const isWorking = workingStatuses.has(order.status);
  return <div className="portfolio-order"><StockSymbol ticker={order.symbol}/><span>{order.side} · {order.filled_qty}/{order.qty} filled</span><span>{order.limit_price == null ? 'Market' : money(order.limit_price)}</span><b className={isWorking ? 'working' : order.status === 'filled' ? 'filled' : ''}><Clock3 size={13}/>{statusLabel(order.status)}</b></div>;
}
