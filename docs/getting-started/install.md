# Install

!!! warning "Not on PyPI"

    fipha has never been released. There is no `fipha`
    package on PyPI, so `pip install fipha` will fail. The current
    version is `0.1.0.dev0` and it must be installed from the Git repository.

Python 3.11 or newer is required.

## Install from the repository

```bash
pip install "fipha @ git+https://github.com/aeronjl/fipha.git"
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv pip install "fipha @ git+https://github.com/aeronjl/fipha.git"
```

To pin an exact commit — which you should do for anything you intend to report —
append `@<sha>`:

```bash
pip install "fipha @ git+https://github.com/aeronjl/fipha.git@<commit-sha>"
```

Check the install:

```bash
python -c "import fipha; print(fipha.__version__)"
```

## Extras

The base install carries only NumPy, SciPy, and xarray. File-format readers,
plotting, and statistics are opt-in extras. Request them in square brackets
before the `@`:

```bash
pip install "fipha[acquisition,plots] @ git+https://github.com/aeronjl/fipha.git"
```

| Extra | Adds | Needed for |
|---|---|---|
| `acquisition` | `h5py`, `pandas`, `pyarrow` | [Tabular import](../tabular-import.md) and [native Doric / Neurophotometrics / pyPhotometry readers](../native-acquisition-import.md) |
| `tdt` | `tdt` | [TDT block import](../tdt-import.md) |
| `nwb` | `pynwb`, `ndx-fiber-photometry`, `ndx-pose`, `remfile` | Reading and writing the [community NWB data model](../nwb-data-model.md), DANDI streaming |
| `behavior` | `behavio[readers]` (from Git; not yet on PyPI) | Pose, ethogram, clock-synchronization and interval-policy types owned by [Behavio](https://github.com/aeronjl/behavio), plus the [longitudinal handoff](../behavio-interoperability.md) |
| `plots` | `matplotlib` | `plot_event_diagnostics` and `plot_specification_curve`, including [your first peri-event plot](first-peri-event-plot.md) |
| `stats` | `pandas`, `statsmodels` | [Scalar mixed-model sensitivity summaries](../scalar-mixed-model.md) |

[ndx-pose round trips](../ndx-pose-interoperability.md) need **both** `nwb` and
`behavior`: `nwb` supplies the NWB extension, `behavior` supplies the
`behavio.pose.PoseTrajectory` values the adapter reads and writes.

```bash
pip install "fipha[nwb,behavior] @ git+https://github.com/aeronjl/fipha.git"
```

Because Behavio has not been released either, the `behavior` extra resolves it from
a pinned Git revision (`behavio[readers] @ git+https://github.com/aeronjl/behavio@a784883`).
That pin will become an ordinary version range once Behavio is published.

Missing extras fail at import of the specific reader, not at
`import fipha`, so a base install stays usable for signal work.

## Command-line entry point

Installing the package also installs the `fipha` command used by the
[configuration-first CLI](../cli.md):

```bash
fipha --help
```

## Working from a checkout

Some pages in this documentation refer to scripts and example projects that only
exist in the repository. Clone it and let `uv` build the environment:

```bash
git clone https://github.com/aeronjl/fipha.git
cd fipha
uv sync --all-extras
uv run python -c "import fipha; print(fipha.__version__)"
```

## Next

- [Your first dF/F trace](first-dff-trace.md) — 15 lines, no data files needed.
- [Your first peri-event plot](first-peri-event-plot.md) — the standard
  event-aligned figure.
