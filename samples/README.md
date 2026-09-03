# SatQuery AI — Demonstration Sample Data Pack (Phase 4)

This directory contains the documented, legitimately sourced Earth Observation sample data pack for **SatQuery AI**.

---

## 1. Directory Structure

```
samples/
├── vqa/                     # Visual Question Answering (RSVQA-LR benchmark & S2 RGB chips)
│   ├── rsvqa_sample_0.png
│   ├── rsvqa_sample_1.png
│   ├── rsvqa_sample_40.png
│   ├── sentinel2_lake_suburb_vqa.png
│   ├── sentinel2_forest_vqa.png
│   └── manifest.json
├── caption/                 # Remote Sensing Scene Captioning & Terrain Description
│   ├── sentinel2_lake_suburb_caption.png
│   ├── sentinel2_forest_canopy_caption.png
│   ├── sentinel1_coastal_port_caption.png
│   ├── sentinel1_river_farmland_caption.png
│   └── manifest.json
├── grounding/               # Text-Guided Visual Region Grounding & Spatial Localization
│   ├── sentinel2_lake_suburb_grounding.png
│   ├── sentinel2_forest_canopy_grounding.png
│   └── manifest.json
├── land_cover/              # BigEarthNet v2.0 (reBEN) Multi-Modal Land-Cover Classification
│   ├── sentinel2_12band_multispectral.tif   # 12-band Sentinel-2 L2A GeoTIFF (Analysis Data)
│   ├── sentinel1_2band_sar.tif              # 2-band Sentinel-1 GRD SAR GeoTIFF (Analysis Data)
│   ├── sentinel1_s2_14band_multimodal.tif   # 14-band Co-registered S1+S2 GeoTIFF (Analysis Data)
│   ├── sentinel2_land_cover_rgb_preview.png # 8-bit RGB Visual Preview (Preview Only)
│   └── manifest.json
├── change_detection/        # Bi-Temporal Change Detection & Environmental Monitoring
│   ├── change_01_deforestation_t1.png
│   ├── change_01_deforestation_t2.png
│   ├── change_01_deforestation_mask.png     # Ground truth change binary mask
│   ├── change_02_urban_growth_t1.png
│   ├── change_02_urban_growth_t2.png
│   ├── change_02_urban_growth_mask.png
│   ├── change_03_reservoir_depletion_t1.png
│   ├── change_03_reservoir_depletion_t2.png
│   ├── change_03_reservoir_depletion_mask.png
│   └── manifest.json
├── optical_sar/             # Co-Registered Multi-Sensor Optical + SAR Pairs
│   ├── pair1_coastal_port_sentinel2_optical.png
│   ├── pair1_coastal_port_sentinel1_sar.png
│   ├── pair2_river_farmland_sentinel2_optical.png
│   ├── pair2_river_farmland_sentinel1_sar.png
│   └── manifest.json
├── optical/                 # Single-Sensor Optical Imagery Archive
│   ├── sentinel2_lake_suburb_optical.png
│   ├── sentinel2_forest_canopy_optical.png
│   └── sentinel2_12band_multispectral.tif
├── sar/                     # Single-Sensor SAR Imagery Archive
│   ├── sentinel1_coastal_port_sar.png
│   └── sentinel1_river_farmland_sar.png
├── temporal/                # Legacy Temporal Pair Aliases
└── README.md                # Master Sample Pack Documentation
```

---

## 2. Core Integrity & Data Type Distinctions

> [!IMPORTANT]
> **Strict Nomenclature & Data Type Rules:**
> 1. **Never label a generic RGB image as "Sentinel-2"** unless it was legitimately derived from Sentinel-2 Level-2A/Level-1C spectral bands.
> 2. **Never label a visualized SAR image as raw SAR.** SAR visualizations are 8-bit amplitude renderings; raw analysis SAR data consists of complex I/Q data or calibrated float32 $\sigma^0 / \gamma^0$ backscatter rasters.
> 3. **Always distinguish RAW/ANALYSIS DATA from VISUALIZATION IMAGES.**

