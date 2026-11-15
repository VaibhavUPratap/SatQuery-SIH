# NISAR Bengaluru Temporal Change Analysis Report

## 1. Study objective

This Phase 3 analysis compares NISAR L2 GCOV RTC gamma-zero measurements over
the Bengaluru AOI on 2026-10-29 and 2026-11-10. It identifies measured
backscatter differences and statistically unusual, spatially coherent regions.
It does not establish that a specific environmental or construction event
occurred.

The Phase 1 report was found under `Docs/NISAR_HDF5_VALIDATION_REPORT.md`
(capital `D`); the Phase 2 report is
[NISAR_BENGALURU_EXTRACTION_REPORT.md](/Users/deepika/Documents/SIH/SatQuery-SIH/docs/NISAR_BENGALURU_EXTRACTION_REPORT.md).

## 2. Input data and quality validation

Inputs were:

- `nisar_hh_20261029.tif`, `nisar_hv_20261029.tif`
- `nisar_hh_20261110.tif`, `nisar_hv_20261110.tif`
- The corresponding quality and `inputDataExceptionMask` rasters.

All inputs were read successfully and verified to have:

- Shape: `3920 × 4382` (`17,177,440` pixels)
- CRS: EPSG:32643
- Resolution: 10 m
- Identical affine transform and bounds: `[760170, 1416220, 803990, 1455420]`
- Linear gamma-zero power metadata and float32 measurement dtype
- NaN measurement NoData, quality-mask NoData `255`, exception-mask NoData `65535`

The common analysis mask requires finite positive values, quality-mask validity,
the HH validity bit (`256`) or HV validity bit (`512`), and a clear exception
bit 2. All AOI pixels pass this mask for both dates and polarizations.

### Phase 1 versus Phase 2 dimensions

Phase 1 documented an approximate array slice of `3919 × 4383`
(`rows 13146:17065`, `columns 13592:17975`). Phase 2 independently projected
the geographic AOI and used pixel-edge geometry, resulting in
`3920 × 4382` (`rows 13146:17066`, `columns 13593:17975`). The Phase 2 grids
are internally consistent and are the authoritative inputs for this analysis;
no resampling or alignment correction was applied.

## 3. Temporal statistics

Statistics are computed over the complete common-valid AOI. Percentiles are
linear gamma-zero power values.

| Date | Pol. | Valid % | Minimum | Maximum | Mean | Median | Std. dev. | P1 | P5 | P95 | P99 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-10-29 | HH | 100 | 0.001957 | 37897.000000 | 1.156246 | 0.245544 | 23.251550 | 0.030914 | 0.053898 | 3.230072 | 14.211989 |
| 2026-11-10 | HH | 100 | 0.002466 | 33125.500000 | 1.182549 | 0.249369 | 23.998211 | 0.030995 | 0.054411 | 3.306854 | 14.557007 |
| 2026-10-29 | HV | 100 | 0.000404 | 1481.375000 | 0.060317 | 0.033448 | 0.768831 | 0.003986 | 0.006750 | 0.163128 | 0.369053 |
| 2026-11-10 | HV | 100 | 0.000424 | 1142.359375 | 0.060854 | 0.033638 | 0.763225 | 0.003952 | 0.006738 | 0.164322 | 0.374992 |

The complete table, including P2.5, P25, P50, P75, P97.5 and invalid counts,
is [temporal_statistics.csv](/Users/deepika/Documents/SIH/SatQuery-SIH/datasets/processed/bengaluru/change_analysis/temporal_statistics.csv).

## 4. Gamma-zero conversion and temporal products

For positive valid samples, the script computes:

`gamma0_dB = 10 * log10(gamma0_linear)`

Non-positive, non-finite, or mask-invalid pixels are written as NaN in derived
floating-point products. Original linear-power GeoTIFFs were not modified.

For each polarization:

- Linear difference: `November - October`
- Linear ratio: `November / October`
- Percentage change: `(ratio - 1) × 100`
- dB difference: `November_dB - October_dB`

Positive dB differences and ratios above 1 indicate increased measured
backscatter; negative dB differences and ratios below 1 indicate decreased
measured backscatter. These are measurement changes, not automatically
environmental-change labels.

