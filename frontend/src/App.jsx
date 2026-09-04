import React, { useEffect, useState } from 'react';
import { ImageOverlay, MapContainer, Rectangle } from 'react-leaflet';
import L from 'leaflet';
import { downloadPdf, getJob, login, submitJob } from './api';
import './app.css';

const stages = ['LOGIN', 'DATA', 'VALIDATION', 'CLASSIFICATION', 'ANALYSIS', 'REPORT'];

const MODES = [
  {
    id: 'OPTICAL_SINGLE',
    label: 'Single Optical',
    icon: '◉',
    sensor: 'Sentinel-2 Optical',
    desc: 'Optical surface reflectance RGB / Multi-spectral GeoTIFF',
  },
  {
    id: 'SAR_SINGLE',
    label: 'Single SAR',
    icon: '◈',
    sensor: 'Sentinel-1 SAR',
    desc: 'Synthetic Aperture Radar backscatter intensity raster',
  },
  {
    id: 'OPTICAL_SAR',
    label: 'Optical + SAR',
    icon: '⊕',
    sensor: 'Multi-Sensor Pair',
    desc: 'Co-registered Sentinel-2 (Optical) + Sentinel-1 (SAR) dual fusion',
  },
  {
    id: 'TEMPORAL',
    label: 'Bi-Temporal',
    icon: '⊘',
    sensor: 'Temporal Sentinel Pair',
    desc: 'Dual-date satellite acquisitions for change detection',
  },
];

