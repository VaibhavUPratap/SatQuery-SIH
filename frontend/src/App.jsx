import React, { useEffect, useState } from 'react';
import { ImageOverlay, MapContainer, Rectangle } from 'react-leaflet';
import L from 'leaflet';
import { downloadPdf, getJob, login, submitJob } from './api';
import './app.css';

const stages = ['LOGIN', 'DATA', 'VALIDATION', 'CLASSIFICATION', 'ANALYSIS', 'REPORT'];

const MODES = [
  { id: 'OPTICAL_SINGLE', label: 'Single Optical', sensor: 'Sentinel-2 Optical', desc: 'Optical surface reflectance RGB / Multi-spectral GeoTIFF' },
  { id: 'SAR_SINGLE', label: 'Single SAR', sensor: 'Sentinel-1 SAR', desc: 'Synthetic Aperture Radar backscatter intensity raster' },
  { id: 'OPTICAL_SAR', label: 'Optical + SAR', sensor: 'Multi-Sensor Pair', desc: 'Co-registered Sentinel-2 (Optical) + Sentinel-1 (SAR) dual fusion' },
  { id: 'TEMPORAL', label: 'Bi-Temporal', sensor: 'Temporal Sentinel Pair', desc: 'Dual-date satellite acquisitions for change detection' },
];

function StageNav({ current, onNavigate }) {
  return (
    <nav className="stage-nav" aria-label="Analysis progress">
      {stages.map((stage, index) => (
        <button
          key={stage}
          className={current === stage ? 'stage active' : 'stage'}
          type="button"
          onClick={() => index < stages.indexOf(current) && onNavigate(stage)}
        >
          <span>{String(index + 1).padStart(2, '0')}</span>
          {stage}
        </button>
      ))}
    </nav>
  );
}

function Page({ eyebrow, title, onBack, children }) {
  return (
    <main className="page">
      <div className="page-heading">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {onBack && <button className="back-button" type="button" onClick={onBack}>Back</button>}
      </div>
      {children}
    </main>
  );
}

function FileMetaCard({ label, file, modalityHint }) {
  if (!file) return null;
  const ext = file.name.split('.').pop()?.toUpperCase() || 'UNKNOWN';
  const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
  const isTiff = /tiff?$/i.test(file.name);
  const isSar = modalityHint === 'SAR' || /sar|s1/i.test(file.name);
  const isS2 = modalityHint === 'Optical' || /s2|sentinel2|msi/i.test(file.name);
  
  const sensor = isSar ? 'Sentinel-1 C-band SAR' : isS2 ? 'Sentinel-2 MSI Optical' : (modalityHint || 'Satellite Imagery');
  const bands = isTiff ? (file.name.includes('12band') ? '12 Bands (ESA S2)' : 'Multi-band GeoTIFF') : '3-Band RGB';
  const pol = isSar ? 'Intensity (VV/VH)' : 'Optical Reflectance';

  return (
    <div className="file-meta-card">
      <div className="meta-card-header">
        <span className="badge-sensor">{sensor}</span>
        <span className="badge-status">VALID FORMAT</span>
      </div>
      <div className="meta-grid">
        <div className="meta-item"><span>File</span><strong>{file.name}</strong></div>
        <div className="meta-item"><span>Size</span><strong>{sizeMb} MB</strong></div>
        <div className="meta-item"><span>Format</span><strong>{ext}</strong></div>
        <div className="meta-item"><span>Bands/Pol</span><strong>{isSar ? pol : bands}</strong></div>
      </div>
    </div>
  );
}

