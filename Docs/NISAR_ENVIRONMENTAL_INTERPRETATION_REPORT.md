# NISAR Bengaluru Environmental Interpretation and Geospatial Validation

## 1. Study-area overview

This Phase 4 review investigates the geographical distribution of Phase 3
potential-change candidates from the two NISAR L2 GCOV observations:
2026-10-29 and 2026-11-10. The AOI is Bengaluru, Karnataka, with the
Phase 2 EPSG:32643 grid bounds `[760170, 1416220, 803990, 1455420]`, a
`3920 × 4382` 10 m raster.

The source reports reviewed were the Phase 1 HDF5 validation report, the Phase
2 extraction report, and the Phase 3 temporal analysis report. All original
measurements, masks, and Phase 3 products were preserved.

## 2. Geospatial validation and candidate locations

The script
[09_geospatial_interpretation.py](/Users/deepika/Documents/SIH/SatQuery-SIH/scripts/nisar/09_geospatial_interpretation.py)
polygonized the Phase 3 HH and HV masks in EPSG:32643. Polygon areas are
computed in projected square metres and also reported in hectares and square
kilometres. Each feature includes the projected centroid and a WGS84
longitude/latitude centroid for geographic interpretation.

Candidate centroid ranges cover the AOI:

- HH decrease: longitude `77.39892–77.80136`, latitude `12.79699–13.15168`
- HH increase: longitude `77.39914–77.80122`, latitude `12.79688–13.15209`
- HV decrease: longitude `77.40080–77.79506`, latitude `12.79701–13.15388`
- HV increase: longitude `77.40100–77.79801`, latitude `12.79939–13.14651`

Small centroid excursions just outside the requested decimal-coordinate AOI
are expected because Phase 2 used an enclosing pixel-edge window; the
10-metre raster cells remain on the verified extraction grid.

## 3. Candidate area statistics

| Polarization | Direction | Regions | Pixels | Area (ha) | Area (km²) | Mean region dB difference |
|---|---|---:|---:|---:|---:|---:|
| HH | Decrease | 700 | 2,163 | 21.63 | 0.2163 | -12.8915 |
| HH | Increase | 871 | 3,578 | 35.78 | 0.3578 | 13.1032 |
| HV | Decrease | 561 | 1,949 | 19.49 | 0.1949 | -10.5491 |
| HV | Increase | 475 | 1,813 | 18.13 | 0.1813 | 10.9625 |

These are areas of statistically screened candidate pixels, not confirmed
land-cover transition areas. The candidate screen was inherited from Phase 3:
absolute dB difference beyond three scaled MADs from the polarization median,
plus at least five candidate pixels in a 3×3 neighborhood.

Vector outputs:

- `change_analysis/geospatial_interpretation/hh_candidate_change_regions_epsg32643.geojson`
- `change_analysis/geospatial_interpretation/hv_candidate_change_regions_epsg32643.geojson`
- `change_analysis/geospatial_interpretation/candidate_area_summary.csv`

The GeoJSON files retain an explicit EPSG:32643 CRS declaration.

## 4. HH/HV comparison

HH contains 5,741 candidate pixels (`0.0334%` of the common-valid AOI):
3,578 increases and 2,163 decreases. HV contains 3,762 candidate pixels
(`0.0219%`): 1,813 increases and 1,949 decreases. HH candidate area is
therefore larger in this screening, while both polarizations show both signs
of change. This supports describing the result as localized radar
backscatter anomalies rather than a single directional environmental signal.

## 5. Land-cover and geographical associations

No verified Bengaluru-specific land-cover, water-body, urban-boundary,
agricultural, vegetation, or OSM vector layer was present in the repository.
The unrelated raster files under `datasets/real_sar/`,
`datasets/real_temporal_tiffs/`, and `datasets/samples/` have different or
missing CRS/footprints and were not used as geographical evidence.

Accordingly, overlap with urban areas, agricultural land, vegetation, lakes,
or other land-cover classes is **not assessed**. The maps show the candidate
locations on the verified NISAR grid and explicitly mark land-cover context as
unavailable; no land-cover class has been inferred from pixel appearance.

