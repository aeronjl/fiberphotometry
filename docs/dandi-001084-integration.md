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

The 18.4 GB file is not downloaded. The bounded validator resolves its public S3
URL and uses HTTP range requests to read NWB metadata and capped signal slices:

```bash
uv run python scripts/stream_dandi_001084.py
```

The corresponding live test is opt-in so routine CI does not depend on mutable
network state:

```bash
FIBERPHOTOMETRY_LIVE_DANDI=1 uv run pytest -m integration
```

## Current compatibility

- `from_nwb_series` accepts core `TimeSeries` and
  `FiberPhotometryResponseSeries`-shaped objects.
- Extension channel-table fields retained when present: location, excitation and
  emission wavelength, indicator, and optical fiber.
- `add_recording_to_nwb` creates a lossless core NWB representation when full
  extension hardware metadata is unavailable.
- The library deliberately does not fabricate indicators, implants, filters or
  acquisition hardware to satisfy the extension schema.

## Live validation result

On 2026-07-26 the validator successfully opened the remote file with namespace
loading and found three response series: raw fluorescence, fitted baseline, and
processed dF/F. Each has shape 40,000 × 103. Exactly 1,000 samples per series were
indexed; all values in those slices were finite, spanning 0.7785–34.0842 seconds.
Channel locations were recovered from the extension table. The machine-readable
summary is [`benchmarks/dandi-001084-validation.json`](../benchmarks/dandi-001084-validation.json).

The read emitted six compatibility warnings. The file's embedded extension stores
several device `model` fields as text, whereas NWB 2.9 represents them as links to
`DeviceModel`. Current PyNWB can read by remapping those values, but the resulting
objects should not be assumed safely writable without metadata repair.

The remaining validation task is numerical comparison of the bounded processed
trace against the DANDI example notebook, rather than merely structural agreement.

Sources:

- [DANDI 001084 example](https://docs.dandiarchive.org/example-notebooks/001084/HoweLab/001084_demo/)
- [`ndx-fiber-photometry`](https://github.com/catalystneuro/ndx-fiber-photometry)
