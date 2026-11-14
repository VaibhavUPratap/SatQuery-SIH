import React from 'react';

export function LandingView({ onGetStarted }) {
  return (
    <section className="landing-view">
      <div className="hero-banner">
        <div className="challenge-tag">
          <span className="nasa-dot" /> NASA Space Apps Challenge 2026 — <strong>Dancing with the SARs</strong>
        </div>
        <h1>TerraPulse AI</h1>
        <p className="hero-subtitle">
          Agentic Intelligence for NASA-ISRO NISAR-Based Earth Surface Change Detection
        </p>
        <p className="hero-desc">
          Empowering scientists and disaster response teams with actual NISAR L-band radar backscatter analysis,
          calibrated decibel log-ratio change detection, and physics-grounded flood inundation tracking.
        </p>
        <div className="hero-actions">
          <button type="button" className="btn-primary" onClick={onGetStarted}>
            Explore NISAR Workspace &rarr;
          </button>
        </div>
      </div>

      <div className="team-card">
        <h3>Development Team</h3>
        <p className="team-sub">Dayananda Sagar University, Bengaluru — Harohalli Local Event</p>
        <div className="team-grid">
          <div className="member-pill">
            <strong>Vaibhav U Pratap</strong>
            <small>AI &amp; Machine Learning</small>
          </div>
          <div className="member-pill">
            <strong>Deepika M</strong>
            <small>Data Science &amp; Remote Sensing</small>
          </div>
          <div className="member-pill">
            <strong>Carol Das</strong>
            <small>Data Science &amp; Geospatial</small>
          </div>
          <div className="member-pill">
            <strong>Krish</strong>
            <small>AI &amp; Machine Learning</small>
          </div>
        </div>
      </div>

      <div className="core-pillars">
        <div className="pillar-card">
          <span className="pillar-icon">🛰️</span>
          <h4>Actual NISAR Ingestion</h4>
          <p>
            Direct HDF5 reader parsing official NISAR L2-GCOV (Geocoded Polarimetric Covariance) and L2-GSLC products, extracting HH, HV, VV, and VH polarimetric channels.
          </p>
        </div>

        <div className="pillar-card">
          <span className="pillar-icon">📉</span>
          <h4>Calibrated Radar Physics</h4>
          <p>
            Eliminates arbitrary RGB subtraction. Computes decibel backscatter difference (&Delta;&sigma;&deg; = &sigma;&deg;<sub>T2,dB</sub> - &sigma;&deg;<sub>T1,dB</sub>) with Enhanced Lee speckle reduction.
          </p>
        </div>

        <div className="pillar-card">
          <span className="pillar-icon">🌊</span>
          <h4>Flood &amp; Water Tracking</h4>
          <p>
            Delineates open water through specular scattering drop and identifies inundated vegetation through canopy double-bounce backscatter surges.
          </p>
        </div>

        <div className="pillar-card">
          <span className="pillar-icon">🧠</span>
          <h4>LangGraph Orchestration</h4>
          <p>
            Auditable DAG execution routing user queries across specialized SAR nodes, calculating spatial area in km&sup2;, and producing downloadable 6-page scientific dossiers.
          </p>
        </div>
      </div>
    </section>
  );
}
