import numpy as np

from fipha.validation import compare_fitted_baseline_dff


def test_dff_comparison_detects_channelwise_zeroing() -> None:
    baseline = np.asarray([[2.0, 4.0], [2.0, 4.0], [2.0, 4.0]])
    raw = baseline * np.asarray([[1.1, 1.2], [1.2, 1.3], [1.3, 1.4]])
    calculated = (raw - baseline) / baseline
    archived = calculated - np.asarray([0.05, 0.1])

    result = compare_fitted_baseline_dff(
        raw=raw, baseline=baseline, archived_dff=archived
    )

    assert np.isclose(result.median_channel_correlation, 1.0)
    assert np.isclose(result.median_channel_offset, 0.075)
    assert result.offset_adjusted_rmse < 1e-12