## 6. Supporting datasets investigated

The following are suitable sources for a follow-up validation, but none was
downloaded or used in the Phase 4 conclusions:

| Dataset | Relevant date/resolution | Potential use | Status and limitations |
|---|---|---|---|
| [ESA WorldCover 2021 v200](https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf) | 2021 land-cover baseline, 10 m, global | Urban, cropland, tree/grass cover, water classes | Not downloaded. It is not contemporaneous with the 2026 observations and has classification error/ mixed pixels. |
| [Copernicus Sentinel-2](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html) | Date-specific L2A acquisitions; 10 m visible/NIR bands, 20 m red-edge/SWIR | Vegetation, water, bare-soil and construction corroboration | Not downloaded. Cloud, haze, acquisition timing, atmospheric correction and spectral-to-radar differences require screening. |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Vector data changes with download date; variable geometry precision | Buildings, roads, named water features and human infrastructure | Not downloaded. Coverage and update history are heterogeneous; ODbL attribution is required. |
| [NASA GPM IMERG](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary) | Half-hourly, 0.1° (~10 km), date-specific precipitation | Rainfall context before acquisitions | Not downloaded. The grid is much coarser than 10 m and is not direct surface-event evidence. |
| [NASA SMAP SPL3SMP_E](https://nsidc.org/data/SPL3SMP_E) | Daily, 9 km EASE-Grid soil moisture | Broad soil-moisture context | Not downloaded. It is much coarser than the AOI raster and includes retrieval quality limitations. |

No external acquisition date, download checksum, or spatial overlap result is
claimed because these data were not downloaded and verified.

## 7. Environmental hypotheses

### Observed radar changes

The observed quantities are pixel-wise changes in NISAR RTC gamma-zero
backscatter. Positive dB differences indicate increased measured backscatter;
negative values indicate decreased measured backscatter.

### Geographical associations

The candidate polygons are distributed throughout the extracted AOI. No
verified land-cover or infrastructure overlay is available, so no association
with Bengaluru urbanization, agriculture, vegetation, lakes, or water bodies
can be reported.

### Hypotheses requiring independent evidence

- Vegetation structure or moisture could alter HH/HV scattering.
- Soil-moisture differences between acquisition dates could change dielectric
  response.
- Temporary surface water could increase or decrease the observed response
  depending on roughness and surrounding scattering.
- Agricultural operations could change canopy, exposed soil, or field moisture.
- Urban construction or surface modification could produce localized changes.

These are physically plausible explanations only. This analysis does not
confirm deforestation, flooding, construction, agricultural activity, or any
other event.

## 8. Visualization outputs

The geospatial maps are under
`datasets/processed/bengaluru/change_analysis/geospatial_interpretation/figures/`:

- `candidate_change_geospatial_maps.png`: HH/HV dB difference with candidate
  locations, AOI outline, scale bar, north arrow, and legend.
- `candidate_change_context_status.png`: candidate masks with explicit
  “not classified” land-cover status.

## 9. Uncertainties and limitations

- The candidate regions are statistical screens, not validated change
  polygons.
- Only two detected-power dates are available.
- The 10 m NISAR grid does not provide land-cover semantics by itself.
- Gamma-zero differences can reflect soil moisture, vegetation, surface water,
  geometry, calibration, incidence-angle, and processing effects.
- Candidate regions may contain mixed land-cover pixels.
- No field observations, rainfall record, soil-moisture record, optical image,
  cadastral data, or OSM layer was verified for these dates.

## 10. Final findings

HH and HV candidate regions were successfully georeferenced and measured.
HH candidates cover `57.41 ha` and HV candidates cover `37.62 ha` under the
Phase 3 screening rules. Both increase and decrease candidates occur across
the AOI. Their geographical distribution is reproducible and preserved in
EPSG:32643 GeoJSON, but environmental interpretation remains hypothesis-only
until contemporaneous external evidence is downloaded, quality-checked, and
overlaid.

Phase 4 is complete. No frontend integration or model training was performed.
