export default function RiskConfig({ mandate, saved, busy, onChange, onSave }) {
  const fields = [
    ['allocated_capital', 'Trading Budget'],
    ['max_position_size', 'Max Per Trade'],
    ['max_loss_per_trade', 'Loss Margin / Safety Stop'],
    ['max_daily_loss', 'Daily Loss Limit'],
  ];
  return <section className="section mandate" id="risk-mandate"><div className="section-heading"><h2>Safety settings</h2><span className={'small-label ' + (saved ? 'up' : '')}>{saved ? 'SAVED' : 'UNSAVED'}</span></div>
    <form onSubmit={onSave}><div className="mandate-fields">{fields.map(([key, label]) => <label key={key}><span className="label">{label} / USD</span><input type="number" min="0.01" step="0.01" required value={mandate[key]} onChange={event => onChange(key, Number(event.target.value))}/></label>)}</div>
      <label><span className="label">Strategy Mode</span><select value={mandate.risk_style} onChange={event => onChange('risk_style', event.target.value)}><option value="capital_preservation">Capital Preservation</option><option value="conservative">Cautious</option><option value="balanced">Balanced</option><option value="growth">Growth</option><option value="high-risk">Aggressive</option></select></label>
      <label><span className="label">Order approval</span><select value={mandate.auto_execution_mode} onChange={event => onChange('auto_execution_mode', event.target.value)}><option value="observe">Research only</option><option value="recommend_approve">Approve each order</option><option value="bounded_autopilot">Bounded autopilot</option></select></label>
      <button className="secondary-button" disabled={!!busy}>{busy === 'mandate' ? 'Saving...' : 'Save safety settings'}</button>
    </form>
  </section>;
}
