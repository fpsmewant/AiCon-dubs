import { useEffect, useRef, useState } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Mic, MicOff, Volume2, X, ArrowUpRight, ShieldCheck, ShieldX } from 'lucide-react';
import { api } from '../services/api';

function speak(text) {
  if (!window.speechSynthesis || !text) return;
  window.speechSynthesis.cancel();
  const voice = new SpeechSynthesisUtterance(text);
  voice.rate = 1.04;
  window.speechSynthesis.speak(voice);
}

export default function VoiceGuide({ open, onClose, onSelectSymbol, onDeploy, busy, canDeploy }) {
  const [recording, setRecording] = useState(false);
  const [working, setWorking] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState('');
  const recorder = useRef(null);
  const stream = useRef(null);
  const chunks = useRef([]);
  const timer = useRef(null);

  useEffect(() => () => {
    clearTimeout(timer.current);
    stream.current?.getTracks().forEach(track => track.stop());
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    if (!open || !prompt.trim()) return;
    const timeout = setTimeout(() => api.mention(prompt).catch(() => {}), 350);
    return () => clearTimeout(timeout);
  }, [prompt, open]);

  async function ask(text) {
    if (!text.trim()) return;
    setWorking(true); setError(''); setAnswer(null);
    try {
      const result = await api.ask(text.trim());
      setAnswer(result);
      if (result.ticker) onSelectSymbol(result.ticker);
      speak(result.speech_text);
    } catch (failure) { setError(failure.message); }
    finally { setWorking(false); }
  }

  function stopRecording() {
    clearTimeout(timer.current);
    if (recorder.current?.state === 'recording') recorder.current.stop();
  }

  async function toggleRecording() {
    if (recording) { stopRecording(); return; }
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Microphone recording is unavailable. Type your question below.'); return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      const format = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const next = new MediaRecorder(media, format ? { mimeType: format } : undefined);
      recorder.current = next; stream.current = media; chunks.current = [];
      next.ondataavailable = event => { if (event.data.size) chunks.current.push(event.data); };
      next.onstop = async () => {
        setRecording(false); media.getTracks().forEach(track => track.stop()); setWorking(true);
        try {
          const result = await api.transcribe(new Blob(chunks.current, { type: next.mimeType || 'audio/webm' }));
          setPrompt(result.text);
          api.mention(result.text).catch(() => {});
          await ask(result.text);
        } catch (failure) { setError(failure.message); setWorking(false); }
      };
      next.start(); setRecording(true); timer.current = setTimeout(stopRecording, 20000);
    } catch (failure) { setError(failure?.name === 'NotAllowedError' ? 'Microphone permission was denied.' : 'The microphone could not start.'); }
  }

  if (!open) return null;
  return <div className="guide-shell" role="dialog" aria-modal="true" aria-label="Ask Coin">
    <div className="guide-head"><div><span className="small-label">COIN INTELLIGENCE</span><h2>Ask Coin</h2></div><button className="guide-close" onClick={onClose} aria-label="Close guide"><X size={18}/></button></div>
    <p className="guide-copy">Ask about a stock, today’s market, or a specific paper trading budget.</p>
    <button className={`guide-mic ${recording ? 'recording' : ''}`} onClick={toggleRecording} disabled={working}>{recording ? <MicOff size={21}/> : <Mic size={21}/>} {recording ? 'Listening · tap to finish' : working ? 'Building your view…' : 'Ask with your microphone'}</button>
    <form className="guide-form" onSubmit={event => { event.preventDefault(); ask(prompt); }}><input value={prompt} maxLength={500} onChange={event => setPrompt(event.target.value)} placeholder="Should I invest $100 in Nvidia?" aria-label="Market question"/><button disabled={working || !prompt.trim()}>Explore</button></form>
    {error && <p className="guide-error" role="alert">{error}</p>}
    {answer && <div className="guide-result"><div className="guide-summary"><p>{answer.speech_text}</p><button onClick={() => speak(answer.speech_text)} aria-label="Read aloud"><Volume2 size={17}/></button></div>
      {answer.ticker && <div className="guide-asset"><div><span className="small-label">STOCK IN FOCUS</span><h3>{answer.ticker}</h3></div>{answer.requested_amount && <b>${answer.requested_amount.toFixed(2)} budget</b>}</div>}
      {answer.chart_data?.length > 0 && <div className="guide-mini-chart" aria-label="30 day price chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={answer.chart_data}><defs><linearGradient id="guideFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d8ed88" stopOpacity={0.3}/><stop offset="100%" stopColor="#d8ed88" stopOpacity={0}/></linearGradient></defs><Tooltip contentStyle={{background:'#171b1e',border:'1px solid #526044'}} formatter={value => [`$${Number(value).toFixed(2)}`, 'Close']}/><Area dataKey="close" stroke="#d8ed88" fill="url(#guideFill)" strokeWidth={2}/></AreaChart></ResponsiveContainer></div>}
      <div className="guide-procon"><div><h4>Merits</h4>{answer.pros?.length ? answer.pros.map((item, i) => <p key={i}>{item}</p>) : <p>No verified upside drivers in current context.</p>}</div><div><h4>Risks</h4>{answer.cons?.length ? answer.cons.map((item, i) => <p key={i}>{item}</p>) : <p>Review volatility and market conditions.</p>}</div></div>
      {answer.requested_amount && <div className={`guide-safety ${answer.firewall_status?.passed ? 'passed' : 'rejected'}`}>{answer.firewall_status?.passed ? <ShieldCheck size={17}/> : <ShieldX size={17}/>}<span>{answer.firewall_status?.passed ? 'Safety check passed' : answer.firewall_status?.reasons?.join(' · ')}</span></div>}
      {answer.proposal && <button className="guide-deploy" disabled={!canDeploy || !answer.firewall_status?.passed || working || !!busy} onClick={() => onDeploy(answer.proposal)}>Deploy ${answer.requested_amount?.toFixed(2)} paper order <ArrowUpRight size={17}/></button>}
    </div>}
    <p className="guide-note">Market data and AI analysis can be incomplete. Orders use your saved limits and Alpaca paper account.</p>
  </div>;
}