| Aspect | RAW / ANALYSIS DATA | VISUALIZATION IMAGE |
| :--- | :--- | :--- |
| **File Format** | Cloud-Optimized GeoTIFF (`.tif`), HDF5, NetCDF | PNG (`.png`), JPEG (`.jpg`, `.jpeg`), WebP |
| **Data Types** | `float32`, `uint16` radiometric Digital Numbers (DN) | 8-bit unsigned integer (`uint8` [0–255]) |
| **Spectral Channels** | 12 MSI bands (`B01`–`B12`), 2 SAR polarizations (`VV`, `VH`) | 3-channel RGB (`R=B04, G=B03, B=B02`) or Grayscale |
| **Physical Units** | Bottom-Of-Atmosphere (BOA) Reflectance $[0.0, 1.0]$, Calibrated $\sigma^0$ Backscatter (dB / linear power) | Scaled display brightness $[0, 255]$ with gamma/contrast stretch |
| **Geospatial Header** | Embedded EPSG CRS, GeoTransform matrix, bounding tie-points | Non-georeferenced pixel array (spatial grid inferred by pairing) |
| **Target SatQuery API** | `/api/v1/land-cover` (BigEarthNet ConvMixer) | `/api/v1/vqa`, `/api/v1/caption`, `/api/v1/grounding`, `/api/v1/change`, `/api/v1/optical-sar`, `/api/v1/agent` |

---

## 3. Sample Categories & Specifications

---

### Category A: Visual Question Answering (`samples/vqa/`)

* **Source**: RSVQA-LR Benchmark (*Sylvain Lobry et al., IEEE TGRS*) & Copernicus Open Access Hub.
* **License**: Open Data / CC BY 4.0.
* **Sensor**: Sentinel-2 MSI (Multi-Spectral Instrument).
* **Format**: 8-bit PNG (VISUALIZATION IMAGE derived from Sentinel-2 L2A Bands B04, B03, B02).
* **Native Resolution**: 10m Ground Sample Distance (GSD), $256 \times 256$ pixels ($2.56\,\text{km} \times 2.56\,\text{km}$).
* **Intended API**: `/api/v1/vqa` or `/api/v1/agent` (with `analysis_type: "vqa"`).

| File | Question | Expected Answer | Category / Reasoning |
| :--- | :--- | :--- | :--- |
| `rsvqa_sample_0.png` | *"Is it a rural or an urban area"* | `rural` | Binary land-use classification over agricultural parcel mosaic. |
| `rsvqa_sample_1.png` | *"What is the number of commercial buildings?"* | `5` | Object counting across commercial warehouse rooftops. |
| `rsvqa_sample_40.png` | *"What is the number of small water areas in the image?"* | `7` | Strictly held-out test split sample (0% training overlap). |
| `sentinel2_lake_suburb_vqa.png` | *"Is there a river or water body present?"* | `Yes, a water body is visible.` | Water presence verification on $512 \times 512$ suburban scene. |
| `sentinel2_forest_vqa.png` | *"What type of land cover dominates this image?"* | `Dense vegetation and forest canopy` | Spectral vegetation index identification. |

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/vqa \
  -F "file=@samples/vqa/rsvqa_sample_0.png" \
  -F "question=Is it a rural or an urban area"
```

---

### Category B: Remote Sensing Scene Captioning (`samples/caption/`)

* **Source**: European Space Agency (ESA) Copernicus Data Space Ecosystem (CDSE).
* **License**: Copernicus Open Access (Free, full and open data policy).
* **Sensors**: Sentinel-2 MSI (Optical) & Sentinel-1 C-SAR (Radar).
* **Format**: 8-bit PNG (VISUALIZATION IMAGE).
* **Intended API**: `/api/v1/caption` or `/api/v1/agent` (with `analysis_type: "caption"`).

| File | Sensor / Modality | Acquisition Date | Expected Caption / Summary |
| :--- | :--- | :--- | :--- |
| `sentinel2_lake_suburb_caption.png` | Sentinel-2 MSI (Optical RGB) | 2021-06-20 | *A satellite scene showing a clear water body with developed built-up urban structures and roads.* |
| `sentinel2_forest_canopy_caption.png` | Sentinel-2 MSI (Optical RGB) | 2021-07-10 | *A satellite scene showing dense vegetation or forest area with natural green canopy cover.* |
| `sentinel1_coastal_port_caption.png` | Sentinel-1 C-SAR (GRD Backscatter Render) | 2021-06-22 | *A high-altitude remote sensing view of coastal port infrastructure with high corner-reflector backscatter and dark specular water.* |
| `sentinel1_river_farmland_caption.png` | Sentinel-1 C-SAR (GRD Backscatter Render) | 2021-07-05 | *A satellite scene showing meandering river channel with surrounding rough agricultural soil parcels.* |

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/caption \
  -F "file=@samples/caption/sentinel2_lake_suburb_caption.png"
```

