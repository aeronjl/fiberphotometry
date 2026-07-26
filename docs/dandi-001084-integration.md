# DANDI 001084 integration contract

The first NWB benchmark target is DANDI 001084, containing multifiber striatal
photometry from head-fixed mice running on a treadmill. Its documented NWB files
use `ndx-fiber-photometry`, including a `FiberPhotometryTable` and
`FiberPhotometryResponseSeries`, alongside processed dF/F and imaging data.

## Confirmed asset

Metadata checked against the DANDI API on 2026-07-26:

- Dandiset: `001084`, draft version
- path: `sub-DL18/sub-DL18_ses-211110_image+ophys.nwb`
- asset ID: `e766feb5-f2e6-449a-a960-9562bf60d498`
- size: 18,408,586,717 bytes

The check is reproducible with:

```bash
uv run python scripts/check_dandi_001084.py
```

This metadata check is intentionally not part of ordinary CI: it requires the
network and the draft asset can change. The 18.4 GB file is not downloaded. A
subsequent integration fixture should stream the file through its DANDI S3 URL
and read only NWB metadata and a bounded signal slice.

## Current compatibility

- `from_nwb_series` accepts core `TimeSeries` and
  `FiberPhotometryResponseSeries`-shaped objects.
- Extension channel-table fields retained when present: location, excitation and
  emission wavelength, indicator, and optical fiber.
- `add_recording_to_nwb` creates a lossless core NWB representation when full
  extension hardware metadata is unavailable.
- The library deliberately does not fabricate indicators, implants, filters or
  acquisition hardware to satisfy the extension schema.

## Remaining live validation

1. Resolve the asset's content URL through the DANDI API.
2. Open remotely with PyNWB and namespace loading enabled.
3. Locate each `FiberPhotometryResponseSeries` programmatically.
4. Read metadata and at most 1,000 samples per series.
5. Validate channel count, timestamps, locations, and finite-data fraction.
6. Compare a bounded processed trace against the DANDI example notebook.

Sources:

- [DANDI 001084 example](https://docs.dandiarchive.org/example-notebooks/001084/HoweLab/001084_demo/)
- [`ndx-fiber-photometry`](https://github.com/catalystneuro/ndx-fiber-photometry)

