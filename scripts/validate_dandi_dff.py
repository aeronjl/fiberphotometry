"""Numerically compare DANDI 001084 raw/baseline and archived dF/F slices."""

from __future__ import annotations

import warnings

import h5py
import numpy as np
import remfile
from pynwb import NWBHDF5IO

from fipha.validation import compare_fitted_baseline_dff

URL = "https://dandiarchive.s3.amazonaws.com/blobs/efc/662/efc66290-fcb4-473a-abaf-7e71ed314402"
SAMPLES = 1_000


def main() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        remote = remfile.File(URL)
        with (
            h5py.File(remote, "r") as h5_file,
            NWBHDF5IO(file=h5_file, mode="r", load_namespaces=True) as io,
        ):
            nwbfile = io.read()
            ophys = nwbfile.processing["ophys"]
            raw = np.asarray(
                nwbfile.acquisition["FiberPhotometryResponseSeriesGreen"].data[:SAMPLES]
            )
            baseline = np.asarray(
                ophys["BaselineFiberPhotometryResponseSeriesGreen"].data[:SAMPLES]
            )
            archived = np.asarray(
                ophys["DfOverFFiberPhotometryResponseSeriesGreen"].data[:SAMPLES]
            )
    print(
        compare_fitted_baseline_dff(raw=raw, baseline=baseline, archived_dff=archived)
    )


if __name__ == "__main__":
    main()
