"use client"

// Coin's symbol-only adaptation of the attached three-panel workflow bento.
// Every ready state comes from the active request; no simulated prices or sources.
import { ArrowRight, BookOpen, BrainCircuit, Check, Database, Newspaper, Scale, ShieldCheck, ShieldX, TrendingDown, TrendingUp } from "lucide-react"
import { StockSymbol } from "./stock-symbols"

export type CoinSources = { alpaca?: boolean; marketaux?: number; liquid?: number }
type WorkflowPhase = "idle" | "fetching" | "debating" | "judging" | "ready" | "blocked" | "error"

export default function InkOrbitFeatures({ ticker, phase = "idle", sources = {}, bull, bear,
  proposal, verdict, values = [] }: {
  ticker: string
  phase?: WorkflowPhase
  sources?: CoinSources
  bull?: string
  bear?: string
  proposal?: { judge_summary?: string; confidence_score?: number } | null
  verdict?: { passed?: boolean } | null
  values?: number[]
}) {
  const actualValues = values.filter((value) => Number.isFinite(value)).slice(-30)
  const low = Math.min(...actualValues)
  const high = Math.max(...actualValues)
  const points = actualValues.map((value, index) => {
    const x = 7 + (index / Math.max(1, actualValues.length - 1)) * 186
    const y = 53 - ((value - low) / (high - low || 1)) * 44
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(" ")
  const bullReady = !!bull && !bull.includes("analysis unavailable")
  const bearReady = !!bear && !bear.includes("analysis unavailable")
  const working = ["fetching", "debating", "judging"].includes(phase)

  return <section className="coin-workflow" aria-label={`${ticker} analysis workflow`} aria-busy={working}>
    <div className="section-heading"><div><span className="small-label">COIN / SIGNAL PATH</span><h2>How the decision forms</h2></div><StockSymbol ticker={ticker}/></div>
    <div className="coin-workflow-grid">
      <div className="coin-workflow-card" data-active={phase === "fetching"}>
        <div className="coin-workflow-card-head"><span>01 / GATHER</span><Database size={16}/></div>
        <div className="coin-source-map">
          <span className={sources.alpaca ? "active" : ""}><TrendingUp size={17}/>Price<small>{sources.alpaca ? "Received" : "Waiting"}</small></span>
          <span className={sources.marketaux ? "active" : ""}><Newspaper size={17}/>News<small>{sources.marketaux ? `${sources.marketaux} stories` : "No stories"}</small></span>
          <span className={sources.liquid ? "active" : ""}><BookOpen size={17}/>Memory<small>{sources.liquid ? `${sources.liquid} matches` : "No matches"}</small></span>
        </div>
        <p>Live price, cached headlines, and retrieved memory feed the analysts.</p>
      </div>
      <div className="coin-workflow-card" data-active={phase === "debating"}>
        <div className="coin-workflow-card-head"><span>02 / DEBATE</span><BrainCircuit size={16}/></div>
        <div className="coin-debate-map"><span className={bullReady ? "active" : ""}><TrendingUp size={18}/><b>Bull</b></span><ArrowRight size={18}/><span className={bearReady ? "active" : ""}><TrendingDown size={18}/><b>Bear</b></span></div>
        <p>{bullReady && bearReady ? "Both cases delivered to the judge." : "Independent upside and downside cases are being gathered."}</p>
      </div>
      <div className="coin-workflow-card" data-active={phase === "judging" || phase === "ready"}>
        <div className="coin-workflow-card-head"><span>03 / DECIDE</span><Scale size={16}/></div>
        <div className="coin-decision-map"><Scale size={21}/><ArrowRight size={17}/>{verdict ? verdict.passed ? <ShieldCheck size={21}/> : <ShieldX size={21}/> : <ShieldCheck size={21} className="muted"/>}</div>
        <p>{proposal ? verdict ? verdict.passed ? "Judge proposal passed the safety check." : "Judge proposal stopped by the safety check." : "Judge proposal ready for safety review." : "The judge and safety check follow the debate."}</p>
      </div>
    </div>
    <div className="coin-workflow-footer"><span className={working ? "coin-workflow-pulse" : ""}>{working ? `${phase.toUpperCase()} ${ticker}` : phase === "ready" ? "REVIEW READY" : phase === "blocked" ? "SAFETY CHECK BLOCKED" : phase === "error" ? "CHECK SOURCE STATUS" : "READY TO ANALYZE"}</span>
      {actualValues.length > 1 && <div className="coin-workflow-spark"><svg viewBox="0 0 200 60" role="img" aria-label={`Recent ${ticker} daily closes`}><polyline fill="none" stroke="currentColor" strokeWidth="2" points={points}/></svg><small>RECENT CLOSES</small></div>}
      {proposal && <span className="coin-workflow-confidence"><Check size={14}/>{Math.round((proposal.confidence_score || 0) * 100)}% JUDGE CONFIDENCE</span>}
    </div>
  </section>
}
