# Official TDT demo validation

The TDT adapter is exercised against the real `FiPho-180416` fiber-photometry
block distributed in TDT's official Python SDK example archive. The archive is
not committed to this repository.

## Frozen source

- URL: <https://www.tdt.com/files/examples/TDTExampleData.zip>
- archive SHA-256: `8af3a76fafb595b938fd3e5c8a8f16423bfd24bbc50d5f5f10bcc9ed2790a147`
- selected block: `FiPho-180416`
- validated SDK version: `tdt==0.7.3`

TDT documents `tdt.download_demo_data()` as the supported way to obtain this
archive. The project fetcher adds checksum verification and extracts only the
selected block:

```bash
uv run python scripts/fetch_tdt_demo.py
FIPHA_TDT_DEMO_BLOCK=.cache/tdt-demo/extracted/FiPho-180416 \
  uv run pytest tests/test_tdt_official_demo.py
```

The download is approximately 347 MB and the selected extracted block is about
78 MB, so this remains opt-in rather than burdening every unit-test run.

## What the fixture caught

The real SDK output exposed two cases absent from the initial shaped fixtures:

1. StoreIDs beginning with a digit, such as `4654`, become Python fields such as
   `_4654`. Configuration now retains the acquisition StoreID while the adapter
   handles this SDK field-name conversion internally.
2. The final offset of an onset epoc can be `+inf`. The adapter retains this
   open-ended SDK sentinel while still rejecting non-finite onsets, NaN offsets,
   negative infinity, and finite offsets preceding onset.

## Frozen parity assertions

The integration test checks the official block's sample count, sampling rate,
first and last selected signal/reference values, 30 epocs, three epoc values with
ten observations each, and the canonical import fingerprint. It therefore tests
real TSQ/TEV parsing through the official SDK as well as our mapping boundary.

This is an interoperability fixture, not evidence that the acquisition's numeric
epoc codes have a particular scientific meaning. They are deliberately labelled
as `pulse_code`; a real analysis must supply experiment-specific labels.
