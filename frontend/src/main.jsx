import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ImageOverlay, MapContainer, Rectangle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './styles.css';
import NewApp from './App.jsx';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const prompts = ['Describe this scene', 'Highlight water and built-up regions', 'What changed between dates?'];

function FileCard({ label, hint, file, onChange, onClear }) {
  const [preview, setPreview] = useState(null);
  useEffect(() => {
    if (!file) { setPreview(null); return undefined; }
    if (!file.type.startsWith('image/') || /\.tiff?$/i.test(file.name)) { setPreview(null); return undefined; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return <div className={`file-card ${file ? 'has-file' : ''}`}>
    <div className="file-card-heading"><span className="eyebrow">{label}</span>{file && <button className="text-button" type="button" onClick={onClear}>Remove</button>}</div>
    <label className="file-drop">
      {preview ? <img src={preview} alt={`${label} preview`} /> : <span className="upload-mark">+</span>}
      <span className="file-copy"><strong>{file ? file.name : 'Drop an image here'}</strong><small>{file ? (/\.tiff?$/i.test(file.name) ? 'TIFF / server preview' : `${(file.size / 1024 / 1024).toFixed(1)} MB`) : hint}</small></span>
      <input type="file" accept="image/*,.tif,.tiff" onChange={(event) => onChange(event.target.files?.[0])} />
    </label>
  </div>;
}

function Metric({ label, value }) { return <div className="metric"><span>{label}</span><strong>{value || '--'}</strong></div>; }

function App() {
  const [first, setFirst] = useState(null); const [second, setSecond] = useState(null);
  const [query, setQuery] = useState(prompts[0]); const [result, setResult] = useState(null);
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);

  async function analyze(event) {
    event.preventDefault(); if (!first || !query.trim()) return;
    setLoading(true); setError(''); setResult(null);
    const body = new FormData(); body.append('file_1', first); if (second) body.append('file_2', second);
    body.append('query', query.trim()); body.append('include_report', 'true');
    try {
      const response = await fetch(`${API}/agent`, { method: 'POST', body }); const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'The analysis could not be completed.');
      setResult(payload);
    } catch (requestError) { setError(requestError.message || 'The analysis could not be completed.'); }
    finally { setLoading(false); }
  }

  function downloadReport() {
    const raw = atob(result.report_pdf_b64); const bytes = Uint8Array.from(raw, (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' })); const link = document.createElement('a');
    link.href = url; link.download = 'satquery-report.pdf'; link.click(); URL.revokeObjectURL(url);
  }

  const trace = result?.execution_trace || {}; const route = result?.route || {};
  const overlay = result?.overlay_b64 || result?.annotated_image_b64;
  const [sourcePreview, setSourcePreview] = useState(null);
  useEffect(() => {
    if (!first || /\.tiff?$/i.test(first.name)) { setSourcePreview(null); return undefined; }
    const url = URL.createObjectURL(first);
    setSourcePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [first]);
  const boxes = (result?.bounding_boxes || []).map((box) => {
    const coordinates = Array.isArray(box) ? box : box?.coordinates;
    if (!Array.isArray(coordinates) || coordinates.length !== 4) return null;
    return coordinates.map(Number);
  }).filter((box) => box && box.every(Number.isFinite));
  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="SatQuery home"><span className="brand-mark">SQ</span><span>SatQuery <em>AI</em></span></a><div className="system-status"><span className="status-dot" /> Analysis workspace <span className="status-divider" /> v0.1</div></header>
    <section className="intro"><div><p className="kicker">Remote sensing intelligence</p><h1>Read the landscape<br /><span>with evidence.</span></h1></div><p className="intro-copy">Upload one or two satellite images, ask a focused question, and receive a routed analysis with an auditable result.</p></section>
    <div className="workspace-grid">
      <section className="panel intake-panel"><div className="panel-header"><div><p className="section-index">01 / INPUT</p><h2>Set your scene</h2></div><span className="quiet-label">{second ? 'Paired analysis' : 'Single image'}</span></div>
        <form onSubmit={analyze}><div className="file-grid"><FileCard label="Primary image" hint="PNG, JPG, TIFF" file={first} onChange={setFirst} onClear={() => setFirst(null)} /><FileCard label="Comparison image" hint="Optional second date" file={second} onChange={setSecond} onClear={() => setSecond(null)} /></div>
          <div className="query-block"><div className="field-label"><label htmlFor="query">Question</label><span>{query.length}/240</span></div><textarea id="query" maxLength="240" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="What would you like to know?" /><div className="prompt-row">{prompts.map((prompt) => <button type="button" className={query === prompt ? 'prompt active' : 'prompt'} key={prompt} onClick={() => setQuery(prompt)}>{prompt}</button>)}</div></div>
          {error && <div className="error-message" role="alert"><strong>Analysis stopped</strong><span>{error}</span></div>}
          <button className="analyze-button" disabled={loading || !first || !query.trim()} type="submit"><span>{loading ? 'Routing analysis...' : 'Run analysis'}</span><span className="button-arrow">{loading ? '...' : '->'}</span></button>
        </form>
      </section>
      <aside className="panel result-panel"><div className="panel-header"><div><p className="section-index">02 / OUTPUT</p><h2>Analysis report</h2></div>{result && <span className="success-label">Complete</span>}</div>
        {!result && !loading && <div className="empty-state"><div className="empty-orbit"><span>+</span></div><h3>Your findings will appear here</h3><p>Start with a scene and a question to generate a visual report.</p></div>}
        {loading && <div className="empty-state loading-state"><div className="loader" /><h3>Reading your scene</h3><p>Routing to the right specialist and assembling evidence.</p></div>}
        {result && <div className="result-content"><div className="answer-block"><span className="eyebrow">Answer</span><p>{result.answer || result.detail}</p></div><div className="metrics"><Metric label="Task" value={route.task} /><Metric label="Confidence" value={result.confidence ? `${Math.round(result.confidence * 100)}%` : '--'} /><Metric label="Steps" value={trace.steps?.length} /></div><div className="trace-block"><div className="trace-heading"><span>Execution trace</span><small>{trace.fallback_active ? 'Fallback active' : 'Specialist route'}</small></div><details><summary>View route details</summary><pre>{JSON.stringify(route || trace, null, 2)}</pre></details></div>{result.report_pdf_b64 && <button className="report-button" type="button" onClick={downloadReport}>Download PDF report <span>-&gt;</span></button>}</div>}
      </aside>
    </div>
    {first && <section className="viewer-section"><div className="viewer-header"><div><p className="section-index">03 / EVIDENCE VIEW</p><h2>Spatial result</h2></div><span>{overlay ? 'Annotated output' : sourcePreview ? 'Source image' : 'Preview unavailable'}</span></div>{(overlay || sourcePreview) ? <div className="map-frame"><MapContainer className="map" center={[0, 0]} zoom={1} crs={L.CRS.Simple} scrollWheelZoom={false}><ImageOverlay url={overlay ? `data:image/png;base64,${overlay}` : sourcePreview} bounds={[[-100, -100], [100, 100]]} />{boxes.map((box, index) => <Rectangle key={index} bounds={[[100 - box[0], box[1] - 100], [100 - box[2], box[3] - 100]]} pathOptions={{ color: '#ef7657', weight: 2, fillOpacity: 0.12 }} />)}</MapContainer><div className="map-legend"><span className="legend-swatch" /> Detected region</div></div> : <div className="no-preview">TIFF evidence is processed by the API and will appear here when an annotated output is returned.</div>}</section>}
    <footer><span>SatQuery AI / Earth observation toolkit</span><span>Results are advisory and should be reviewed by an analyst.</span></footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<NewApp />);
