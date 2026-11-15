# NISAR Scientific Validation and Application Readiness Report

**Project:** SatQuery-SIH — Dancing with the SARs  
**Study area:** Bengaluru, Karnataka, India  
**Validation date:** 15 November 2026  
**Branch:** `phase7-scientific-validation`

## 1. Study area and observations

The authoritative extracted AOI is the enclosing 10 m EPSG:32643 grid with
dimensions `3920 × 4382` and bounds
`[760170, 1416220, 803990, 1455420]` in projected metres. The requested
geographic extent is 77.40–77.80°E and 12.80–13.15°N.

The two verified observations are:

| Date | Product ID | Product / acquisition metadata |
|---|---|---|
| 2026-10-29 | `NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001` | NASA-ISRO NISAR L-SAR, L2 GCOV, L-band, 1.239 GHz, track 77, frame 82, descending |
| 2026-11-10 | `NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001` | NASA-ISRO NISAR L-SAR, L2 GCOV, L-band, 1.239 GHz, track 77, frame 82, descending |

Available polarizations are HH and HV. The source datasets are the diagonal
covariance measurements `HHHH` and `HVHV`.

## 2. Methodology audit

The Phase 3 implementation was inspected rather than rerun. It:

1. validates the four measurement rasters and corresponding quality and
   exception masks against one common grid;
2. requires finite positive power, a valid quality value, the
   polarization-specific exception validity bit (HH `256`, HV `512`), and a
   clear exception bit `2`;
3. converts positive linear power using `10 * log10(power)`;
4. computes November minus October dB difference, November/October linear
   ratio, and `(ratio - 1) * 100` percentage change;
5. screens candidates using three scaled MADs from the median dB difference
   and at least five candidate pixels in a 3×3 neighborhood.

No source measurement or mask file was changed. Derived floating-point NoData
is NaN; potential-mask NoData is `255`.

## 3. Polarization and measurement accuracy

- **HH:** co-polarized covariance diagonal `HHHH`, representing the HH
  backscatter-power term.
- **HV:** cross-polarized covariance diagonal `HVHV`, representing the HV
  backscatter-power term.
- **Quantity:** RTC gamma-zero (`gamma0`) in linear power units.
- **Conversion:** `gamma0_dB = 10 * log10(gamma0_linear)`.

The application labels the measurement as RTC gamma-zero linear power and
labels difference previews as dB difference. It does not label the products as
sigma-nought or as confirmed environmental change.

## 4. Temporal validation results

All `17,177,440` AOI pixels were common-valid for each polarization and date
under the documented mask logic. Independent equation checks against the
original linear GeoTIFFs passed for HH and HV:

- date-specific dB rasters equal `10 * log10(linear power)`;
- dB difference equals November dB minus October dB;
- ratio equals November linear power divided by October linear power;
- percentage equals `(ratio - 1) * 100`.

| Polarization | Median dB difference | Robust threshold | Candidate pixels | Candidate percentage |
|---|---:|---:|---:|---:|
| HH | 0.0664 dB | 7.7098 dB | 5,741 | 0.0334% |
| HV | 0.0215 dB | 7.9047 dB | 3,762 | 0.0219% |

The small positive medians do not establish a scene-wide environmental
increase. The candidate screen identifies unusual differences relative to
each polarization's AOI distribution.

## 5. Potential surface-change regions

The complete per-region geographic and measurement records are preserved in
the EPSG:32643 GeoJSON files. Each feature contains region ID, direction,
pixel count, projected area, centroid in metres, WGS84 centroid longitude and
latitude, minimum/mean/maximum dB difference, and an explicit
`land_cover_status` of unavailable.

| Pol. | Direction | Regions | Pixels | Area (ha) | Mean region dB diff. | Equivalent power change* |
|---|---|---:|---:|---:|---:|---:|
| HH | Decrease | 700 | 2,163 | 21.63 | -12.8915 dB | -94.86% |
| HH | Increase | 871 | 3,578 | 35.78 | 13.1032 dB | +1,943.24% |
| HV | Decrease | 561 | 1,949 | 19.49 | -10.5491 dB | -91.19% |
| HV | Increase | 475 | 1,813 | 18.13 | 10.9625 dB | +1,148.10% |

