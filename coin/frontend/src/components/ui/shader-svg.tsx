"use client"

import { MeshGradient } from "@paper-design/shaders-react"
import { motion, useReducedMotion } from "framer-motion"
import { useEffect, useId, useRef, useState } from "react"
import { StockSymbol } from "./stock-symbols"

export type GhostMood = "idle" | "listening" | "thinking" | "speaking" | "happy" | "concerned"

const colors = ["#FFB3D9", "#87CEEB", "#4A90E2", "#2C3E50", "#1A1A2E"]
const moodNames: Record<GhostMood, string> = {
  idle: "ready", listening: "listening", thinking: "thinking", speaking: "speaking",
  happy: "ready with an answer", concerned: "needs attention",
}

export function MeshGradientSVG({ mood = "idle", ticker, compact = false }: {
  mood?: GhostMood
  ticker?: string | null
  compact?: boolean
}) {
  const clipId = `coin-ghost-${useId().replace(/:/g, "")}`
  const svgRef = useRef<SVGSVGElement>(null)
  const [eyeOffset, setEyeOffset] = useState({ x: 0, y: 0 })
  const reduced = useReducedMotion()

  useEffect(() => {
    if (reduced) return
    const handleMouseMove = (event: MouseEvent) => {
      const rect = svgRef.current?.getBoundingClientRect()
      if (!rect) return
      const x = (event.clientX - (rect.left + rect.width / 2)) * 0.08
      const y = (event.clientY - (rect.top + rect.height / 2)) * 0.08
      setEyeOffset({ x: Math.max(-8, Math.min(8, x)), y: Math.max(-8, Math.min(8, y)) })
    }
    window.addEventListener("mousemove", handleMouseMove)
    return () => window.removeEventListener("mousemove", handleMouseMove)
  }, [reduced])

  const eyeHeight = mood === "thinking" ? 22 : mood === "happy" ? 24 : 30
  const eyes = [80, 150]

  return <div className={`coin-ghost ${compact ? "coin-ghost-compact" : ""}`} role="img"
    aria-label={`Coin mascot ${moodNames[mood]}${ticker ? ` about ${ticker}` : ""}`}>
    <motion.div className="coin-ghost-float"
      animate={reduced ? undefined : { y: [0, -8, 0], scaleY: [1, 1.06, 1] }}
      transition={{ duration: mood === "thinking" ? 1.9 : 2.8, repeat: Infinity, ease: "easeInOut" }}>
      <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" width="231" height="289" viewBox="0 0 231 289">
        <defs>
          <clipPath id={clipId}>
            <path d="M230.809 115.385V249.411C230.809 269.923 214.985 287.282 194.495 288.411C184.544 288.949 175.364 285.718 168.26 280C159.746 273.154 147.769 273.461 139.178 280.23C132.638 285.384 124.381 288.462 115.379 288.462C106.377 288.462 98.1451 285.384 91.6055 280.23C82.912 273.385 70.9353 273.385 62.2415 280.23C55.7532 285.334 47.598 288.411 38.7246 288.462C17.4132 288.615 0 270.667 0 249.359V115.385C0 51.6667 51.6756 0 115.404 0C179.134 0 230.809 51.6667 230.809 115.385Z" />
          </clipPath>
        </defs>
        <foreignObject width="231" height="289" clipPath={`url(#${clipId})`}>
          <div className="coin-ghost-shader"><MeshGradient colors={colors} className="coin-ghost-mesh" speed={1} /></div>
        </foreignObject>
        {eyes.map((base) => <motion.ellipse key={base} rx="20" ry={eyeHeight} fill="#14223b"
          animate={reduced ? { cx: base, cy: 120 } : {
            cx: base + eyeOffset.x + (mood === "thinking" ? (base === 80 ? -2 : 2) : 0),
            cy: 120 + eyeOffset.y,
            scaleY: [1, 1, 0.08, 1],
          }}
          transition={reduced ? undefined : { cx: { type: "spring", stiffness: 150, damping: 15 }, cy: { type: "spring", stiffness: 150, damping: 15 }, scaleY: { duration: 3.4, repeat: Infinity, times: [0, 0.9, 0.95, 1] } }}
        />)}
        {mood === "listening" && <ellipse cx="115" cy="205" rx="7" ry="10" fill="#14223b" />}
        {mood === "speaking" && <motion.ellipse cx="115" cy="205" rx="10" fill="#14223b"
          animate={reduced ? { ry: 5 } : { ry: [4, 10, 5, 11, 4] }} transition={{ duration: 0.7, repeat: Infinity }} />}
        {mood === "thinking" && <path d="M102 207Q115 201 128 206" fill="none" stroke="#14223b" strokeWidth="5" strokeLinecap="round" />}
        {mood === "happy" && <path d="M97 201Q115 224 133 201" fill="none" stroke="#14223b" strokeWidth="6" strokeLinecap="round" />}
        {mood === "concerned" && <path d="M98 212Q115 197 132 212" fill="none" stroke="#14223b" strokeWidth="5" strokeLinecap="round" />}
        {mood === "idle" && <path d="M105 205Q115 211 125 205" fill="none" stroke="#14223b" strokeWidth="5" strokeLinecap="round" />}
      </svg>
    </motion.div>
    {ticker && <StockSymbol ticker={ticker} />}
  </div>
}