/* ── Stage Navigation ─────────────────────────────────────────── */
function StageNav({ current, onNavigate }) {
  const currentIndex = stages.indexOf(current);
  // Skip LOGIN in displayed nav
  const navStages = stages.slice(1);

  return (
    <nav className="stage-nav" aria-label="Analysis progress">
      {navStages.map((stage, index) => {
        const absoluteIndex = index + 1;
        const isActive = current === stage;
        const isCompleted = absoluteIndex < currentIndex;
        const className = ['stage', isActive && 'active', isCompleted && 'completed']
          .filter(Boolean)
          .join(' ');

        return (
          <React.Fragment key={stage}>
            <button
              className={className}
              type="button"
              onClick={() => isCompleted && onNavigate(stage)}
              aria-current={isActive ? 'step' : undefined}
            >
              <span aria-hidden="true">
                {isCompleted ? '✓' : String(absoluteIndex).padStart(2, '0')}
              </span>
              {stage}
            </button>
            {index < navStages.length - 1 && (
              <div
                className="stage-connector"
                aria-hidden="true"
                style={isCompleted ? { background: 'var(--accent-green-dim)' } : {}}
              />
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

/* ── Page Wrapper ─────────────────────────────────────────────── */
function Page({ eyebrow, title, onBack, children }) {
  return (
    <main className="page">
      <div className="page-heading">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {onBack && (
          <button className="back-button" type="button" onClick={onBack}>
            ← Back
          </button>
        )}
      </div>
      {children}
    </main>
  );
}

/* ── File Meta Card ───────────────────────────────────────────── */
function FileMetaCard({ label, file, modalityHint }) {
  if (!file) return null;
  const ext = file.name.split('.').pop()?.toUpperCase() || 'UNKNOWN';
  const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
  const isTiff = /tiff?$/i.test(file.name);
  const isSar = modalityHint === 'SAR' || /sar|s1/i.test(file.name);
  const isS2 = modalityHint === 'Optical' || /s2|sentinel2|msi/i.test(file.name);

  const sensor = isSar
    ? 'Sentinel-1 C-band SAR'
    : isS2
    ? 'Sentinel-2 MSI Optical'
    : modalityHint || 'Satellite Imagery';
  const bands = isTiff
    ? file.name.includes('12band')
      ? '12 Bands (ESA S2)'
      : 'Multi-band GeoTIFF'
    : '3-Band RGB';
  const pol = isSar ? 'Intensity (VV/VH)' : 'Optical Reflectance';

  return (
    <div className="file-meta-card">
      <div className="meta-card-header">
        <span className="badge-sensor">{sensor}</span>
        <span className="badge-status">✓ Valid format</span>
      </div>
      <div className="meta-grid">
        <div className="meta-item">
          <span>File</span>
          <strong>{file.name}</strong>
        </div>
        <div className="meta-item">
          <span>Size</span>
          <strong>{sizeMb} MB</strong>
        </div>
        <div className="meta-item">
          <span>Format</span>
          <strong>{ext}</strong>
        </div>
        <div className="meta-item">
          <span>Bands/Pol</span>
          <strong>{isSar ? pol : bands}</strong>
        </div>
      </div>
    </div>
  );
}

/* ── File Input ───────────────────────────────────────────────── */
function FileInput({ label, sublabel, file, modalityHint, onChange }) {
  const [dragging, setDragging] = useState(false);

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onChange(dropped);
  }

  return (
    <div className="file-input-wrapper">
      <label
        className={['file-input', file ? 'selected' : '', dragging ? 'dragging' : '']
          .filter(Boolean)
          .join(' ')}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <span className="field-label">
          <span>{label}</span>
          <small>{sublabel}</small>
        </span>
        <strong>{file?.name || 'Drop or click to select file'}</strong>
        <span className="input-hint">
          {file
            ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready for analysis`
            : 'GeoTIFF · TIFF · PNG · JPEG accepted'}
        </span>
        <input
          type="file"
          accept="image/*,.tif,.tiff"
          onChange={(event) => onChange(event.target.files?.[0] || null)}
        />
      </label>
      <FileMetaCard label={label} file={file} modalityHint={modalityHint} />
    </div>
  );
}

/* ── Metric ───────────────────────────────────────────────────── */
function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value || '--'}</strong>
    </div>
  );
}

/* ── Execution Trace ──────────────────────────────────────────── */
function Trace({ result }) {
  const steps = result?.execution_trace?.steps || [];
  if (steps.length === 0) return null;

  return (
    <section className="trace">
      <div className="section-heading">
        <span>Execution trace</span>
        <small>{steps.length} step{steps.length !== 1 ? 's' : ''} · backend-emitted</small>
      </div>
      {steps.map((step, index) => (
        <div
          className="trace-step"
          key={`${step.node || 'event'}-${index}`}
        >
          <b
            className={
              step.status === 'failed' ? 'trace-icon failed' : 'trace-icon'
            }
            aria-label={step.status === 'failed' ? 'Failed' : 'Passed'}
          >
            {step.status === 'failed' ? '!' : '✓'}
          </b>
          <div>
            <strong>{(step.node || 'workflow event').replaceAll('_', ' ')}</strong>
            <small>
              {step.selected_task ||
                step.model ||
                step.inference_mode ||
                step.reason ||
                step.status ||
                'completed'}
            </small>
          </div>
        </div>
      ))}
    </section>
  );
}

/* ── Validation Page ──────────────────────────────────────────── */
function Validation({ result, onBack, onNext }) {
  const failed = result?.status === 'error';
  const steps = result?.execution_trace?.steps || [
    { node: 'validate_inputs', status: failed ? 'failed' : 'passed' },
  ];

  return (
    <Page eyebrow="02 / VALIDATION" title="Input integrity & compatibility" onBack={onBack}>
      <div className={`status-banner ${failed ? 'failed-banner' : ''}`}>
        <b className={failed ? 'status-mark failed' : 'status-mark'}>
          {failed ? '!' : '✓'}
        </b>
        <div>
          <strong>{failed ? 'Validation failed' : 'Input accepted'}</strong>
          <p>
            {failed
              ? result.detail
              : 'The service accepted and validated the submitted satellite imagery. All bands and projections are compatible.'}
          </p>
        </div>
      </div>

      <div className="check-list">
        {steps.map((step, index) => (
          <div className="check-row" key={`${step.node}-${index}`}>
            <b className={step.status === 'failed' ? 'check failed' : 'check'}>
              {step.status === 'failed' ? '!' : '✓'}
            </b>
            <span>{(step.node || 'check').replaceAll('_', ' ')}</span>
            <small>{step.status || 'passed'}</small>
          </div>
        ))}
      </div>

      {!failed && (
        <button className="primary-button" type="button" onClick={onNext}>
          <span>Continue to classification</span>
          <span>→</span>
        </button>
      )}
    </Page>
  );
}

/* ── Loading Overlay ──────────────────────────────────────────── */
function LoadingSpinner({ stage: loadStage }) {
  const messages = [
    'Routing to specialist model…',
    'Parsing satellite bands…',
    'Running inference pipeline…',
    'Assembling evidence…',
  ];
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % messages.length);
    }, 1800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="loading-overlay" role="status" aria-live="polite">
      <div className="loading-ring">
        <div className="loading-ring-inner" />
        <span className="loading-icon">◉</span>
      </div>
      <p className="loading-message">{messages[msgIndex]}</p>
      <small className="loading-hint">
        Large images may take up to 30 seconds
      </small>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   Root App Component
══════════════════════════════════════════════════════════════════ */
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
    if (
      (uploadMode === 'OPTICAL_SAR' || uploadMode === 'TEMPORAL') &&
      !comparison
    ) {
      setError(
        `Both files are required for ${
          uploadMode === 'OPTICAL_SAR' ? 'Optical + SAR' : 'Bi-Temporal'
        } analysis.`
      );
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
      if (job.status !== 'COMPLETED')
        throw new Error(job.error || 'The analysis job failed.');
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
  const source =
    primary && !/\.tiff?$/i.test(primary.name)
      ? URL.createObjectURL(primary)
      : null;
  const boxes = (result?.bounding_boxes || [])
    .map((box) => (Array.isArray(box) ? box : box.coordinates))
    .filter(
      (box) =>
        Array.isArray(box) &&
        box.length === 4 &&
        box.every((v) => Number.isFinite(Number(v)))
    );

  useEffect(() => () => source && URL.revokeObjectURL(source), [source]);

  const activeMode = MODES.find((m) => m.id === uploadMode);

  return (
    <div className="app-shell">
      {/* ── Top Bar ──────────────────────────────────────────────── */}
      <header className="topbar">
        <a className="brand" href="#top" aria-label="SatQuery AI home">
          <span className="brand-mark" aria-hidden="true">SQ</span>
          <span>SatQuery <em>AI</em></span>
        </a>
        <span className="system-status" role="status">
          <i aria-hidden="true" />
          Remote sensing intelligence platform
        </span>
      </header>

      {/* ── Stage Progress Nav ────────────────────────────────────── */}
      {stage !== 'LOGIN' && (
        <StageNav current={stage} onNavigate={setStage} />
      )}

      {/* ══════════════════════════════════════════════════════════
          LOGIN
      ══════════════════════════════════════════════════════════ */}
      {stage === 'LOGIN' && (
        <Page
          eyebrow="SatQuery AI / Workspace"
          title="Earth observation analysis platform"
        >
          <form className="login-panel" onSubmit={authenticate} noValidate>
            <p>
              Access the SatQuery analysis workspace. Upload satellite imagery and
              run AI-powered geospatial analysis with an auditable execution trace.
            </p>

            <label>
              Username / Analyst ID
              <input
                required
                autoComplete="username"
                value={credentials.username}
                onChange={(e) =>
                  setCredentials({ ...credentials, username: e.target.value })
                }
                placeholder="analyst.demo"
              />
            </label>

            <label>
              Password
              <input
                required
                type="password"
                autoComplete="current-password"
                value={credentials.password}
                onChange={(e) =>
                  setCredentials({ ...credentials, password: e.target.value })
                }
                placeholder="satquery-demo"
              />
            </label>

            {error && (
              <div className="error-message" role="alert">
                {error}
              </div>
            )}

            <button className="primary-button" type="submit">
              <span>Secure login</span>
              <span>→</span>
            </button>

            <small className="disclaimer">
              Prototype credentials are environment-configured. No government or
              ISRO authentication is claimed.
            </small>
          </form>
        </Page>
      )}

      {/* ══════════════════════════════════════════════════════════
          DATA INGESTION
      ══════════════════════════════════════════════════════════ */}
      {stage === 'DATA' && (
        <Page eyebrow="01 / Data Ingestion" title="Select modality & query">

          {/* Mode Tabs */}
          <div
            className="mode-selector"
            role="tablist"
            aria-label="Satellite data modality"
          >
            {MODES.map((mode) => (
              <button
                key={mode.id}
                type="button"
                role="tab"
                aria-selected={uploadMode === mode.id}
                className={`mode-tab ${uploadMode === mode.id ? 'active' : ''}`}
                onClick={() => handleModeChange(mode.id)}
              >
                <span className="mode-tab-icon" aria-hidden="true">
                  {mode.icon}
                </span>
                <strong>{mode.label}</strong>
                <small>{mode.sensor}</small>
              </button>
            ))}
          </div>

          {/* Modality Banner */}
          {uploadMode === 'OPTICAL_SAR' && (
            <div className="modality-banner" role="note">
              <div className="banner-formula">
                <span className="badge-opt">Optical / Sentinel-2</span>
                <span className="plus">+</span>
                <span className="badge-sar">SAR / Sentinel-1</span>
                <span className="equals">===</span>
                <strong className="badge-fusion">Multi-Sensor Fusion</strong>
              </div>
              <p>
                Upload co-registered Sentinel-2 Optical and Sentinel-1 SAR
                intensity rasters for joint spectral-backscatter analysis.
              </p>
            </div>
          )}

          {uploadMode === 'TEMPORAL' && (
            <div className="modality-banner" role="note">
              <div className="banner-formula">
                <span className="badge-opt">Acquisition T1 (Before)</span>
                <span className="plus">vs</span>
                <span className="badge-opt">Acquisition T2 (After)</span>
                <span className="equals">===</span>
                <strong className="badge-fusion">Bi-Temporal Change</strong>
              </div>
              <p>
                Upload dual-date co-registered satellite rasters to detect
                deforestation, urban expansion, or reservoir depletion.
              </p>
            </div>
          )}

          {/* Form */}
          <form className="data-form" onSubmit={analyze} noValidate>
            <div className="file-grid">
              {uploadMode === 'OPTICAL_SINGLE' && (
                <FileInput
                  label="Sentinel-2 Optical Raster"
                  sublabel="RGB / 12-Band GeoTIFF"
                  file={primary}
                  modalityHint="Optical"
                  onChange={setPrimary}
                />
              )}
              {uploadMode === 'SAR_SINGLE' && (
                <FileInput
                  label="Sentinel-1 SAR Raster"
                  sublabel="Backscatter Intensity"
                  file={primary}
                  modalityHint="SAR"
                  onChange={setPrimary}
                />
              )}
              {uploadMode === 'OPTICAL_SAR' && (
                <>
                  <FileInput
                    label="Optical / Sentinel-2"
                    sublabel="Surface Reflectance"
                    file={primary}
                    modalityHint="Optical"
                    onChange={setPrimary}
                  />
                  <FileInput
                    label="SAR / Sentinel-1"
                    sublabel="Radar Backscatter"
                    file={comparison}
                    modalityHint="SAR"
                    onChange={setComparison}
                  />
                </>
              )}
              {uploadMode === 'TEMPORAL' && (
                <>
                  <FileInput
                    label="Image / Date T1"
                    sublabel="Earlier Acquisition"
                    file={primary}
                    modalityHint="Optical"
                    onChange={setPrimary}
                  />
                  <FileInput
                    label="Image / Date T2"
                    sublabel="Later Acquisition"
                    file={comparison}
                    modalityHint="Optical"
                    onChange={setComparison}
                  />
                </>
              )}
            </div>

            <label className="query-field">
              <span className="field-label">
                Analysis query
                <small>{query.length}/240</small>
              </span>
              <textarea
                maxLength="240"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a focused question about features, surface characteristics, or temporal changes…"
              />
            </label>

            {error && (
              <div className="error-message" role="alert">
                {error}
              </div>
            )}

            {loading && <LoadingSpinner />}

            <button
              className="primary-button"
              type="submit"
              disabled={
                loading ||
                !primary ||
                !query.trim() ||
                ((uploadMode === 'OPTICAL_SAR' || uploadMode === 'TEMPORAL') &&
                  !comparison)
              }
            >
              <span>
                {loading ? 'Submitting analysis…' : 'Analyse imagery'}
              </span>
              <span>{loading ? '…' : '→'}</span>
            </button>
          </form>
        </Page>
      )}

      {/* ══════════════════════════════════════════════════════════
          VALIDATION
      ══════════════════════════════════════════════════════════ */}
      {stage === 'VALIDATION' && (
        <Validation
          result={result}
          onBack={() => setStage('DATA')}
          onNext={() => setStage('CLASSIFICATION')}
        />
      )}

      {/* ══════════════════════════════════════════════════════════
          CLASSIFICATION
      ══════════════════════════════════════════════════════════ */}
      {stage === 'CLASSIFICATION' && (
        <Page
          eyebrow="03 / Classification"
          title="Task classification"
          onBack={() => setStage('VALIDATION')}
        >
          <div className="classification">
            <span className="eyebrow">Detected task</span>
            <strong className="task-name">{route.task || 'Unknown'}</strong>
            <p>{route.reason || 'No routing reason was returned.'}</p>

            <div className="detail-grid">
              <Metric
                label="Required inputs"
                value={comparison ? 'Paired imagery' : 'Single image'}
              />
              <Metric label="Workflow" value={route.task} />
              <Metric
                label="Confidence"
                value={
                  result?.confidence
                    ? `${Math.round(result.confidence * 100)}%`
                    : 'Not emitted'
                }
              />
            </div>
          </div>

          <Trace result={result} />

          <button
            className="primary-button"
            type="button"
            onClick={() => setStage('ANALYSIS')}
          >
            <span>View analysis</span>
            <span>→</span>
          </button>
        </Page>
      )}

      {/* ══════════════════════════════════════════════════════════
          ANALYSIS
      ══════════════════════════════════════════════════════════ */}
      {stage === 'ANALYSIS' && (
        <Page
          eyebrow="04 / Analysis"
          title="Analysis result"
          onBack={() => setStage('CLASSIFICATION')}
        >
          <div className="answer-card">
            <span className="eyebrow">Final answer</span>
            <p>{result?.answer || result?.detail || 'No answer returned.'}</p>
          </div>

          <div className="detail-grid">
            <Metric label="Detected task" value={route.task} />
            <Metric
              label="Confidence"
              value={
                result?.confidence
                  ? `${Math.round(result.confidence * 100)}%`
                  : '--'
              }
            />
            <Metric
              label="Inference"
              value={
                result?.execution_trace?.steps?.at(-1)?.inference_mode ||
                'Specialist'
              }
            />
          </div>

          {(overlay || source) && (
            <div className="map-frame" aria-label="Spatial result viewer">
              <MapContainer
                className="map"
                center={[0, 0]}
                zoom={1}
                crs={L.CRS.Simple}
                scrollWheelZoom={false}
              >
                <ImageOverlay
                  url={
                    overlay
                      ? `data:image/png;base64,${overlay}`
                      : source
                  }
                  bounds={[
                    [-100, -100],
                    [100, 100],
                  ]}
                />
                {boxes.map((box, index) => (
                  <Rectangle
                    key={index}
                    bounds={[
                      [100 - box[0], box[1] - 100],
                      [100 - box[2], box[3] - 100],
                    ]}
                    pathOptions={{
                      color: '#ef7657',
                      weight: 2,
                      fillOpacity: 0.1,
                    }}
                  />
                ))}
              </MapContainer>
            </div>
          )}

          <Trace result={result} />

          <button
            className="primary-button"
            type="button"
            onClick={() => setStage('REPORT')}
          >
            <span>Prepare report</span>
            <span>→</span>
          </button>
        </Page>
      )}

      {/* ══════════════════════════════════════════════════════════
          REPORT
      ══════════════════════════════════════════════════════════ */}
      {stage === 'REPORT' && (
        <Page
          eyebrow="05 / Report"
          title="Evidence report"
          onBack={() => setStage('ANALYSIS')}
        >
          <div className="report-sheet">
            <span className="eyebrow">SatQuery AI · Analysis record</span>

            <Metric label="Query" value={query} />
            <Metric label="Task" value={route.task} />
            <Metric
              label="Confidence"
              value={
                result?.confidence
                  ? `${Math.round(result.confidence * 100)}%`
                  : '--'
              }
            />

            <div className="report-answer">{result?.answer}</div>

            <Trace result={result} />
          </div>

          <div className="button-row">
            <button
              className="secondary-button"
              type="button"
              disabled={!result?.report_pdf_b64}
              onClick={() => downloadPdf(result.report_pdf_b64)}
            >
              <span>Download PDF report</span>
              <span>↓</span>
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                setResult(null);
                setPrimary(null);
                setComparison(null);
                setQuery('');
                setStage('DATA');
              }}
            >
              <span>New analysis</span>
              <span>→</span>
            </button>
          </div>
        </Page>
      )}

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer>
        <span>SatQuery AI · Earth observation toolkit · v0.1</span>
        <span>Results are advisory and should be reviewed by an analyst.</span>
      </footer>
    </div>
  );
}
