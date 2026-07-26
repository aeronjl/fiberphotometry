import json

import numpy as np

from fiberphotometry import make_recording, reference_dff


def test_reference_dff_recovers_known_linear_baseline() -> None:
    time = np.arange(100, dtype=float)
    reference = 1 + 0.01 * time
    signal = 2 + 3 * reference
    signal[50] += 2
    recording = make_recording(
        time=time,
        signal=signal,
        reference=reference,
        subject="m",
        session="s",
    )

    corrected = reference_dff(recording, method="irls")

    coefficients = corrected.reference_fit_coefficient.values[0]
    assert np.allclose(coefficients, [2, 3], atol=0.05)
    assert corrected.dff.values[50, 0] > 0.2
    assert (
        json.loads(corrected.attrs["fiberphotometry_reference_dff"])["method"] == "irls"
    )
    assert "dff" not in recording


def test_irls_is_less_affected_by_transients_than_ols() -> None:
    time = np.arange(200, dtype=float)
    reference = 1 + time / 200
    signal = 1 + 2 * reference
    signal[::10] += 5
    recording = make_recording(
        time=time, signal=signal, reference=reference, subject="m", session="s"
    )

    robust = reference_dff(recording, method="irls")
    ols = reference_dff(recording, method="ols")

    robust_error = abs(robust.reference_fit_coefficient.values[0, 1] - 2)
    ols_error = abs(ols.reference_fit_coefficient.values[0, 1] - 2)
    assert robust_error < ols_error
