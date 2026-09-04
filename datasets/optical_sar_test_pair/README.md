# Public Optical + SAR Test Pair

Files in this folder:

- `sentinel2_optical_tci_512.tif`: public Sentinel-2 L2A TCI RGB GeoTIFF window.
- `sentinel1_vv_512.tif`: public Sentinel-1 GRD VV backscatter GeoTIFF window.

Use the optical file as the first upload and the SAR file as the second upload in
Optical + SAR mode.

Suggested query:

```text
Identify vegetation-covered and built-up regions using optical and SAR.
```

The files are compact 512 x 512 test windows. They are from public satellite
sources and have compatible dimensions for API ingestion. They are not a
scientifically co-registered same-acquisition pair, so the result is a fusion
smoke test rather than a calibrated geospatial measurement.
