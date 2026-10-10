import { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Volume2, X } from 'lucide-react';
import { api } from '../services/api';

const STEP_LABELS = {
  opportunities: 'Compare candidates',
  market_news: 'Review new and stored news',
  price_history: 'Inspect price history',
  research: 'Run the bull / bear review',
  risk_mandate: 'Check your risk limits',
};
const STEP_TARGETS = {
  opportunities: 'opportunities',
  market_news: 'market-news',
  price_history: 'price-history',
  research: 'research',
  risk_mandate: 'risk-mandate',
};

function speak(text) {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text) return;
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(text);
  speech.rate = 1.02;
  window.speechSynthesis.speak(speech);
}

export default function VoiceGuide({ open, onClose, opportunities, newsFilters, onSelectSymbol }) {
  const [recording, setRecording] = useState(false);
  const [working, setWorking] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [plan, setPlan] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState('');
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const stopTimerRef = useRef(null);

  useEffect(() => () => {
    clearTimeout(stopTimerRef.current);
    streamRef.current?.getTracks().forEach(track => track.stop());
    if (typeof window !== 'undefined') window.speechSynthesis?.cancel();
  }, []);

  function showStep(nextPlan, index) {
    const steps = nextPlan?.steps || [];
    const bounded = Math.max(0, Math.min(index, steps.length - 1));
    setStepIndex(bounded);
    const symbol = nextPlan?.symbols?.[Math.min(bounded, nextPlan.symbols.length - 1)];
    if (symbol) onSelectSymbol(symbol);
    const target = document.getElementById(STEP_TARGETS[steps[bounded]]);
    target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  async function runGuide(text) {
    const clean = text.trim();
    if (!clean) return;
    setWorking(true); setError(''); setPlan(null);
    try {
      const next = await api.guide(clean, newsFilters);
      setPlan(next); setStepIndex(0);
      speak(next.spoken_summary);
      if (next.valid) setTimeout(() => showStep(next, 0), 150);
    } catch (requestError) { setError(requestError.message); }
    finally { setWorking(false); }
  }

  function stopRecording() {
    clearTimeout(stopTimerRef.current);
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
  }

  async function toggleRecording() {
    if (recording) { stopRecording(); return; }
    setError(''); setPlan(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Microphone recording is not supported here. Type the request below.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferred = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const recorder = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined);
      streamRef.current = stream; recorderRef.current = recorder; chunksRef.current = [];
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach(track => track.stop());
        setWorking(true);
        try {
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
          const result = await api.transcribe(blob);
          setPrompt(result.text);
          await runGuide(result.text);
        } catch (requestError) { setError(requestError.message); setWorking(false); }
      };
      recorder.start(); setRecording(true);
      stopTimerRef.current = setTimeout(stopRecording, 20000);
    } catch (mediaError) {
      setError(mediaError?.name === 'NotAllowedError' ? 'Microphone access was denied. Allow access or type the request below.' : 'The microphone could not start. Type the request below.');
    }
  }

  if (!open) return null;
  const matches = (opportunities?.candidates || []).filter(item => plan?.symbols?.includes(item.symbol));
  const maxReturn = Math.max(1, ...matches.map(item => item.return_20d_pct));
  const currentStep = plan?.steps?.[stepIndex];

  return <div className="guide-shell" role="dialog" aria-modal="true" aria-label="Coin voice guide">
    <div className="guide-head"><div><span className="small-label">GUIDED WORKSPACE</span><h2>Ask Coin</h2></div><button className="guide-close" onClick={onClose} aria-label="Close guide"><X size={18}/></button></div>
    <p className="guide-copy">Ask about an amount, time horizon, stability, or stock risk. Coin will move through the relevant charts and controls.</p>
    <button className={`guide-mic ${recording ? 'recording' : ''}`} onClick={toggleRecording} disabled={working} aria-label={recording ? 'Stop recording' : 'Start voice guide'}>{recording ? <MicOff size={22}/> : <Mic size={22}/>}<span>{recording ? 'Listening — tap to finish' : working ? 'Working…' : 'Ask with your microphone'}</span></button>
    <form className="guide-form" onSubmit={event => { event.preventDefault(); runGuide(prompt); }}><input value={prompt} maxLength={500} onChange={event => setPrompt(event.target.value)} placeholder="Or type: How should I explore investing $100 long term?" aria-label="Guided investing request"/><button disabled={working || !prompt.trim()}>Guide me</button></form>
    {error && <p className="guide-error" role="alert">{error}</p>}
    {plan && <div className={`guide-result ${plan.valid ? '' : 'invalid'}`}><div className="guide-summary"><p>{plan.spoken_summary}</p><button onClick={() => speak(plan.spoken_summary)} aria-label="Read guidance aloud"><Volume2 size={17}/></button></div>
      {plan.valid && <>{matches.length > 0 && <div className="guide-bars">{matches.map(item => { const allocation = plan.allocations?.find(value => value.symbol === item.symbol); return <button key={item.symbol} onClick={() => onSelectSymbol(item.symbol)}><span><b>{item.symbol}</b><em>20-session return {item.return_20d_pct > 0 ? '+' : ''}{item.return_20d_pct}%</em></span><i><u style={{ width: `${allocation ? allocation.percent : Math.max(5, item.return_20d_pct / maxReturn * 100)}%` }}/></i><small>{allocation ? `$${allocation.amount.toLocaleString()} of the stated budget · ${allocation.percent}% · ${allocation.fractional_shares_reference} fractional-share reference` : `Risk-sized reference: ${item.shares} shares / $${item.estimated_cost.toLocaleString()}`}</small></button>})}</div>}
      <ul className="guide-points">{plan.key_points.map(point => <li key={point}>{point}</li>)}</ul>
      {plan.news_points?.length > 0 && <div className="guide-news"><span className="small-label">NEWS IN THIS GUIDE</span>{plan.news_points.map(point => <p key={point}>{point}</p>)}</div>}
      {plan.steps.length > 0 && <div className="guide-progress"><span>{stepIndex + 1} / {plan.steps.length} · {STEP_LABELS[currentStep]}</span><div><button disabled={stepIndex === 0} onClick={() => showStep(plan, stepIndex - 1)}>Back</button><button onClick={() => stepIndex === plan.steps.length - 1 ? onClose() : showStep(plan, stepIndex + 1)}>{stepIndex === plan.steps.length - 1 ? 'Finish' : 'Next insight'}</button></div></div>}</>}
    </div>}
    <p className="guide-note">Voice is transcribed by Groq Whisper. Guidance uses current watchlist data and never submits an order.</p>
  </div>;
}
