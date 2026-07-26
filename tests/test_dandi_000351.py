from __future__ import annotations

import numpy as np
import pytest

from fiberphotometry.io.dandi_000351 import from_dandi_000351_nwb

h5py = pytest.importorskip("h5py")


def _write_fixture(path, *, identity="raw405,raw470", time_offset=0.0):
    with h5py.File(path, "w") as nwb:
        raw = nwb.create_group("acquisition/photometry")
        raw.attrs["data_identity"] = identity
        raw.create_dataset("data", data=[[1.0, 2.0], [1.1, 2.2], [1.2, 2.4]])
        raw.create_dataset("timestamps", data=[0.0, 0.1, 0.2])
        archived = nwb.create_group("processing/photometry/dff")
        archived.create_dataset("data", data=[0.0, 1.0, 2.0])
        archived.create_dataset(
            "timestamps", data=np.asarray([0.0, 0.1, 0.2]) + time_offset
        )
        nwb.create_dataset("general/subject/subject_id", data=b"mouse-1")
        nwb.create_dataset("identifier", data=b"session-1")


def test_loads_raw_identity_and_archived_percentage(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(path)

    recording = from_dandi_000351_nwb(path)

    np.testing.assert_allclose(recording.signal.values[:, 0], [2.0, 2.2, 2.4])
    np.testing.assert_allclose(recording.reference.values[:, 0], [1.0, 1.1, 1.2])
    np.testing.assert_allclose(
        recording.archived_dff_percentage.values[:, 0], [0, 1, 2]
    )
    assert recording.attrs["raw_column_identity"] == "raw405,raw470"


def test_rejects_ambiguous_raw_identity(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(path, identity="raw470,raw405")

    with pytest.raises(ValueError, match="requires data_identity"):
        from_dandi_000351_nwb(path)


def test_rejects_timestamp_misalignment(tmp_path):
    path = tmp_path / "sample.nwb"
    _write_fixture(path, time_offset=2e-6)

    with pytest.raises(ValueError, match="timestamps differ"):
        from_dandi_000351_nwb(path)
