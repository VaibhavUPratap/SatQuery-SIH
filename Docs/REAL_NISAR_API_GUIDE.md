# Real NISAR API Guide

## Product requirement

The generalized workflow accepts two existing local NISAR L2-GCOV HDF5
products, or validated GeoTIFF extracts. It never treats a search result,
synthetic product, or fabricated identifier as an observation.

Products are resolved from `datasets/` by basename, from `NISAR_DATA_ROOT`, or
from an approved local path in debug deployments.

## Start the API

```bash
.venv/bin/python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

## Queue processing

```http
POST /api/v1/nisar/process
Content-Type: application/json
```

```json
{
  "observation_1": "NISAR_L2_PR_GCOV_20261029.h5",
  "observation_2": "NISAR_L2_PR_GCOV_20261110.h5",
  "product_type": "GCOV",
  "polarizations": ["HH", "HV"],
  "analysis_type": "change",
  "aoi_bbox": [77.40, 12.80, 77.80, 13.15],
  "parameters": {"threshold_db": 3.0}
}
```

The response contains a `job_id`. Poll:

- `GET /api/v1/nisar/jobs/{job_id}`
- `GET /api/v1/nisar/jobs/{job_id}/results`
- `GET /api/v1/nisar/jobs/{job_id}/trace`

Job status is one of `queued`, `validating`, `preprocessing`, `analysing`,
`generating_evidence`, `completed`, or `failed`.

Optional local corroboration can be supplied through `parameters.external_sources`:

```json
{
  "external_sources": [
    {
      "source": "Sentinel-2",
      "path": "context/sentinel2_20261109.tif",
      "source_date": "2026-11-09",
      "source_url": "https://dataspace.copernicus.eu/"
    }
  ]
}
```

The source must be inside `datasets/` or `NISAR_DATA_ROOT`. The result records
the original filename, source date/URL, CRS, dimensions, and AOI coverage.
Unavailable standard sources remain explicitly marked `not_verified`.

## Scientific interpretation

Returned candidate regions are statistical radar-backscatter anomalies.
They are not confirmed flooding, construction, urbanization, deforestation,
or another environmental event without independent corroboration.