function FileInput({ label, sublabel, file, modalityHint, onChange }) {
  return (
    <div className="file-input-wrapper">
      <label className={`file-input ${file ? 'selected' : ''}`}>
        <span className="field-label">
          <span>{label}</span>
          <small>{sublabel}</small>
        </span>
        <strong>{file?.name || 'Select GeoTIFF, TIFF, PNG, or JPEG'}</strong>
        <span className="input-hint">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB ready` : 'Click to browse satellite raster'}</span>
        <input type="file" accept="image/*,.tif,.tiff" onChange={(event) => onChange(event.target.files?.[0] || null)} />
      </label>
      <FileMetaCard label={label} file={file} modalityHint={modalityHint} />
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value || '--'}</strong>
    </div>
  );
}

function Trace({ result }) {
  const steps = result?.execution_trace?.steps || [];
  return (
    <section className="trace">
      <div className="section-heading">
        <span>Execution trace</span>
        <small>Backend-emitted events</small>
      </div>
      {steps.map((step, index) => (
        <div className="trace-step" key={`${step.node || 'event'}-${index}`}>
          <b className={step.status === 'failed' ? 'trace-icon failed' : 'trace-icon'}>{step.status === 'failed' ? '!' : '✓'}</b>
          <div>
            <strong>{(step.node || 'workflow event').replaceAll('_', ' ')}</strong>
            <small>{step.selected_task || step.model || step.inference_mode || step.reason || step.status || 'completed'}</small>
          </div>
        </div>
      ))}
    </section>
  );
}

function Validation({ result, onBack, onNext }) {
  const failed = result?.status === 'error';
  const steps = result?.execution_trace?.steps || [{ node: 'validate_inputs', status: failed ? 'failed' : 'passed' }];
  return (
    <Page eyebrow="02 / VALIDATION" title="Input integrity & compatibility" onBack={onBack}>
      <div className="status-banner">
        <b className={failed ? 'status-mark failed' : 'status-mark'}>{failed ? '!' : '✓'}</b>
        <div>
          <strong>{failed ? 'Validation failed' : 'Input accepted'}</strong>
          <p>{failed ? result.detail : 'The service accepted and validated the submitted satellite imagery.'}</p>
        </div>
      </div>
      <div className="check-list">
        {steps.map((step, index) => (
          <div className="check-row" key={`${step.node}-${index}`}>
            <b className={step.status === 'failed' ? 'check failed' : 'check'}>{step.status === 'failed' ? '!' : '✓'}</b>
            <span>{(step.node || 'check').replaceAll('_', ' ')}</span>
            <small>{step.status || 'passed'}</small>
          </div>
        ))}
      </div>
      {!failed && (
        <button className="primary-button" type="button" onClick={onNext}>
          Continue to classification <span>→</span>
        </button>
      )}
    </Page>
  );
}

export default function App() {
  const [stage, setStage] = useState('LOGIN');
  const [token, setToken] = useState('');
  const [uploadMode, setUploadMode] = useState('OPTICAL_SINGLE');
  const [primary, setPrimary] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [credentials, setCredentials] = useState({ username: '', password: '' });

  function handleModeChange(modeId) {
    setUploadMode(modeId);
    setPrimary(null);
    setComparison(null);
    setError('');
    if (modeId === 'OPTICAL_SAR' && !query) {
      setQuery('Identify water-covered and built-up regions using optical and SAR.');
    } else if (modeId === 'TEMPORAL' && !query) {
      setQuery('What changed between the two dates?');
    }
  }

  async function authenticate(event) {
    event.preventDefault();
    setError('');
    try {
      setToken(await login(credentials.username, credentials.password));
      setStage('DATA');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function analyze(event) {
    event.preventDefault();
    if (!primary || !query.trim()) return;
    if ((uploadMode === 'OPTICAL_SAR' || uploadMode === 'TEMPORAL') && !comparison) {
      setError(`Both files are required for ${uploadMode === 'OPTICAL_SAR' ? 'Optical + SAR' : 'Bi-Temporal'} analysis.`);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const submitted = await submitJob({ primary, comparison, query, token });
      let job = submitted;
      while (job.status === 'QUEUED' || job.status === 'PROCESSING') {
        await new Promise((resolve) => setTimeout(resolve, 500));
        job = await getJob(submitted.job_id, token);
      }
      if (job.status !== 'COMPLETED') throw new Error(job.error || 'The analysis job failed.');
      setResult(job.result);
      setStage('VALIDATION');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const route = result?.route || {};
  const overlay = result?.overlay_b64 || result?.annotated_image_b64;
  const source = primary && !/\.tiff?$/i.test(primary.name) ? URL.createObjectURL(primary) : null;
  const boxes = (result?.bounding_boxes || []).map((box) => (Array.isArray(box) ? box : box.coordinates)).filter((box) => Array.isArray(box) && box.length === 4 && box.every((v) => Number.isFinite(Number(v))));

  useEffect(() => () => source && URL.revokeObjectURL(source), [source]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top">
          <span className="brand-mark">SQ</span>
          <span>SatQuery <em>AI</em></span>
        </a>
        <span className="system-status"><i /> Remote sensing intelligence platform</span>
      </header>
      {stage !== 'LOGIN' && <StageNav current={stage} onNavigate={setStage} />}

      {stage === 'LOGIN' && (
        <Page eyebrow="SATQUERY AI / WORKSPACE" title="Remote sensing intelligence platform">
          <form className="login-panel" onSubmit={authenticate}>
            <p>Access the SatQuery analysis workspace.</p>
            <label>Username / Analyst ID
              <input required value={credentials.username} onChange={(e) => setCredentials({ ...credentials, username: e.target.value })} placeholder="analyst.demo" />
            </label>
            <label>Password
              <input required type="password" value={credentials.password} onChange={(e) => setCredentials({ ...credentials, password: e.target.value })} placeholder="satquery-demo" />
            </label>
            {error && <div className="error-message" role="alert">{error}</div>}
            <button className="primary-button">Secure login <span>→</span></button>
            <small className="disclaimer">Prototype credentials are environment-configured. No government or ISRO authentication is claimed.</small>
          </form>
        </Page>
      )}

      {stage === 'DATA' && (
        <Page eyebrow="01 / DATA INGESTION" title="Select modality & query">
          <div className="mode-selector" role="tablist" aria-label="Satellite data modality">
            {MODES.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={`mode-tab ${uploadMode === mode.id ? 'active' : ''}`}
                onClick={() => handleModeChange(mode.id)}
              >
                <strong>{mode.label}</strong>
                <small>{mode.sensor}</small>
              </button>
            ))}
          </div>

          {uploadMode === 'OPTICAL_SAR' && (
            <div className="modality-banner">
              <div className="banner-formula">
                <span className="badge-opt">OPTICAL / SENTINEL-2</span>
                <span className="plus">+</span>
                <span className="badge-sar">SAR / SENTINEL-1</span>
                <span className="equals">===</span>
                <strong className="badge-fusion">MULTI-SENSOR FUSION</strong>
              </div>
              <p>Upload co-registered Sentinel-2 Optical and Sentinel-1 SAR intensity rasters for joint spectral-backscatter analysis.</p>
            </div>
          )}

          {uploadMode === 'TEMPORAL' && (
            <div className="modality-banner">
              <div className="banner-formula">
                <span className="badge-opt">ACQUISITION T1 (BEFORE)</span>
                <span className="plus">vs</span>
                <span className="badge-opt">ACQUISITION T2 (AFTER)</span>
                <span className="equals">===</span>
                <strong className="badge-fusion">BI-TEMPORAL CHANGE</strong>
              </div>
              <p>Upload dual-date co-registered satellite rasters to detect deforestation, urban expansion, or reservoir depletion.</p>
            </div>
          )}

          <form className="data-form" onSubmit={analyze}>
            <div className="file-grid">
              {uploadMode === 'OPTICAL_SINGLE' && (
                <FileInput label="Sentinel-2 Optical Raster" sublabel="RGB / 12-BAND GEOTIFF" file={primary} modalityHint="Optical" onChange={setPrimary} />
              )}
              {uploadMode === 'SAR_SINGLE' && (
                <FileInput label="Sentinel-1 SAR Raster" sublabel="BACKSCATTER INTENSITY" file={primary} modalityHint="SAR" onChange={setPrimary} />
              )}
              {uploadMode === 'OPTICAL_SAR' && (
                <>
                  <FileInput label="Optical / Sentinel-2" sublabel="SURFACE REFLECTANCE" file={primary} modalityHint="Optical" onChange={setPrimary} />
                  <FileInput label="SAR / Sentinel-1" sublabel="RADAR BACKSCATTER" file={comparison} modalityHint="SAR" onChange={setComparison} />
                </>
              )}
              {uploadMode === 'TEMPORAL' && (
                <>
                  <FileInput label="Image / Date T1" sublabel="EARLIER ACQUISITION" file={primary} modalityHint="Optical" onChange={setPrimary} />
                  <FileInput label="Image / Date T2" sublabel="LATER ACQUISITION" file={comparison} modalityHint="Optical" onChange={setComparison} />
                </>
              )}
            </div>

            <label className="query-field">
              <span className="field-label">Analysis query <small>{query.length}/240</small></span>
              <textarea maxLength="240" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Enter a focused question about features, surface characteristics, or temporal changes" />
            </label>

            {error && <div className="error-message" role="alert">{error}</div>}

            <button className="primary-button" disabled={loading || !primary || !query.trim() || ((uploadMode === 'OPTICAL_SAR' || uploadMode === 'TEMPORAL') && !comparison)}>
              {loading ? 'Submitting analysis...' : 'Analyze imagery'} <span>→</span>
            </button>
          </form>
        </Page>
      )}

      {stage === 'VALIDATION' && <Validation result={result} onBack={() => setStage('DATA')} onNext={() => setStage('CLASSIFICATION')} />}

      {stage === 'CLASSIFICATION' && (
        <Page eyebrow="03 / CLASSIFICATION" title="Task classification" onBack={() => setStage('VALIDATION')}>
          <div className="classification">
            <span className="eyebrow">Detected task</span>
            <strong className="task-name">{route.task || 'Unknown'}</strong>
            <p>{route.reason || 'No routing reason was returned.'}</p>
            <div className="detail-grid">
              <Metric label="Required inputs" value={comparison ? 'Paired imagery' : 'Single image'} />
              <Metric label="Workflow" value={route.task} />
              <Metric label="Confidence" value={result?.confidence ? `${Math.round(result.confidence * 100)}%` : 'Not emitted'} />
            </div>
          </div>
          <Trace result={result} />
          <button className="primary-button" type="button" onClick={() => setStage('ANALYSIS')}>View analysis <span>→</span></button>
        </Page>
      )}

      {stage === 'ANALYSIS' && (
        <Page eyebrow="04 / ANALYSIS" title="Analysis result" onBack={() => setStage('CLASSIFICATION')}>
          <div className="answer-card">
            <span className="eyebrow">Final answer</span>
            <p>{result?.answer || result?.detail || 'No answer returned.'}</p>
          </div>
          <div className="detail-grid">
            <Metric label="Detected task" value={route.task} />
            <Metric label="Confidence" value={result?.confidence ? `${Math.round(result.confidence * 100)}%` : '--'} />
            <Metric label="Inference" value={result?.execution_trace?.steps?.at(-1)?.inference_mode || 'Specialist'} />
          </div>
          {(overlay || source) && (
            <div className="map-frame">
              <MapContainer className="map" center={[0, 0]} zoom={1} crs={L.CRS.Simple} scrollWheelZoom={false}>
                <ImageOverlay url={overlay ? `data:image/png;base64,${overlay}` : source} bounds={[[-100, -100], [100, 100]]} />
                {boxes.map((box, index) => (
                  <Rectangle key={index} bounds={[[100 - box[0], box[1] - 100], [100 - box[2], box[3] - 100]]} pathOptions={{ color: '#d9694b', weight: 2 }} />
                ))}
              </MapContainer>
            </div>
          )}
          <Trace result={result} />
          <button className="primary-button" type="button" onClick={() => setStage('REPORT')}>Prepare report <span>→</span></button>
        </Page>
      )}

      {stage === 'REPORT' && (
        <Page eyebrow="05 / REPORT" title="Evidence report" onBack={() => setStage('ANALYSIS')}>
          <div className="report-sheet">
            <span className="eyebrow">SatQuery AI / analysis record</span>
            <Metric label="Query" value={query} />
            <Metric label="Task" value={route.task} />
            <Metric label="Confidence" value={result?.confidence ? `${Math.round(result.confidence * 100)}%` : '--'} />
            <div className="report-answer">{result?.answer}</div>
            <Trace result={result} />
          </div>
          <div className="button-row">
            <button className="secondary-button" type="button" disabled={!result?.report_pdf_b64} onClick={() => downloadPdf(result.report_pdf_b64)}>Download PDF</button>
            <button className="primary-button" type="button" onClick={() => { setResult(null); setPrimary(null); setComparison(null); setQuery(''); setStage('DATA'); }}>New analysis <span>→</span></button>
          </div>
        </Page>
      )}

      <footer>SatQuery AI / Earth observation toolkit <span>Results are advisory and should be reviewed by an analyst.</span></footer>
    </div>
  );
}
