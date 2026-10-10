import type { LucideIcon } from "lucide-react"
import { Activity, Apple, ChartNoAxesCombined, Cloud, Cpu, Landmark, PanelsTopLeft, ShoppingBag, Zap } from "lucide-react"

const STOCKS: Record<string, { name: string; Icon: LucideIcon; color: string }> = {
  NVDA: { name: "Nvidia", Icon: Cpu, color: "#b5ed88" },
  AAPL: { name: "Apple", Icon: Apple, color: "#f0d8e3" },
  MSFT: { name: "Microsoft", Icon: PanelsTopLeft, color: "#93c9f5" },
  AMZN: { name: "Amazon", Icon: ShoppingBag, color: "#ffd090" },
  TSLA: { name: "Tesla", Icon: Zap, color: "#f2a4a4" },
  SPY: { name: "S&P 500 ETF", Icon: ChartNoAxesCombined, color: "#c6b7f2" },
  QQQ: { name: "Nasdaq 100 ETF", Icon: Cloud, color: "#a0dce5" },
  DIA: { name: "Dow Jones ETF", Icon: Landmark, color: "#e6d09e" },
}

export function stockIdentity(ticker?: string | null) {
  const symbol = (ticker || "").toUpperCase()
  return STOCKS[symbol] || { name: symbol || "Market", Icon: Activity, color: "#d8ed88" }
}

export function StockSymbol({ ticker, label = true, size = 16 }: { ticker?: string | null; label?: boolean; size?: number }) {
  const { name, Icon, color } = stockIdentity(ticker)
  return <span className="coin-stock-symbol" style={{ color }} title={name}>
    <Icon size={size} aria-hidden="true" />
    {label && <span>{ticker || "US market"}</span>}
  </span>
}
