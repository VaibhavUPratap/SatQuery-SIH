import React from 'react';

export function DashboardView({ onSelectHotspot, onQuickDemo }) {
  const hotspots = [
    {
      id: 'kaveri',
      title: 'Kaveri Basin, Karnataka',
      type: 'Flood Inundation & Reservoirs',
      dates: '2026-06-02 to 2026-07-14',
      status: 'High Alert',
      coords: [12.8, 77.4],
      bbox: [76.8, 12.2, 77.9, 13.5],
      desc: 'Monsoon surge monitoring along Kaveri river tributaries and urban catchment basins.',
    },
    {
      id: 'brahmaputra',
      title: 'Brahmaputra Floodplain, Assam',
      type: 'River Dynamics & Wetlands',
      dates: '2026-06-10 to 2026-08-10',
      status: 'Active Monitoring',
      coords: [26.2, 92.4],
      bbox: [91.5, 25.8, 93.2, 27.2],
      desc: 'Severe seasonal inundation and sandbar channel changes captured via L-band SAR.',
    },
    {
      id: 'godavari',
      title: 'Godavari Delta, Andhra Pradesh',
      type: 'Mangrove & Polarimetry',
      dates: '2026-05-18 to 2026-07-02',
      status: 'Baseline Stable',
      coords: [16.8, 82.2],
      bbox: [81.8, 16.3, 82.7, 17.2],
      desc: 'Quad-pol coastal wetland monitoring with dual-pol cross-ratio vegetation decomposition.',
    },
  ];

  return (
    <section className="dashboard-view">
      <div className="view-header">
        <div>
          <h3>Mission Operational Dashboard</h3>
          <p>Real-time telemetry and regional Earth observation monitoring status</p>
        </div>
        <button type="button" className="btn-secondary" onClick={onQuickDemo}>
          ⚡ Run End-to-End NISAR Flood Demo
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <small>Active Radar Mission</small>
          <strong>NASA-ISRO NISAR</strong>
          <span className="badge-tag">L-band (1.25 GHz)</span>
        </div>
        <div className="stat-card">
          <small>Primary Product Tier</small>
          <strong>L2-GCOV / GSLC</strong>
          <span className="badge-tag">HDF5 Geocoded</span>
        </div>
        <div className="stat-card">
          <small>Change Metric</small>
          <strong>Decibel Log-Ratio</strong>
          <span className="badge-tag">&Delta;&sigma;&deg; (dB)</span>
        </div>
        <div className="stat-card">
          <small>Orchestration Engine</small>
          <strong>LangGraph DAG</strong>
          <span className="badge-tag">Thread Checkpointed</span>
        </div>
      </div>

      <div className="hotspots-section">
        <h4>Target Hotspot Scenarios</h4>
        <div className="hotspots-grid">
          {hotspots.map((h) => (
            <div key={h.id} className="hotspot-card">
              <div className="card-top">
                <span className="pill-type">{h.type}</span>
                <span className={`pill-status ${h.status.toLowerCase().replace(' ', '-')}`}>{h.status}</span>
              </div>
              <h5>{h.title}</h5>
              <p className="card-desc">{h.desc}</p>
              <div className="card-meta">
                <span><strong>Window:</strong> {h.dates}</span>
              </div>
              <button
                type="button"
                className="btn-outline"
                onClick={() => onSelectHotspot(h)}
              >
                Inspect Observation Pair &rarr;
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