---

### Category C: Text-Guided Visual Grounding (`samples/grounding/`)

* **Source**: Sentinel-2 MSI Level-2A Orthorectified Surface Reflectance.
* **License**: Copernicus Open Access.
* **Format**: 8-bit PNG (VISUALIZATION IMAGE).
* **Coordinate Output**: Bounding Boxes in `[ymin, xmin, ymax, xmax]` pixel format + Base64 annotated overlay.
* **Intended API**: `/api/v1/grounding` or `/api/v1/agent` (with `analysis_type: "grounding"`).

| File | Target Query | Target Class | Expected Localization |
| :--- | :--- | :--- | :--- |
| `sentinel2_lake_suburb_grounding.png` | *"Locate the water body."* | `water body` | Coordinates enclosing the blue water reservoir. |
| `sentinel2_lake_suburb_grounding.png` | *"Highlight the built-up area."* | `built-up structure` | Coordinates enclosing suburban houses, asphalt, and concrete. |
| `sentinel2_forest_canopy_grounding.png` | *"Highlight the dense vegetation and forest area."* | `vegetation` | Coordinates enclosing high-chlorophyll forest canopy. |

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/grounding \
  -F "file=@samples/grounding/sentinel2_lake_suburb_grounding.png" \
  -F "query=Locate the water body."
```

---

### Category D: BigEarthNet-Compatible Land Cover (`samples/land_cover/`)

* **Source**: BIFOLD BigEarthNet v2.0 (reBEN) / TU Berlin / ESA Copernicus.
* **License**: Community Data License Agreement - Permissive (CDLA-Permissive-1.0).
* **Nomenclature**: 19-Class CORINE Land Cover (CLC) Aggregated Taxonomy.
* **Target Model**: `BIFOLD-BigEarthNetv2-0/convmixer_768_32-all-v0.2.0` (ConvMixer-768/32).
* **Chip Geometry**: $120 \times 120$ pixels, 10m GSD ($1.2\,\text{km} \times 1.2\,\text{km}$), `EPSG:32634`.
* **Intended API**: `/api/v1/land-cover`.

#### 1. Sentinel-2 Spectral Bands Specification (12 Bands)
All 20m and 60m bands are resampled to 10m GSD matching the official reBEN / ConfigILM standard:

| Band Index | Band Name | Spectral Region | Central $\lambda$ (nm) | Native GSD (m) | Preprocessing State |
| :---: | :---: | :--- | :---: | :---: | :--- |
| 1 | **B01** | Coastal Aerosol | 443 | 60 | L2A BOA Reflectance, Bilinear resampled to 10m |
| 2 | **B02** | Blue | 490 | 10 | L2A BOA Reflectance (Native 10m) |
| 3 | **B03** | Green | 560 | 10 | L2A BOA Reflectance (Native 10m) |
| 4 | **B04** | Red | 665 | 10 | L2A BOA Reflectance (Native 10m) |
| 5 | **B05** | Vegetation Red Edge 1 | 705 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |
| 6 | **B06** | Vegetation Red Edge 2 | 740 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |
| 7 | **B07** | Vegetation Red Edge 3 | 783 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |
| 8 | **B08** | NIR (Broad) | 842 | 10 | L2A BOA Reflectance (Native 10m) |
| 9 | **B8A** | NIR (Narrow / Red Edge 4) | 865 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |
| 10 | **B09** | Water Vapour | 945 | 60 | L2A BOA Reflectance, Bilinear resampled to 10m |
| 11 | **B11** | SWIR 1 | 1610 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |
| 12 | **B12** | SWIR 2 | 2190 | 20 | L2A BOA Reflectance, Nearest resampled to 10m |

#### 2. Sentinel-1 SAR Bands Specification (2 Bands)
| Band Index | Band Name | Polarization | Central Freq | Native Resolution | Preprocessing State |
| :---: | :---: | :--- | :---: | :---: | :--- |
| 1 | **VV** | Co-polarized (Vertical Tx / Vertical Rx) | 5.405 GHz (C-band) | 20m $\times$ 22m (IW GRD) | Radiometric calibration to $\sigma^0$ backscatter (dB), terrain-corrected (SRTM 30m), 10m grid |
| 2 | **VH** | Cross-polarized (Vertical Tx / Horizontal Rx) | 5.405 GHz (C-band) | 20m $\times$ 22m (IW GRD) | Radiometric calibration to $\sigma^0$ backscatter (dB), terrain-corrected (SRTM 30m), 10m grid |

#### 3. Land Cover Sample Files
* `sentinel2_12band_multispectral.tif`: **RAW/ANALYSIS DATA** (12-band `float32` GeoTIFF). Expected labels: *Mixed forest*, *Land principally occupied by agriculture, with significant areas of natural vegetation*.
* `sentinel1_2band_sar.tif`: **RAW/ANALYSIS DATA** (2-band `float32` GeoTIFF, VV/VH $\sigma^0$).
* `sentinel1_s2_14band_multimodal.tif`: **RAW/ANALYSIS DATA** (14-band `float32` GeoTIFF, VV + VH + B01–B12).
* `sentinel2_land_cover_rgb_preview.png`: **VISUALIZATION IMAGE** (8-bit RGB preview for human UI viewing only).

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/land-cover \
  -F "file=@samples/land_cover/sentinel2_12band_multispectral.tif"
```

