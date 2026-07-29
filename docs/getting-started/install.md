# Install

!!! warning "Not on PyPI"

    FiberPhotometry has never been released. There is no `fiberphotometry`
    package on PyPI, so `pip install fiberphotometry` will fail. The current
    version is `0.1.0.dev0` and it must be installed from the Git repository.

Python 3.11 or newer is required.

## Install from the repository

```bash
pip install "fiberphotometry @ git+https://github.com/aeronjl/fiberphotometry.git"
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv pip install "fiberphotometry @ git+https://github.com/aeronjl/fiberphotometry.git"
```

To pin an exact commit — which you should do for anything you intend to report —
append `@<sha>`:

```bash
pip install "fiberphotometry @ git+https://github.com/aeronjl/fiberphotometry.git@<commit-sha>"
```

Check the install:

```bash
python -c "import fiberphotometry; print(fiberphotometry.__version__)"
```

## Extras

The base install carries only NumPy, SciPy, and xarray. File-format readers,
plotting, and statistics are opt-in extras. Request them in square brackets
before the `@`:

```bash
pip install "fiberphotometry[acquisition,plots] @ git+https://github.com/aeronjl/fiberphotometry.git"
```

| Extra | Adds | Needed for |
|---|---|---|
| `acquisition` | `h5py`, `pandas`, `pyarrow` | [Tabular import](../tabular-import.md) and [native Doric / Neurophotometrics / pyPhotometry readers](../native-acquisition-import.md) |
| `tdt` | `tdt` | [TDT block import](../tdt-import.md) |
| `nwb` | `pynwb`, `ndx-fiber-photometry`, `ndx-pose`, `remfile` | Reading and writing the [community NWB data model](../nwb-data-model.md), DANDI streaming, [ndx-pose round trips](../ndx-pose-interoperability.md) |
| `behavior` | `h5py`, `pandas`, `tables` | DeepLabCut, SLEAP, Keypoint-MoSeq, and BORIS adapters |
| `plots` | `matplotlib` | `plot_event_diagnostics` and `plot_specification_curve`, including [your first peri-event plot](first-peri-event-plot.md) |
| `stats` | `pandas`, `statsmodels` | [Scalar mixed-model sensitivity summaries](../scalar-mixed-model.md) |

Missing extras fail at import of the specific reader, not at
`import fiberphotometry`, so a base install stays usable for signal work.

## Command-line entry point

Installing the package also installs the `fiberphotometry` command used by the
[configuration-first CLI](../cli.md):

```bash
fiberphotometry --help
```

## Working from a checkout

Some pages in this documentation refer to scripts and example projects that only
exist in the repository. Clone it and let `uv` build the environment:

```bash
git clone https://github.com/aeronjl/fiberphotometry.git
cd fiberphotometry
uv sync --all-extras
uv run python -c "import fiberphotometry; print(fiberphotometry.__version__)"
```

## Next

- [Your first dF/F trace](first-dff-trace.md) — 15 lines, no data files needed.
- [Your first peri-event plot](first-peri-event-plot.md) — the standard
  event-aligned figure.