## 5. Distribution and robust anomaly approaches

Two approaches were evaluated:

1. **Distribution tails:** the 2.5th and 97.5th percentiles of the dB
   difference identify approximately 5% of common-valid pixels as distribution
   tails. This is descriptive and intentionally not treated as a change mask.
2. **Robust, spatially coherent screening:** use the median dB difference and
   scaled MAD (`1.4826 × MAD`). A candidate is beyond three scaled MADs from
   the median, then must have at least five candidate pixels in its 3×3
   neighborhood. This reduces isolated speckle-like outliers while retaining
   explicitly measured changes. The 3-MAD rule and 5-of-9 neighborhood rule
   are documented reproducible screening assumptions, not physical detection
   thresholds.

| Pol. | Median dB diff. | MAD | Scaled MAD | 2.5th–97.5th dB range | Robust threshold | Spatially coherent candidates |
|---|---:|---:|---:|---:|---:|---:|
| HH | 0.0664 | 1.7334 | 2.5699 | -5.2553 to 5.4152 | 7.7098 dB | 5,741 (0.0334%) |
| HV | 0.0215 | 1.7772 | 2.6349 | -5.3762 to 5.4275 | 7.9047 dB | 3,762 (0.0219%) |

HH candidate pixels include 2,163 decreases and 3,578 increases. HV candidate
pixels include 1,949 decreases and 1,813 increases. The potential-change masks
encode `0=no detected change`, `1=decrease`, `2=increase`, and `255=invalid`.

## 6. Generated products

Products are in
[change_analysis/](/Users/deepika/Documents/SIH/SatQuery-SIH/datasets/processed/bengaluru/change_analysis/):

- `hh_difference_db.tif`, `hv_difference_db.tif`
- `hh_change_ratio.tif`, `hv_change_ratio.tif`
- `hh_percentage_change.tif`, `hv_percentage_change.tif`
- `hh_potential_change_mask.tif`, `hv_potential_change_mask.tif`
- Date-specific dB rasters: `hh_20261029_db.tif`, `hh_20261110_db.tif`,
  `hv_20261029_db.tif`, `hv_20261110_db.tif`
- `temporal_statistics.csv` and `change_summary.json`

All products preserve the Phase 2 CRS, transform, dimensions, and bounds.

## 7. Visualizations

The reproducible implementation is
[08_visualize_temporal_changes.py](/Users/deepika/Documents/SIH/SatQuery-SIH/scripts/nisar/08_visualize_temporal_changes.py).
Figures are in `change_analysis/figures/`:

- HH and HV October-versus-November comparisons
- HH and HV dB difference maps
- HH and HV potential-change maps
- HH and HV statistical distribution plots

Comparison displays use consistent polarization-specific dB ranges. Difference
maps use a symmetric range derived from the 1st and 99th percentiles of each
polarization's valid differences. Visualization scaling does not modify
GeoTIFF measurements.

## 8. Physical interpretation

The observed differences are compatible with multiple processes, including
vegetation structure or moisture changes, soil-moisture variation, temporary
surface water, agricultural activity, and urban surface modification. HH/HV
response alone cannot uniquely distinguish these mechanisms. The statistically
screened regions should therefore be treated as potential change indicators for
follow-up investigation, not confirmed land-cover or event labels.

## 9. Uncertainty and limitations

- Only two detected-power observations are available; no seasonal or
  multi-date baseline is available.
- GCOV gamma-zero differences can reflect incidence-angle, soil-moisture,
  vegetation, surface-water, geometric, and processing effects.
- The robust threshold detects unusual temporal differences relative to this
  AOI's own distribution; it is not a calibrated uncertainty model.
- No external rainfall, land-use, construction, field-survey, or optical
  evidence was used.
- No filtering, smoothing, resampling, normalization, machine learning, or
  deep learning was used.

## 10. Final findings

The two observations are grid-compatible and have complete common-valid
coverage in the extracted AOI. Their distributions are broadly similar, with
small shifts in HH and HV medians and means. The robust spatial screen
identifies a small fraction of unusually different pixels (HH `0.0334%`,
HV `0.0219%`), split between increases and decreases. These are scientifically
valid measured anomalies under the stated screening method, but no specific
physical event is asserted.
