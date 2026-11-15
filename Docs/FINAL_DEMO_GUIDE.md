# TerraPulse AI Final Demo Guide

## 1. Start services

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

## 2. Bengaluru case study

Open the dashboard, authenticate with the environment-configured prototype
credentials, and choose **Open Bengaluru NISAR case study**. Demonstrate:

1. HH/HV switching.
2. Candidate opacity and increase/decrease legend.
3. October/November preview selection.
4. Candidate area statistics.
5. Product IDs, CRS, resolution, processing history, and limitations.

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