`*`Equivalent power change is `10^(mean dB/10)-1`, calculated from the mean
region dB for orientation only. It is not the arithmetic mean of per-pixel
percentage changes. The per-region GeoJSON is the authoritative location and
measurement record.

The candidate centroids span nearly the complete AOI. No verified external
land-cover, water-body, urban, agricultural, optical, rainfall, soil-moisture,
or field dataset is available in this repository. Therefore:

- observed: localized HH/HV gamma-zero differences under the stated screen;
- geographical association: candidate polygons and centroids on the verified
  NISAR grid;
- hypothesis only: vegetation, soil moisture, temporary water, agriculture, or
  urban surface changes could contribute;
- not confirmed: flooding, deforestation, construction, damage, or any named
  environmental event.

## 6. Interactive map quality

The final case-study view was inspected in a live browser:

- Bengaluru AOI rectangle is displayed using the documented WGS84 bounds;
- HH/HV selection changes candidate geometry, statistics, and previews;
- candidate polygons are now fetched from the API's EPSG:4326 map-display
  route; the original EPSG:32643 GeoJSON remains available unchanged;
- increase, decrease, and no-detected-change/invalid legend entries are shown;
- candidate opacity is adjustable from 10% to 90%;
- observation-date buttons switch the actual October/November preview image;
- dB difference is explicitly labelled “November minus October”;
- zoom controls, pan behavior, metadata, granule ID, and processing
  history/limitations are visible;
- browser validation recorded no console errors or failed requests.

The map uses OpenStreetMap tiles only as geographic basemap context. They are
not used as scientific land-cover evidence.

## 7. Data transparency

The catalog API and interface expose:

- both verified product IDs;
- dates, product level/type, sensor, L-band frequency, track, frame, and
  orbit direction;
- HH/HV polarization and RTC gamma-zero linear-power quantity;
- EPSG:32643, 10 m resolution, and AOI metadata;
- Phase 1–4 processing history;
- common-valid mask and environmental interpretation limitations.

The frontend displays compact previews and candidate polygons rather than
loading the ignored raw HDF5 products or large measurement GeoTIFFs.

## 8. Validation evidence

Executed Phase 7 checks:

- FastAPI catalog metadata and EPSG:4326 candidate-route checks passed.
- Original raster equation checks passed for HH and HV.
- The Phase 6 raster audit validated 20 processed rasters as 4382 × 3920,
  EPSG:32643, 10 m, and grid-aligned.
- Original HDF5 SHA-256 values still match the Phase 1 records:
  `961ca2ec272c3e64b16576e95acd47a53c200c41d5116917e7e811271db7e9ef`
  (2026-10-29) and
  `99b893a0360c112ae765c1511ed13fadd55249c5e93cfe30fcaf57029eff9704`
  (2026-11-10).
- `pytest -q tests/test_nisar_ingestion.py`: **6 passed**.
- `cd frontend && npm run build`: **passed**.
- Live browser check passed for metadata, HH/HV switching, date selection,
  polygon rendering, opacity control, legend, and zero console/network errors.

## 9. Release readiness

**Status: ready for a scientifically qualified hackathon demonstration.**

The module can demonstrate real NISAR-derived Bengaluru measurements and
statistical candidate regions. The demo must describe these as measured
backscatter differences and potential-change indicators, not as confirmed
events or land-cover classifications.

## 10. Remaining limitations and recommendations

1. Obtain contemporaneous optical, rainfall, soil-moisture, water-body, or
   field evidence before assigning a physical cause.
2. Add more repeat observations to separate seasonal variability from unusual
   change.
3. Add a formal uncertainty and radiometric consistency assessment if
   quantitative event detection is required.
4. Consider streaming tiled/overview GeoTIFF products for analyst-level raster
   inspection; the current UI intentionally avoids large-file loading.
5. Retain the original projected GeoJSON and document any future display CRS
   transformations as separate, derived representations.
