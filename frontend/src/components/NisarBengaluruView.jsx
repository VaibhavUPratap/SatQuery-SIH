import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  GeoJSON,
  ImageOverlay,
  MapContainer,
  Rectangle,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import { API_BASE_URL, downloadPdf, getBengaluruCaseStudy, getNisarJob, getNisarJobResults, getNisarJobTrace, queueNisarProcessing } from '../api';

const AOI_BOUNDS = [[12.8, 77.4], [13.15, 77.8]];
const STAGES = ['product validation', 'metadata inspection', 'measurement extraction', 'geospatial alignment', 'temporal comparison', 'candidate detection', 'evidence preparation'];

function FitBounds({ bounds }) {
  const map = useMap();
  useEffect(() => map.fitBounds(bounds, { padding: [18, 18] }), [bounds, map]);
  return null;
}

function MapReadout({ onMove }) {
  useMapEvents({ mousemove: (event) => onMove(event.latlng) });
  return null;
}

function MapActions({ selectedRegion, onFit }) {
  const map = useMap();
  useEffect(() => {
    if (!selectedRegion) return;
    const coordinates = selectedRegion.geometry?.coordinates?.flat(Infinity);
    if (!coordinates?.length) return;
    const points = [];
    for (let index = 0; index < coordinates.length; index += 2) {
      if (Number.isFinite(coordinates[index]) && Number.isFinite(coordinates[index + 1])) {
        points.push([coordinates[index + 1], coordinates[index]]);
      }
    }
    if (points.length) map.fitBounds(points, { padding: [42, 42], maxZoom: 15 });
  }, [map, selectedRegion]);
  return <button className="map-fit-button" type="button" onClick={() => onFit(map)}>Fit AOI</button>;
}

function formatNumber(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '--';
}

function formatArea(value) {
  return `${formatNumber(value)} ha`;
}

function assetUrl(path) {
  return path ? `${API_BASE_URL.replace(/\/api\/v1$/, '')}${path}` : '';
}

