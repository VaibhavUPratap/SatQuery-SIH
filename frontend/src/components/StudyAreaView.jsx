import React, { useState } from 'react';
import { MapContainer, TileLayer, Rectangle, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon paths in Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const PRESETS = [
  { name: 'Kaveri Basin, Bengaluru (Karnataka)', bbox: [76.8, 12.2, 77.9, 13.5], center: [12.85, 77.35] },
  { name: 'Brahmaputra Floodplain (Assam)', bbox: [91.5, 25.8, 93.2, 27.2], center: [26.5, 92.35] },
  { name: 'Godavari Delta (Andhra Pradesh)', bbox: [81.8, 16.3, 82.7, 17.2], center: [16.75, 82.25] },
];

export function StudyAreaView({ currentBbox, onSetBbox, onSearchNisar }) {
  const [selectedPreset, setSelectedPreset] = useState(0);

  const activeBbox = currentBbox || PRESETS[selectedPreset].bbox;
  // Leaflet Rectangle bounds: [[minLat, minLon], [maxLat, maxLon]]
  const bounds = [
    [activeBbox[1], activeBbox[0]],
    [activeBbox[3], activeBbox[2]],
  ];
  const center = [
    (activeBbox[1] + activeBbox[3]) / 2,
    (activeBbox[0] + activeBbox[2]) / 2,
  ];

  function handleSelectPreset(index) {
    setSelectedPreset(index);
    onSetBbox(PRESETS[index].bbox);
  }

  return (
    <section className="study-area-view">
      <div className="view-header">
        <div>
          <h3>Study Area Selection</h3>
          <p>Define geographic area of interest (AOI) polygon bounding coordinates for NISAR data retrieval</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => onSearchNisar(activeBbox)}
        >
          🔍 Search NISAR Granules for AOI
        </button>
      </div>

      <div className="aoi-layout">
        <div className="map-panel">
          <MapContainer
            center={center}
            zoom={8}
            scrollWheelZoom={true}
            style={{ height: '480px', width: '100%', borderRadius: '12px' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Rectangle
              bounds={bounds}
              pathOptions={{ color: '#0ea5e9', weight: 2, fillOpacity: 0.25 }}
            />
            <Marker position={center}>
              <Popup>
                <strong>Area of Interest</strong><br />
                Bounding Box: [{activeBbox.map((c) => c.toFixed(2)).join(', ')}]
              </Popup>
            </Marker>
          </MapContainer>
        </div>

        <div className="aoi-sidebar">
          <h4>Regional Presets</h4>
          <div className="preset-list">
            {PRESETS.map((p, idx) => (
              <button
                key={p.name}
                type="button"
                className={`preset-item ${selectedPreset === idx ? 'selected' : ''}`}
                onClick={() => handleSelectPreset(idx)}
              >
                <strong>{p.name}</strong>
                <small>BBOX: [{p.bbox.join(', ')}]</small>
              </button>
            ))}
          </div>

          <div className="coords-card">
            <h5>Current Bounding Box Coordinates</h5>
            <div className="coords-grid">
              <div><small>Min Longitude</small><span>{activeBbox[0]}° E</span></div>
              <div><small>Min Latitude</small><span>{activeBbox[1]}° N</span></div>
              <div><small>Max Longitude</small><span>{activeBbox[2]}° E</span></div>
              <div><small>Max Latitude</small><span>{activeBbox[3]}° N</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
