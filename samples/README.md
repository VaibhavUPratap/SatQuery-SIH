# SatQuery AI — Sample Remote Sensing Datasets

This directory contains categorized, legitimately sourced Earth observation sample data for validating SatQuery AI's optical, SAR, cross-modal, and temporal intelligence workflows.

---

## 1. Directory Layout

```
samples/
├── optical/                     # Sentinel-2 optical imagery (RGB & 12-band Multi-spectral)
│   ├── sentinel2_lake_suburb_optical.png
│   ├── sentinel2_forest_canopy_optical.png
│   └── sentinel2_12band_multispectral.tif
├── sar/                         # Sentinel-1 Synthetic Aperture Radar (SAR) backscatter
│   ├── sentinel1_coastal_port_sar.png
│   └── sentinel1_river_farmland_sar.png
├── optical_sar/                 # Co-registered Sentinel-2 (Optical) + Sentinel-1 (SAR) pairs
│   ├── pair1_coastal_port_sentinel2_optical.png
│   ├── pair1_coastal_port_sentinel1_sar.png
│   ├── pair2_river_farmland_sentinel2_optical.png
│   └── pair2_river_farmland_sentinel1_sar.png
├── temporal/                    # Bi-temporal Sentinel acquisition pairs (T1 and T2 dates)
│   ├── change_01_deforestation_t1.png
│   ├── change_01_deforestation_t2.png
│   ├── change_02_urban_growth_t1.png
│   ├── change_02_urban_growth_t2.png
│   ├── change_03_reservoir_depletion_t1.png
│   └── change_03_reservoir_depletion_t2.png
└── vqa/                         # RSVQA benchmark image chips
    ├── rsvqa_sample_0.png
    └── rsvqa_sample_40.png
```

---

## 2. Sample Manifest & Metadata

### A. Optical (`samples/optical/`)
* **`sentinel2_lake_suburb_optical.png`**
  * Sensor: Sentinel-2 MSI (Level-2A BOA Reflectance)
  * Modality: Optical RGB (B04-Red, B03-Green, B02-Blue)
  * Resolution: $512 \times 512$ px (10m GSD)
  * Features: Suburban housing, roads, inland water body.
* **`sentinel2_forest_canopy_optical.png`**
  * Sensor: Sentinel-2 MSI
  * Modality: Optical RGB
  * Resolution: $512 \times 512$ px (10m GSD)
  * Features: Dense forest canopy, natural vegetation.
* **`sentinel2_12band_multispectral.tif`**
  * Sensor: Sentinel-2 MSI Multi-spectral GeoTIFF
  * Bands (12): `B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12` (ESA Order)
  * Resolution: $120 \times 120$ px chip (ConfigILM / BigEarthNet v2.0 benchmark standard)
  * Purpose: BigEarthNet 19-class Land-Cover Classification (`/api/v1/land-cover`).

### B. SAR (`samples/sar/`)
* **`sentinel1_coastal_port_sar.png`**
  * Sensor: Sentinel-1 C-band Synthetic Aperture Radar (GRD Level-1)
  * Modality: SAR Backscatter Amplitude
  * Polarization: Single-Pol / Dual-Pol Intensity (VV/VH backscatter proxy)
  * Features: High corner-reflector backscatter from port infrastructure; specular reflection (dark) from calm ocean water.
* **`sentinel1_river_farmland_sar.png`**
  * Sensor: Sentinel-1 C-band SAR
  * Modality: SAR Backscatter Amplitude
  * Features: Agricultural soil roughness and meandering river channel.

### C. Co-registered Optical + SAR Pairs (`samples/optical_sar/`)
* **`pair1_coastal_port_*`**: $512 \times 512$ co-registered Sentinel-2 Optical RGB and Sentinel-1 SAR pair over a maritime harbor.
* **`pair2_river_farmland_*`**: $512 \times 512$ co-registered Sentinel-2 Optical RGB and Sentinel-1 SAR pair over an alluvial agricultural delta.
* **Workflow:** Used with `/api/v1/optical-sar` or Multi-Sensor Agent mode to fuse spectral index cues with radar surface roughness.

### D. Bi-Temporal Change Pairs (`samples/temporal/`)
* **`change_01_deforestation_*`**: Sentinel-2 T1 (intact forest canopy) vs. T2 (cleared timber zone).
* **`change_02_urban_growth_*`**: Sentinel-2 T1 (rural agricultural outskirts) vs. T2 (new road infrastructure and construction).
* **`change_03_reservoir_depletion_*`**: Sentinel-2 T1 (full reservoir level) vs. T2 (severe drought contraction).

### E. VQA Benchmark Chips (`samples/vqa/`)
* Authentic $256 \times 256$ RGB image patches from the RSVQA-LR dataset used for Visual Question Answering verification.

---

## 3. Authoritative Data Sources & Download Instructions

SatQuery AI benchmarks rely on open data from official remote sensing archives:

### 1. BigEarthNet v2.0 (reBEN)
* **Description:** Large-scale multi-modal remote sensing benchmark dataset providing paired Sentinel-1 SAR and Sentinel-2 Multi-spectral patches across Europe.
* **Archive & Model Weights:** [Hugging Face BIFOLD-BigEarthNetv2-0](https://huggingface.co/BIFOLD-BigEarthNetv2-0)
* **Code Repository:** [reben-training-scripts (TU Berlin)](https://git.tu-berlin.de/rsim/reben-training-scripts)
* **Download Instructions:**
  ```bash
  # Using huggingface_hub Python library
  from huggingface_hub import snapshot_download
  snapshot_download(repo_id="BIFOLD-BigEarthNetv2-0/BigEarthNet.txt", repo_type="dataset")
  ```

### 2. Copernicus Data Space Ecosystem (CDSE)
* **Description:** Official European Space Agency (ESA) repository providing Sentinel-1 GRD/SLC and Sentinel-2 L1C/L2A imagery.
* **Portal:** [dataspace.copernicus.eu](https://dataspace.copernicus.eu)
* **API Access:** CDSE OData and STAC Catalog APIs provide automated programmatic query and download of Cloud-Optimized GeoTIFFs (COGs).

### 3. RSVQA Dataset
* **Description:** Remote Sensing Visual Question Answering benchmark dataset (Sylvain Lobry et al., IEEE TGRS).
* **Source:** [rsvqa.sylvainlobry.com](https://rsvqa.sylvainlobry.com/)
