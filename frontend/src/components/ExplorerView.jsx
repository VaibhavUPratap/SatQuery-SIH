import React, { useState, useEffect } from 'react';
import { searchNisarGranules } from '../api';

export function ExplorerView({ currentBbox, onSelectPair }) {
  const [productType, setProductType] = useState('GCOV');
  const [startDate, setStartDate] = useState('2026-05-01');
  const [endDate, setEndDate] = useState('2026-08-30');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [t1Granule, setT1Granule] = useState(null);
  const [t2Granule, setT2Granule] = useState(null);

  useEffect(() => {
    executeSearch();
  }, [productType]);

  async function executeSearch() {
    setLoading(true);
    setError('');
    try {
      const data = await searchNisarGranules({
        minLon: currentBbox ? currentBbox[0] : undefined,
        minLat: currentBbox ? currentBbox[1] : undefined,
        maxLon: currentBbox ? currentBbox[2] : undefined,
        maxLat: currentBbox ? currentBbox[3] : undefined,
        startDate,
        endDate,
        productType,
      });
      setResults(data.granules || []);
      if ((data.granules || []).length >= 2) {
        setT1Granule(data.granules[1]);
        setT2Granule(data.granules[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to search NISAR granules.');
    } finally {
      setLoading(false);
    }
  }

  function handleUseSelectedPair() {
    if (t1Granule && t2Granule) {
      onSelectPair(t1Granule, t2Granule);
    }
  }

  return (
    <section className="explorer-view">
      <div className="view-header">
        <div>
          <h3>NISAR Data Explorer</h3>
          <p>Search and retrieve radar observations from NASA Earthdata Search &amp; ASF Vertex</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          disabled={!t1Granule || !t2Granule}
          onClick={handleUseSelectedPair}
        >
          Proceed with Selected Pair &rarr;
        </button>
      </div>

      <div className="search-toolbar">
        <div className="form-group">
          <label>Product Tier</label>
          <select value={productType} onChange={(e) => setProductType(e.target.value)}>
            <option value="GCOV">L2-GCOV (Geocoded Covariance)</option>
            <option value="GSLC">L2-GSLC (Geocoded Single-Look Complex)</option>
            <option value="GUNW">L2-GUNW (Geocoded Unwrapped Interferogram)</option>
          </select>
        </div>

        <div className="form-group">
          <label>Start Date</label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>

        <div className="form-group">
          <label>End Date</label>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>

        <button type="button" className="btn-secondary" onClick={executeSearch} disabled={loading}>
          {loading ? 'Querying Catalog...' : 'Search Observations'}
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}

      <div className="selection-status-bar">
        <div>
          <span>T1 (Baseline):</span>{' '}
          <strong>{t1Granule ? `${t1Granule.start_time?.slice(0, 10)} (${t1Granule.region_name || 'Observation'})` : 'Not Selected'}</strong>
        </div>
        <div>
          <span>T2 (Monitoring):</span>{' '}
          <strong>{t2Granule ? `${t2Granule.start_time?.slice(0, 10)} (${t2Granule.region_name || 'Observation'})` : 'Not Selected'}</strong>
        </div>
      </div>

      <div className="granules-grid">
        {results.map((g) => (
          <div key={g.granule_id} className="granule-card">
            <div className="granule-top">
              <span className="badge-prod">{g.product_type}</span>
              <span className="badge-pol">{g.polarization}</span>
              <span className="badge-orbit">Orbit {g.orbit_number || g.orbit_pass}</span>
            </div>
            <h6>{g.region_name || g.granule_id}</h6>
            <div className="granule-details">
              <div><span>Date:</span> <strong>{g.start_time ? g.start_time.replace('T', ' ').slice(0, 19) : '2026-06-01'}</strong></div>
              <div><span>Frequency:</span> <strong>{g.frequency_band || 'L-band 1.25 GHz'}</strong></div>
              <div><span>Pass:</span> <strong>{g.orbit_pass || 'Ascending'}</strong></div>
              <div><span>Track / Frame:</span> <strong>{g.track || 43} / {g.frame || 128}</strong></div>
            </div>
            <div className="granule-actions">
              <button
                type="button"
                className={`btn-select ${t1Granule?.granule_id === g.granule_id ? 'active' : ''}`}
                onClick={() => setT1Granule(g)}
              >
                Set as T1 Baseline
              </button>
              <button
                type="button"
                className={`btn-select ${t2Granule?.granule_id === g.granule_id ? 'active' : ''}`}
                onClick={() => setT2Granule(g)}
              >
                Set as T2 Monitoring
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
