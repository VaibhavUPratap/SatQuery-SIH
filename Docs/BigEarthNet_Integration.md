# BigEarthNet v2.0 ConvMixer integration

SatQuery uses the published Hugging Face checkpoint
`BIFOLD-BigEarthNetv2-0/convmixer_768_32-all-v0.2.0` as a specialist for
multi-label land-cover classification. It is exposed at `POST /api/v1/land-cover`
and through the agent with `analysis_type=land_cover` (or a query containing
“land cover” or “classify”).

## Deployment prerequisite

The checkpoint uses the custom model class supplied by the official reBEN
repository, rather than a built-in Transformers architecture. Install the
Python dependencies and make the cloned repository importable from the API
environment:

```bash
pip install -r requirements.txt
git clone https://git.tu-berlin.de/rsim/reben-training-scripts.git external/reben
export PYTHONPATH="$PWD/external/reben:$PYTHONPATH"
```

The integration imports
`reben_publication.BigEarthNetv2_0_ImageClassifier`; if the repository changes
its import layout, set `PYTHONPATH` to the directory that contains the
`reben_publication` package. On first inference, the model class downloads the
checkpoint from Hugging Face unless its standard cache is already populated.

## Input contract

This is not an RGB scene classifier. Submit a co-registered, finite-valued,
12-band Sentinel-2 GeoTIFF in the ESA order `B01`, `B02`, `B03`, `B04`, `B05`,
`B06`, `B07`, `B08`, `B8A`, `B09`, `B11`, `B12`. The published ConvMixer
checkpoint configuration and `backend/models/land_cover/model.py` both use
12 Sentinel-2 channels; a combined 14-band `VV`, `VH`, `B01`–`B12` contract is
not implemented. The API rejects RGB, 3-band visualizations, and rasters with
another band count. It returns all 19 class probabilities and the labels
meeting `BIGEARTHNET_THRESHOLD` (default `0.5`). Configure the model ID,
expected band count, and threshold with the
`BIGEARTHNET_MODEL_ID`, `BIGEARTHNET_EXPECTED_BANDS`, and
`BIGEARTHNET_THRESHOLD` environment variables.

The checkpoint is MIT licensed; cite reBEN and ConfigILM as requested in its
model card when using results in research.