---

### Category E: Bi-Temporal Change Detection (`samples/change_detection/`)

* **Source**: Sentinel-2 MSI Multi-Temporal Acquisitions.
* **License**: Copernicus Open Access.
* **Format**: 8-bit PNG (VISUALIZATION IMAGE Pairs).
* **Dimensions**: $256 \times 256$ pixels ($2.56\,\text{km} \times 2.56\,\text{km}$ at 10m GSD).
* **Intended API**: `/api/v1/change` or `/api/v1/agent` (with 2 image uploads).

| Scenario ID | T1 Acquisition | T2 Acquisition | Expected Change Type | Ground Truth File | Description / Spectral Shift |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `change_01_deforestation` | 2019-08-10 | 2021-08-15 | **Deforestation / Canopy Clearing** | `change_01_deforestation_mask.png` | Dense forest canopy (high NIR/Green) cleared to dry exposed soil (high SWIR/Red). Approx. 35.2% changed area. |
| `change_02_urban_growth` | 2018-05-12 | 2022-05-18 | **Urbanization / Infrastructure Growth** | `change_02_urban_growth_mask.png` | Rural farmland converted to concrete roads, commercial buildings, and roofs. Approx. 23.5% changed area. |
| `change_03_reservoir_depletion` | 2020-04-10 | 2022-06-25 | **Surface Water Contraction / Drought** | `change_03_reservoir_depletion_mask.png` | Post-monsoon full reservoir contracting to dry silt bed during severe drought. Approx. 28.4% changed area. |

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/change \
  -F "file_t1=@samples/change_detection/change_01_deforestation_t1.png" \
  -F "file_t2=@samples/change_detection/change_01_deforestation_t2.png"
