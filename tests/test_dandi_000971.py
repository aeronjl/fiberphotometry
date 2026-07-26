from __future__ import annotations

import numpy as np
import pytest

from fiberphotometry.io.dandi_000971 import from_dandi_000971_nwb

h5py = pytest.importorskip("h5py")


def _write_fixture(path, *, names=None):
    with h5py.File(path, "w") as nwb:
        series = nwb.create_group("acquisition/fiber_photometry_response_series")
        data = np.column_stack(
            [
                np.arange(12),
                np.arange(12) + 100,
                np.arange(12) + 200,
                np.arange(12) + 300,
            ]
        )
        series.create_dataset("data", data=data)
        starting_time = series.create_dataset("starting_time", data=2.5)
        starting_time.attrs["rate"] = 100.0
        table = nwb.create_group("general/fiber_photometry/fiber_photometry_table")
        table.create_dataset(
            "name",
            data=names
            or [
                b"DMS_calcium_signal",
                b"DLS_calcium_signal",
                b"DMS_isosbestic_control",
                b"DLS_isosbestic_control",
            ],
        )
        table.create_dataset("location", data=[b"DMS", b"DLS", b"DMS", b"DLS"])
        nwb.create_dataset("general/subject/subject_id", data=b"mouse-1")
        nwb.create_dataset("identifier", data=b"session-1")


def test_loads_and_block_averages_paired_regions(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(path)

    recording = from_dandi_000971_nwb(path, target_rate_hz=20)

    assert recording.sizes == {"time": 2, "channel": 2}
    assert recording.channel.values.tolist() == ["DMS", "DLS"]
    np.testing.assert_allclose(recording.signal.values, [[2, 102], [7, 107]])
    np.testing.assert_allclose(recording.reference.values, [[202, 302], [207, 307]])
    np.testing.assert_allclose(recording.time.values, [0, 0.05])
    assert recording.attrs["source_rate_hz"] == 100
    assert recording.attrs["discarded_tail_samples"] == 2


def test_rejects_schema_drift(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(
        path,
        names=[
            b"unknown",
            b"DLS_calcium_signal",
            b"DMS_isosbestic_control",
            b"DLS_isosbestic_control",
        ],
    )

    with pytest.raises(ValueError, match="expected calcium/control schema"):
        from_dandi_000971_nwb(path)


def test_reads_names_from_commanded_voltage_references(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(path)
    with h5py.File(path, "a") as nwb:
        table = nwb["general/fiber_photometry/fiber_photometry_table"]
        del table["name"]
        references = []
        for name in (
            "dms_calcium_signal",
            "dls_calcium_signal",
            "dms_isosbestic_control",
            "dls_isosbestic_control",
        ):
            group = nwb.create_group(f"acquisition/commanded_voltage_series_{name}")
            references.append(group.ref)
        table.create_dataset(
            "commanded_voltage_series", data=references, dtype=h5py.ref_dtype
        )

    recording = from_dandi_000971_nwb(path)

    assert recording.channel.values.tolist() == ["DMS", "DLS"]
