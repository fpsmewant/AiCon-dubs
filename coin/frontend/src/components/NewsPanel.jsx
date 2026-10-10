import { RefreshCw } from 'lucide-react';

const ago = value => {
  if (!value) return 'unknown time';
  const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

export default function NewsPanel({ data, filters, loading, error, onFilters, onRefresh }) {
  const articles = data?.articles || [];
  return <section className="section news-panel" id="market-news" aria-label="Market news">
    <div className="section-heading"><div><h2>Market news memory</h2><p>Marketaux stories retained locally for new-versus-previous comparisons.</p></div><span className="small-label">SQLITE CACHE</span></div>
    <div className="news-controls"><label><span>MARKET</span><select value={filters.countries} onChange={event => onFilters({ ...filters, countries: event.target.value })}><option value="us">United States</option><option value="gb">United Kingdom</option><option value="ca">Canada</option><option value="au">Australia</option><option value="de">Germany</option><option value="in">India</option><option value="">Global</option></select></label><label className="news-symbols"><span>SYMBOLS · COMMA SEPARATED</span><input value={filters.symbols} onChange={event => onFilters({ ...filters, symbols: event.target.value.toUpperCase() })} placeholder="AAPL,MSFT,NVDA"/></label><button onClick={() => onRefresh(true)} disabled={loading}><RefreshCw size={15}/>{loading ? 'Syncing…' : 'Fetch new'}</button></div>
    <div className="news-status"><span>{data?.new_count || 0} new this sync</span><span>{articles.length} stored matches</span><span>{data?.cache_hit ? 'local cache' : data ? 'Marketaux refreshed' : 'waiting'}</span></div>
    {error && <p className="news-error">{error}</p>}
    <div className="news-list">{articles.map(article => <article key={article.uuid}><div className="news-meta">{article.is_new && <b>NEW</b>}<span>{article.source}</span><span>{ago(article.published_at)}</span>{article.sentiment_score != null && <span className={article.sentiment_score < 0 ? 'down' : 'up'}>{article.sentiment_score > 0 ? '+' : ''}{article.sentiment_score.toFixed(2)} sentiment</span>}</div><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a><p>{article.description || article.snippet}</p><div className="news-tickers">{article.symbols.map(symbol => <span key={symbol}>{symbol}</span>)}</div></article>)}</div>
    {!loading && !articles.length && <p className="chart-empty">No locally stored stories match these filters. Fetch new stories to populate the database.</p>}
    <p className="footnote">Headlines are third-party information. “New” means first seen by this local Coin database, not necessarily newly published.</p>
  </section>;
}