```

---

### Category F: Co-Registered Optical + SAR Pairs (`samples/optical_sar/`)

* **Source**: Co-registered Sentinel-2 MSI Optical L2A & Sentinel-1 C-SAR GRD.
* **License**: Copernicus Open Access.
* **Spatial Extent**: $512 \times 512$ pixels ($5.12\,\text{km} \times 5.12\,\text{km}$), `EPSG:32632` (UTM Zone 32N).
* **Alignment**: Pixel-to-pixel rigid co-registration on 10m spatial grid ($\Delta t < 48\,\text{h}$).
* **Intended API**: `/api/v1/optical-sar` or `/api/v1/agent` (with 2 image uploads).

#### Cross-Modal Fusion Logic:
* **Water Detection**: Optical Blue absorption dominance ($\text{Blue} > \text{Green} + 15 \land \text{Blue} > \text{Red} + 15$) **$\cap$** SAR specular reflection low backscatter ($\text{SAR} < P_{35}$).
* **Built-Up Detection**: Optical neutral albedo ($\Delta(\text{RGB}) < 20 \land 80 < \mu_{\text{RGB}} < 220$) **$\cap$** SAR corner-reflector high backscatter ($\text{SAR} > P_{65}$).

| Pair ID | Optical File | SAR File | Geography | Expected Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `pair1_coastal_port` | `pair1_coastal_port_sentinel2_optical.png` | `pair1_coastal_port_sentinel1_sar.png` | Coastal Port & Maritime Harbor | Water: $\ge 15\%$, Built-Up: $\ge 8\%$ |
| `pair2_river_farmland` | `pair2_river_farmland_sentinel2_optical.png` | `pair2_river_farmland_sentinel1_sar.png` | River Basin & Agricultural Delta | Water: $\ge 12\%$, Built-Up: $\ge 5\%$ |

**Example API Invocation:**
```bash
curl -X POST http://localhost:8000/api/v1/optical-sar \
  -F "optical_file=@samples/optical_sar/pair1_coastal_port_sentinel2_optical.png" \
  -F "sar_file=@samples/optical_sar/pair1_coastal_port_sentinel1_sar.png" \
  -F "query=Identify water and built-up areas using both optical and SAR."
```

---

## 4. Deterministic Demonstration Playbook

Run the deterministic test script to validate all sample categories and verify backend inference:

```bash
# Activate virtual environment
source .venv/bin/activate

# Execute deterministic validation of all sample categories
pytest tests/test_sample_pack.py -v
```

### End-to-End Capability Verification Matrix

```bash
# 1. Visual Question Answering (VQA)
curl -s -X POST http://localhost:8000/api/v1/vqa \
  -F "file=@samples/vqa/rsvqa_sample_0.png" \
  -F "question=Is it a rural or an urban area" | jq .answer

# 2. Scene Captioning
curl -s -X POST http://localhost:8000/api/v1/caption \
  -F "file=@samples/caption/sentinel2_lake_suburb_caption.png" | jq .caption

# 3. Text-Guided Region Grounding
curl -s -X POST http://localhost:8000/api/v1/grounding \
  -F "file=@samples/grounding/sentinel2_lake_suburb_grounding.png" \
  -F "query=Locate the water body." | jq .bounding_boxes

# 4. BigEarthNet Land-Cover Classification (Requires 12-band GeoTIFF)
curl -s -X POST http://localhost:8000/api/v1/land-cover \
  -F "file=@samples/land_cover/sentinel2_12band_multispectral.tif" | jq .predictions

# 5. Bi-Temporal Change Detection
curl -s -X POST http://localhost:8000/api/v1/change \
  -F "file_t1=@samples/change_detection/change_01_deforestation_t1.png" \
  -F "file_t2=@samples/change_detection/change_01_deforestation_t2.png" | jq .change_summary

# 6. Optical + SAR Cross-Modal Fusion
curl -s -X POST http://localhost:8000/api/v1/optical-sar \
  -F "optical_file=@samples/optical_sar/pair1_coastal_port_sentinel2_optical.png" \
  -F "sar_file=@samples/optical_sar/pair1_coastal_port_sentinel1_sar.png" \
  -F "query=Identify water and built-up regions" | jq .class_coverage
```

---

## 5. Authoritative Data Repositories & Download Instructions

1. **Copernicus Data Space Ecosystem (CDSE)**:
   * Portal: [dataspace.copernicus.eu](https://dataspace.copernicus.eu)
   * Official ESA STAC and OData APIs for programmatic retrieval of Sentinel-1 GRD and Sentinel-2 L2A Cloud-Optimized GeoTIFFs (COGs).
2. **BigEarthNet v2.0 (reBEN)**:
   * Portal & Checkpoints: [Hugging Face BIFOLD-BigEarthNetv2-0](https://huggingface.co/BIFOLD-BigEarthNetv2-0)
   * Repository: [TU Berlin Remote Sensing Image Analysis Group](https://git.tu-berlin.de/rsim/reben-training-scripts)
3. **RSVQA Benchmark**:
   * Sylvain Lobry, Diego Marcos, Devis Tuia, "RSVQA: Visual Question Answering for Remote Sensing Data", *IEEE TGRS*, 2020.
   * Dataset: [rsvqa.sylvainlobry.com](https://rsvqa.sylvainlobry.com/)
