import React from 'react';

export const TABS = [
  { id: 'LANDING', label: 'Home', icon: '🌍' },
  { id: 'DASHBOARD', label: 'Dashboard', icon: '📊' },
  { id: 'STUDY_AREA', label: 'Study Area', icon: '📍' },
  { id: 'EXPLORER', label: 'NISAR Explorer', icon: '🛰️' },
  { id: 'VALIDATION', label: 'Data Validation', icon: '🔬' },
  { id: 'WORKSPACE', label: 'Analysis Workspace', icon: '⚙️' },
  { id: 'RESULTS', label: 'Interactive Map', icon: '🗺️' },
  { id: 'INSIGHTS', label: 'AI Insights', icon: '🧠' },
  { id: 'REPORTS', label: 'Scientific Reports', icon: '📄' },
];

export function Navigation({ activeTab, onSelectTab }) {
  return (
    <header className="topbar">
      <div className="brand" onClick={() => onSelectTab('LANDING')}>
        <span className="brand-logo">🛰️</span>
        <div className="brand-titles">
          <h2>TerraPulse AI</h2>
          <small>NISAR Radar Earth Intelligence</small>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Main Navigation">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`nav-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onSelectTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="topbar-badge">
        <span className="pulse-indicator" />
        <small>NASA Space Apps 2026</small>
      </div>
    </header>
  );
}
