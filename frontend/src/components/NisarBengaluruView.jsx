import React, { useEffect, useMemo, useState } from 'react';
import { GeoJSON, MapContainer, TileLayer, Rectangle, useMap } from 'react-leaflet';
import { API_BASE_URL, getBengaluruCaseStudy, getNisarJob, getNisarJobResults, queueNisarProcessing } from '../api';

function FitBounds({ bounds }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(bounds, { padding: [18, 18] });
  }, [bounds, map]);
  return null;
}

function formatArea(value) {
  return `${Number(value).toFixed(2)} ha`;
}

export default function NisarBengaluruView({ onBack }) {
  const [catalog, setCatalog] = useState(null);
  const [polarization, setPolarization] = useState('HH');
  const [selectedDate, setSelectedDate] = useState('20261110');
  const [opacity, setOpacity] = useState(0.45);
  const [candidateGeojson, setCandidateGeojson] = useState(null);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobResult, setJobResult] = useState(null);

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
    fetch(assetUrl(path))
      .then((response) => {
        if (!response.ok) throw new Error('Candidate region geometry could not be loaded.');
        return response.json();
      })
      .then((payload) => active && setCandidateGeojson(payload))
      .catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [catalog, polarization]);

  const bounds = [[12.8, 77.4], [13.15, 77.8]];
  const selectedSummary = useMemo(
    () => catalog?.area_summary?.filter((row) => row.polarization === polarization) || [],
    [catalog, polarization],
  );
  const assetUrl = (path) => `${API_BASE_URL.replace(/\/api\/v1$/, '')}${path}`;
  const candidates = polarization === 'HH'
    ? catalog?.assets?.hh_candidates_wgs84
    : catalog?.assets?.hv_candidates_wgs84;

  async function runProcessing() {
    if (!catalog || processing) return;
    setProcessing(true);
    setError('');
    setJobResult(null);
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
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcessing(false);
    }
  }

  return (
    <main className="page nisar-case-study">
      <div className="page-heading">
        <p className="eyebrow">VERIFIED NISAR CASE STUDY / BENGALURU</p>
        <h1>Interactive temporal backscatter view</h1>
        <button className="back-button" type="button" onClick={onBack}>Back to workspace</button>
      </div>
      {error && <div className="error-message" role="alert">{error}</div>}
      {!catalog && !error && <div className="status-banner"><strong>Loading verified case-study outputs…</strong></div>}
      {catalog && (
        <>
          <div className="nisar-case-header">
            <div>
              <span className="eyebrow">29 OCTOBER → 10 NOVEMBER 2026</span>
              <h2>{catalog.study_area.name}</h2>
              <p>{catalog.measurements.quantity} · {catalog.study_area.crs} · {catalog.study_area.resolution_m} m pixels</p>
            </div>
            <div className="nisar-polarization-toggle" role="group" aria-label="Polarization">
              {catalog.measurements.polarizations.map((item) => (
                <button key={item} type="button" className={polarization === item ? 'active' : ''} onClick={() => setPolarization(item)}>
                  {item}
                </button>
              ))}
            </div>
          </div>
          <div className="nisar-case-grid">
            <section className="map-frame nisar-map-frame" aria-label={`${polarization} candidate change map`}>
              <MapContainer className="map" center={[12.975, 77.6]} zoom={10} scrollWheelZoom>
                <TileLayer attribution="© OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <Rectangle bounds={bounds} pathOptions={{ color: '#d9694b', weight: 2, fill: false }} />
                {candidates && candidateGeojson && (
                  <GeoJSON
                    key={candidates}
                    data={candidateGeojson}
                    onEachFeature={(feature, layer) => layer.bindPopup(`${polarization} candidate region`)}
                    style={(feature) => ({
                      color: feature?.properties?.direction === 'increase' ? '#d9694b' : '#2c7a7b',
                      weight: 1,
                      fillOpacity: opacity,
                    })}
                  />
                )}
                <FitBounds bounds={bounds} />
              </MapContainer>
              <div className="nisar-map-tools">
                <label htmlFor="candidate-opacity">Candidate opacity <strong>{Math.round(opacity * 100)}%</strong></label>
                <input id="candidate-opacity" type="range" min="0.1" max="0.9" step="0.05" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} />
                <div className="nisar-legend" aria-label="Candidate change legend">
                  <span><i className="legend-swatch increase" /> Increase</span>
                  <span><i className="legend-swatch decrease" /> Decrease</span>
                  <span><i className="legend-swatch neutral" /> No detected change / invalid</span>
                </div>
              </div>
            </section>
            <aside className="nisar-case-sidebar">
              <h3>{polarization} potential-change regions</h3>
              <p className="muted">Candidate regions are statistical indicators, not confirmed environmental events.</p>
              {selectedSummary.map((row) => (
                <div className="nisar-stat-row" key={`${row.polarization}-${row.direction}`}>
                  <span className={`direction-dot ${row.direction}`} />
                  <div><strong>{row.direction}</strong><small>{row.region_count} regions · {row.pixel_count} pixels</small></div>
                  <b>{formatArea(row.area_hectares)}</b>
                </div>
              ))}
              <p className="muted">
                Supporting land-cover data: {catalog.context_status.external_land_cover_data_loaded ? 'loaded' : 'not verified in repository'}.
              </p>
              <button className="primary-button" type="button" onClick={runProcessing} disabled={processing}>
                {processing ? `Processing ${jobStatus?.status || 'queued'}…` : 'Run local NISAR analysis'} <span>→</span>
              </button>
              {jobResult && <p className="muted">Job complete: {jobResult.processing?.answer || 'candidate analysis returned.'}</p>}
            </aside>
          </div>
          <section className="nisar-metadata-panel">
            <div>
              <span className="eyebrow">DATA TRANSPARENCY</span>
              <h3>{catalog.measurements.sensor} · {catalog.measurements.product}</h3>
              <p>{catalog.measurements.frequency} · Track {catalog.measurements.track} · Frame {catalog.measurements.frame} · {catalog.measurements.orbit_direction}</p>
            </div>
            <div className="nisar-date-toggle" role="group" aria-label="Observation date">
              {catalog.observations.map((observation) => (
                <button key={observation.date} type="button" className={selectedDate === observation.date ? 'active' : ''} onClick={() => setSelectedDate(observation.date)}>
                  {observation.label}
                </button>
              ))}
            </div>
            <p className="nisar-granule-id">
              Product ID: {catalog.observations.find((observation) => observation.date === selectedDate)?.granule_id}
            </p>
            <details>
              <summary>Processing history and limitations</summary>
              <ul>
                {catalog.processing_history.map((item) => <li key={item}>{item}</li>)}
                {catalog.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </details>
          </section>
          <div className="nisar-figure-row">
            <figure><img src={assetUrl(catalog.assets[`${polarization.toLowerCase()}_preview_${selectedDate}`])} alt={`${polarization} ${selectedDate} gamma-zero preview`} /><figcaption>{polarization} {selectedDate} display preview</figcaption></figure>
            <figure><img src={assetUrl(catalog.assets[polarization === 'HH' ? 'hh_difference' : 'hv_difference'])} alt={`${polarization} temporal difference preview`} /><figcaption>{polarization} dB difference (November minus October)</figcaption></figure>
            <figure><img src={assetUrl(catalog.assets[polarization === 'HH' ? 'hh_potential_change' : 'hv_potential_change'])} alt={`${polarization} potential change preview`} /><figcaption>{polarization} potential-change preview</figcaption></figure>
          </div>
        </>
      )}
    </main>
  );
}
