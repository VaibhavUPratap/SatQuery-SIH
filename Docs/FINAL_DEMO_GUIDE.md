# TerraPulse AI Final Demo Guide

## 1. Start services

Always use the pushed `main` branch before starting:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

Terminal 1:

```bash
.venv/bin/python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

The browser must be opened at the Vite URL from the terminal. Do not open the
HTML file directly. The frontend defaults to
`http://127.0.0.1:8000/api/v1`; set `VITE_API_URL` if the FastAPI service is
running elsewhere. On a friend's computer, `127.0.0.1` points to the
friend's own computer, so the backend must also run there or be deployed at a
reachable URL.

## 2. Bengaluru case study

Open the dashboard, authenticate with the environment-configured prototype
credentials, and choose **Open Bengaluru NISAR case study**. Wait for the
candidate GeoJSON to finish loading, then demonstrate:

1. HH/HV switching.
2. Temporal backscatter layer visibility and opacity.
3. Swipe and side-by-side October/November comparison.
4. Candidate-region filtering, selection, highlight, and zoom.
5. GeoJSON and candidate-statistics CSV export.
6. Candidate area statistics and measured temporal charts.
7. Product IDs, CRS, resolution, processing history, trace, report, and limitations.

If the page loads but the catalog does not appear, check that
`http://127.0.0.1:8000/api/v1/nisar/bengaluru/case-study` returns HTTP 200 and
that the browser console does not show a CORS or connection-refused error.

## 3. Generalized processing

Place two real HDF5 products under `datasets/` or set `NISAR_DATA_ROOT`, then
submit the request documented in [REAL_NISAR_API_GUIDE.md](./REAL_NISAR_API_GUIDE.md).
Poll the job endpoints and show the result and execution trace.

Do not use `/nisar/synthesize` as a production scientific demonstration; it is
restricted to labelled test fixtures.

## 4. Verification

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```