function downloadText(content, filename, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function candidateCsv(features) {
  const headers = ['region_id', 'polarization', 'direction', 'pixel_count', 'area_hectares', 'mean_difference_db', 'minimum_difference_db', 'maximum_difference_db', 'centroid_latitude', 'centroid_longitude'];
  const rows = features.map(({ properties = {} }) => headers.map((header) => JSON.stringify(properties[header] ?? '')).join(','));
  return [headers.join(','), ...rows].join('\n');
}

function LayerControl({ layers, setLayers, polarization }) {
  return (
    <div className="layer-control">
      <div className="panel-kicker">MAP LAYERS</div>
      {Object.entries(layers).map(([key, layer]) => (
        <div className="layer-row" key={key}>
          <label>
            <input type="checkbox" checked={layer.visible} onChange={(event) => setLayers((current) => ({ ...current, [key]: { ...layer, visible: event.target.checked } }))} />
            <span className="layer-swatch" style={{ background: layer.color }} />
            <span>{layer.label}</span>
          </label>
          {layer.opacity !== undefined && (
            <input aria-label={`${layer.label} opacity`} type="range" min="0.1" max="1" step="0.05" value={layer.opacity} onChange={(event) => setLayers((current) => ({ ...current, [key]: { ...layer, opacity: Number(event.target.value) } }))} />
          )}
        </div>
      ))}
      <p className="layer-note">{polarization} overlays use compact processed previews; raw HDF5 products remain server-side.</p>
    </div>
  );
}

function Kpi({ label, value, detail }) {
  return <div className="nisar-kpi"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

export default function NisarBengaluruView({ onBack }) {
  const [catalog, setCatalog] = useState(null);
  const [polarization, setPolarization] = useState('HH');
  const [selectedDate, setSelectedDate] = useState('20261110');
  const [opacity, setOpacity] = useState(0.45);
  const [candidateGeojson, setCandidateGeojson] = useState(null);
  const [selectedRegionId, setSelectedRegionId] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
  const [regionSort, setRegionSort] = useState('area_hectares');
  const [comparisonMode, setComparisonMode] = useState('swipe');
  const [swipePosition, setSwipePosition] = useState(50);
  const [layers, setLayers] = useState({
    before: { label: '29 Oct backscatter', visible: true, opacity: 0.72, color: '#789aa3' },
    after: { label: '10 Nov backscatter', visible: true, opacity: 0.72, color: '#d8a15d' },
    difference: { label: 'Temporal difference', visible: true, opacity: 0.8, color: '#ef7657' },
    candidates: { label: 'Candidate regions', visible: true, opacity: 0.45, color: '#9ad49e' },
    aoi: { label: 'AOI boundary', visible: true, color: '#ef7657' },
  });
  const [coordinates, setCoordinates] = useState(null);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobResult, setJobResult] = useState(null);
  const [jobTrace, setJobTrace] = useState([]);
  const mapRef = useRef(null);

  useEffect(() => {
    let active = true;
    getBengaluruCaseStudy()
      .then((payload) => active && setCatalog(payload))
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!catalog) return undefined;
    const path = polarization === 'HH' ? catalog.assets.hh_candidates_wgs84 : catalog.assets.hv_candidates_wgs84;
    let active = true;
    setCandidateGeojson(null);
    setSelectedRegionId('');
    fetch(assetUrl(path))
      .then((response) => {
        if (!response.ok) throw new Error('Candidate region geometry could not be loaded.');
        return response.json();
      })
      .then((payload) => active && setCandidateGeojson(payload))
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [catalog, polarization]);

  const selectedSummary = useMemo(
    () => catalog?.area_summary?.filter((row) => row.polarization === polarization) || [],
    [catalog, polarization],
  );
  const changeSummary = catalog?.change_summary?.find?.((row) => row.polarization === polarization)
    || catalog?.change_summary?.[polarization]
    || {};
  const temporalStats = catalog?.temporal_statistics?.filter((row) => row.polarization === polarization) || [];
  const before = temporalStats.find((row) => row.date === '20261029') || {};
  const after = temporalStats.find((row) => row.date === '20261110') || {};
  const candidates = candidateGeojson?.features || [];
  const selectedRegion = candidates.find((feature) => feature.properties?.region_id === selectedRegionId);
  const filteredCandidates = useMemo(() => candidates
    .filter((feature) => {
      const properties = feature.properties || {};
      return !regionFilter || `${properties.region_id} ${properties.direction}`.toLowerCase().includes(regionFilter.toLowerCase());
    })
    .sort((left, right) => Number(right.properties?.[regionSort] || 0) - Number(left.properties?.[regionSort] || 0))
    .slice(0, 100), [candidates, regionFilter, regionSort]);
  const selectedBeforeAsset = catalog?.assets?.[`${polarization.toLowerCase()}_preview_20261029`];
  const selectedAfterAsset = catalog?.assets?.[`${polarization.toLowerCase()}_preview_20261110`];
  const differenceAsset = catalog?.assets?.[polarization === 'HH' ? 'hh_difference' : 'hv_difference'];

  async function runProcessing() {
    if (!catalog || processing) return;
    setProcessing(true);
    setError('');
    setJobResult(null);
    setJobTrace([]);
    try {
      const submitted = await queueNisarProcessing({
        observation1: catalog.observations[0].granule_id,
        observation2: catalog.observations[1].granule_id,
        polarizations: [polarization],
        aoiBbox: catalog.study_area.bbox_wgs84,
      });
      let status = await getNisarJob(submitted.job_id);
      setJobStatus(status);
      while (status.status !== 'completed' && status.status !== 'failed') {
        await new Promise((resolve) => setTimeout(resolve, 600));
        status = await getNisarJob(submitted.job_id);
        setJobStatus(status);
      }
      if (status.status === 'failed') throw new Error(status.error || 'NISAR processing failed.');
      setJobResult((await getNisarJobResults(submitted.job_id)).result);
      setJobTrace((await getNisarJobTrace(submitted.job_id)).trace || []);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessing(false);
    }
  }

  function exportCandidates() {
    if (candidateGeojson) downloadText(JSON.stringify(candidateGeojson, null, 2), `terrapulse-${polarization.toLowerCase()}-candidate-regions.geojson`, 'application/geo+json');
  }

  if (!catalog && !error) {
    return <main className="page nisar-case-study"><div className="status-banner"><strong>Loading verified case-study outputs…</strong></div></main>;
  }

  return (
    <main className="page nisar-case-study">
      <div className="page-heading nisar-workspace-heading">
        <div>
          <p className="eyebrow">VERIFIED NISAR CASE STUDY / BENGALURU</p>
          <h1>Temporal backscatter workspace</h1>
          <p className="workspace-subtitle">A map-first investigation of candidate radar-change signals between 29 October and 10 November 2026.</p>
        </div>
        <button className="back-button" type="button" onClick={onBack}>Back to workspace</button>
      </div>
      {error && <div className="error-message" role="alert">{error}</div>}
      {catalog && (
        <>
          <section className="nisar-observation-bar">
            <div><span className="panel-kicker">OBSERVATION PAIR</span><strong>{catalog.study_area.name}</strong><small>{catalog.measurements.product} · {catalog.measurements.sensor} · {catalog.measurements.frequency}</small></div>
            <div className="observation-pair">
              {catalog.observations.map((observation, index) => <button key={observation.date} type="button" className={selectedDate === observation.date ? 'active' : ''} onClick={() => setSelectedDate(observation.date)}><span>{index ? 'AFTER' : 'BEFORE'}</span><strong>{observation.label}</strong><small>{observation.granule_id.slice(-39)}</small></button>)}
            </div>
            <div className="nisar-polarization-toggle" role="group" aria-label="Polarization">
              {catalog.measurements.polarizations.map((item) => <button key={item} type="button" className={polarization === item ? 'active' : ''} onClick={() => setPolarization(item)}>{item}</button>)}
            </div>
          </section>

          <section className="nisar-kpi-grid" aria-label="Candidate change summary">
            <Kpi label={`${polarization} candidate pixels`} value={formatNumber(changeSummary.potential_change_pixel_count)} detail={`${formatNumber(changeSummary.potential_change_percentage_of_common, 2)}% of common valid pixels`} />
            <Kpi label="Candidate area" value={formatArea(selectedSummary.reduce((sum, row) => sum + Number(row.area_hectares || 0), 0))} detail="statistical candidate estimate" />
            <Kpi label="Median backscatter" value={`${formatNumber(after.median, 3)} linear`} detail={`before ${formatNumber(before.median, 3)} · 10 m grid`} />
            <Kpi label="Elapsed time" value="12 days" detail="two acquisitions only" />
          </section>

          <section className="nisar-analysis-grid">
            <div className="map-frame nisar-map-frame">
              <div className="map-header"><div><span className="panel-kicker">INTERACTIVE MAP</span><strong>{polarization} spatial evidence</strong></div><span className="map-coordinate">{coordinates ? `${coordinates.lat.toFixed(5)}°, ${coordinates.lng.toFixed(5)}°` : 'Move over map for coordinates'}</span></div>
              <MapContainer ref={mapRef} className="map nisar-main-map" center={[12.975, 77.6]} zoom={10} scrollWheelZoom>
                <TileLayer attribution="© OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {layers.before.visible && <ImageOverlay url={assetUrl(selectedBeforeAsset)} bounds={AOI_BOUNDS} opacity={layers.before.opacity} />}
                {layers.after.visible && <ImageOverlay url={assetUrl(selectedAfterAsset)} bounds={AOI_BOUNDS} opacity={layers.after.opacity} />}
                {layers.difference.visible && <ImageOverlay url={assetUrl(differenceAsset)} bounds={AOI_BOUNDS} opacity={layers.difference.opacity} />}
                {layers.aoi.visible && <Rectangle bounds={AOI_BOUNDS} pathOptions={{ color: layers.aoi.color, weight: 2, fill: false }} />}
                {layers.candidates.visible && candidateGeojson && <GeoJSON key={`${polarization}-${selectedRegionId}`} data={candidateGeojson} onEachFeature={(feature, layer) => layer.on('click', () => setSelectedRegionId(feature.properties?.region_id || ''))} style={(feature) => ({ color: feature.properties?.region_id === selectedRegionId ? '#f4f0e8' : feature.properties?.direction === 'increase' ? '#d9694b' : '#2c7a7b', weight: feature.properties?.region_id === selectedRegionId ? 3 : 1, fillOpacity: feature.properties?.region_id === selectedRegionId ? 0.8 : layers.candidates.opacity })} />}
                <FitBounds bounds={AOI_BOUNDS} />
                <MapReadout onMove={setCoordinates} />
                <MapActions selectedRegion={selectedRegion} onFit={(map) => map.fitBounds(AOI_BOUNDS, { padding: [18, 18] })} />
              </MapContainer>
              <div className="nisar-map-footer"><span><i className="legend-swatch increase" /> Increase</span><span><i className="legend-swatch decrease" /> Decrease</span><span>EPSG:32643 · 10 m output grid</span></div>
            </div>
            <aside className="nisar-control-stack">
              <LayerControl layers={layers} setLayers={setLayers} polarization={polarization} />
              <div className="nisar-panel">
                <div className="panel-kicker">SELECTED OBSERVATION</div>
                <strong>{catalog.observations.find((observation) => observation.date.replaceAll('-', '') === selectedDate)?.label}</strong>
                <p>{catalog.measurements.track ? `Track ${catalog.measurements.track} · Frame ${catalog.measurements.frame} · ${catalog.measurements.orbit_direction}` : ''}</p>
                <p className="mono-text">{catalog.observations.find((observation) => observation.date.replaceAll('-', '') === selectedDate)?.granule_id}</p>
              </div>
              <div className="nisar-panel">
                <div className="panel-kicker">EXPORT EVIDENCE</div>
                <div className="export-actions"><button type="button" onClick={exportCandidates} disabled={!candidateGeojson}>GeoJSON</button><button type="button" onClick={() => downloadText(candidateCsv(candidates), `terrapulse-${polarization.toLowerCase()}-candidate-statistics.csv`, 'text/csv')} disabled={!candidates.length}>Stats CSV</button></div>
                <button className="secondary-button" type="button" onClick={runProcessing} disabled={processing}>{processing ? `Processing ${jobStatus?.status || 'queued'}…` : 'Run local analysis'} <span>→</span></button>
                {jobResult?.agent?.report_pdf_b64 && <button className="secondary-button" type="button" onClick={() => downloadPdf(jobResult.agent.report_pdf_b64, `terrapulse-${polarization.toLowerCase()}-nisar-report.pdf`)}>Scientific PDF <span>↓</span></button>}
                <small className="muted">Difference GeoTIFF export is unavailable in the verified asset catalog.</small>
              </div>
            </aside>
          </section>

          <section className="nisar-section">
            <div className="section-title"><div><span className="panel-kicker">TEMPORAL COMPARISON</span><h2>Read the pair before inspecting candidates</h2></div><div className="view-tabs">{['swipe', 'side-by-side'].map((mode) => <button key={mode} type="button" className={comparisonMode === mode ? 'active' : ''} onClick={() => setComparisonMode(mode)}>{mode}</button>)}</div></div>
            {comparisonMode === 'swipe' ? (
              <div className="swipe-compare"><img src={assetUrl(selectedAfterAsset)} alt={`${polarization} November backscatter`} /><div className="swipe-before" style={{ width: `${swipePosition}%` }}><img src={assetUrl(selectedBeforeAsset)} alt={`${polarization} October backscatter`} /></div><input aria-label="Before and after comparison position" type="range" min="5" max="95" value={swipePosition} onChange={(event) => setSwipePosition(Number(event.target.value))} /><div className="compare-label before-label">29 OCT</div><div className="compare-label after-label">10 NOV</div></div>
            ) : <div className="side-by-side-compare"><figure><img src={assetUrl(selectedBeforeAsset)} alt={`${polarization} October backscatter`} /><figcaption>29 October 2026 · {polarization}</figcaption></figure><figure><img src={assetUrl(selectedAfterAsset)} alt={`${polarization} November backscatter`} /><figcaption>10 November 2026 · {polarization}</figcaption></figure></div>}
          </section>

          <section className="nisar-section">
            <div className="section-title"><div><span className="panel-kicker">MEASURED STATISTICS</span><h2>{polarization} temporal signal</h2></div><span className="muted">Source: processed temporal_statistics.csv</span></div>
            <div className="stats-chart"><div className="chart-axis"><span>Mean</span><span>Median</span><span>Valid</span></div>{[before, after].map((row) => <div className="chart-column" key={row.date}><strong>{row.date === '20261029' ? '29 OCT' : '10 NOV'}</strong><div className="bar-track"><i style={{ height: `${Math.min(100, Number(row.mean || 0) / Math.max(Number(before.mean || 1), Number(after.mean || 1)) * 100)}%` }} /><span>{formatNumber(row.mean, 3)}</span></div><div className="bar-track median"><i style={{ height: `${Math.min(100, Number(row.median || 0) / Math.max(Number(before.median || 1), Number(after.median || 1)) * 100)}%` }} /><span>{formatNumber(row.median, 3)}</span></div><div className="valid-pill">{formatNumber(row.valid_percentage, 1)}%</div></div>)}</div>
            <div className="polarization-callout"><strong>{polarization} channel</strong><span>HH is co-polarized horizontal transmit/receive; HV is cross-polarized horizontal transmit/vertical receive. Only channels present in the verified product are shown.</span></div>
          </section>

          <section className="nisar-section region-section">
            <div className="section-title"><div><span className="panel-kicker">CANDIDATE REGION EXPLORER</span><h2>{formatNumber(candidates.length, 0)} {polarization} candidate radar-change regions</h2></div><span className="muted">Select a row to highlight and zoom</span></div>
            <div className="region-toolbar"><input aria-label="Filter candidate regions" placeholder="Filter by region or direction" value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)} /><select aria-label="Sort candidate regions" value={regionSort} onChange={(event) => setRegionSort(event.target.value)}><option value="area_hectares">Sort by area</option><option value="mean_difference_db">Sort by mean dB difference</option><option value="pixel_count">Sort by pixels</option></select></div>
            <div className="region-table-wrap"><table className="region-table"><thead><tr><th>Region</th><th>Direction</th><th>Area</th><th>Mean Δ dB</th><th>Centroid</th></tr></thead><tbody>{filteredCandidates.map((feature) => { const properties = feature.properties || {}; return <tr key={properties.region_id} className={properties.region_id === selectedRegionId ? 'selected' : ''} onClick={() => setSelectedRegionId(properties.region_id)}><td><strong>{properties.region_id}</strong><small>{properties.pixel_count} pixels</small></td><td><span className={`direction-tag ${properties.direction}`}>{properties.direction}</span></td><td>{formatArea(properties.area_hectares)}</td><td>{formatNumber(properties.mean_difference_db)} dB</td><td>{formatNumber(properties.centroid_latitude, 4)}, {formatNumber(properties.centroid_longitude, 4)}</td></tr>; })}</tbody></table></div>
            {selectedRegion && <div className="selected-region-card"><div><span className="panel-kicker">SELECTED REGION</span><strong>{selectedRegion.properties.region_id} · {selectedRegion.properties.direction}</strong></div><span>{formatArea(selectedRegion.properties.area_hectares)} · {formatNumber(selectedRegion.properties.mean_difference_db)} dB mean · external land-cover context not verified</span></div>}
          </section>

          <section className="nisar-lower-grid">
            <div className="nisar-section interpretation-panel"><div className="panel-kicker">GROUNDED AI INTERPRETATION</div><h2>What the evidence supports</h2><ul><li><strong>Observed:</strong> {polarization} temporal backscatter changed between the two acquisitions; the measured median moved from {formatNumber(before.median, 3)} to {formatNumber(after.median, 3)} linear power.</li><li><strong>Algorithm-generated:</strong> {formatNumber(changeSummary.potential_change_pixel_count)} pixels exceeded the robust {formatNumber(changeSummary.robust_threshold_db)} dB screening threshold.</li><li><strong>Possible explanations:</strong> surface moisture, vegetation/roughness, geometry, or built-surface changes may contribute; this pair does not identify a physical cause.</li><li><strong>Verification needed:</strong> optical imagery, rainfall, soil moisture, land-cover, or field evidence. Current catalog marks these sources as not verified.</li></ul></div>
            <div className="nisar-section"><div className="panel-kicker">PROCESSING TRANSPARENCY</div><h2>{processing ? 'Analysis in progress' : jobStatus?.status === 'completed' ? 'Analysis complete' : 'Ready to run local analysis'}</h2><div className="stage-list">{STAGES.map((stage, index) => { const completed = jobTrace.some((step) => `${step.node || ''}`.toLowerCase().includes(stage.split(' ')[0])); const active = processing && (jobStatus?.status || '').toLowerCase().includes(stage.split(' ')[0]); return <div className={`stage-item ${completed ? 'complete' : ''} ${active ? 'active' : ''}`} key={stage}><i>{completed ? '✓' : String(index + 1).padStart(2, '0')}</i><span>{stage}</span></div>; })}</div>{jobTrace.length > 0 && <details className="nisar-trace"><summary>Execution trace ({jobTrace.length} events)</summary><ul>{jobTrace.map((step, index) => <li key={`${step.node || 'step'}-${index}`}><strong>{step.node || 'workflow step'}</strong> · {step.status || 'recorded'}</li>)}</ul></details>}</div>
          </section>
          <section className="nisar-limitations"><strong>Scientific boundary</strong><span>Candidate radar-change regions are not confirmed flooding, construction, urbanization, deforestation, or other environmental events. This workspace preserves the uncertainty and provenance of the verified Bengaluru processing.</span></section>
        </>
      )}
    </main>
  );
}
