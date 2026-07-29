# Wavelength-aware optical unmixing

*Applies to v0.1.*

Use this workflow when several measured optical channels are modeled as known
linear mixtures of declared sensor, hemodynamic, autofluorescence, background, or
other contributions. It produces source estimates only when the coefficient
matrix is independently identified and numerically usable.

This is an **experimental product API**. Wavelength metadata identifies what was
measured; it does not generate mixing coefficients. Coefficients must come from a
versioned independent calibration or be explicitly marked as user-declared.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/optical-unmixing-contract.svg" alt="Known component and optical-channel values from an independent calibration create a versioned mixing matrix, which passes rank and conditioning gates before identifiable channel patterns in a biological recording are solved; underidentified samples remain unsolved.">
  <figcaption><strong>The matrix is identified before the outcome is corrected.</strong> Missing-channel subsets are solved only when they still identify every declared component. Overdetermined systems add leave-one-channel-out reconstruction evidence; a square system cannot manufacture that validation.</figcaption>
</figure>

## The model and its boundary

For each sample, the declared model is:

\[
\mathbf{y} = \mathbf{A}\mathbf{s} + \mathbf{b}
\]

where \(\mathbf{y}\) contains measured channels, \(\mathbf{s}\) contains declared
component values, \(\mathbf{A}\) is a fixed mixing matrix, and \(\mathbf{b}\)
contains fixed channel offsets. FiberPhotometry checks that \(\mathbf{A}\) has full
component rank and does not exceed the requested condition-number gate.

It does not infer both \(\mathbf{A}\) and \(\mathbf{s}\) from the same biological
recording. That factorization is not uniquely identified without additional
constraints, even if every channel has a wavelength label.

## Route A: calibrate from known components

Use `calibrate_optical_mixing` only when each calibration component is independently
controlled or measured. Rows are calibration samples; columns have exactly the
order declared in `components` and `channels`.

```python
from fiberphotometry.multisignal import ChannelIdentity
from fiberphotometry.optical_mixing import (
    OpticalComponent,
    OpticalMixingCalibrationSpec,
    calibrate_optical_mixing,
)

components = (
    OpticalComponent(
        "sensor_fluorescence",
        role="sensor",
        unit="a.u.",
        description="known sensor-fluorophore calibration contribution",
    ),
    OpticalComponent(
        "hemoglobin_absorption",
        role="hemodynamic",
        unit="a.u.",
        description="known absorber calibration contribution",
    ),
)

channels = (
    ChannelIdentity(
        "green-470",
        site="DMS",
        sensor="dLight",
        role="sensor",
        unit="photons/s",
        excitation_wavelength_nm=470,
        emission_wavelength_nm=525,
    ),
    ChannelIdentity(
        "green-405",
        site="DMS",
        sensor="dLight",
        role="reference",
        unit="photons/s",
        excitation_wavelength_nm=405,
        emission_wavelength_nm=525,
    ),
    ChannelIdentity(
        "red-560",
        site="DMS",
        sensor="hemoglobin-control",
        role="control",
        unit="photons/s",
        excitation_wavelength_nm=560,
        emission_wavelength_nm=600,
    ),
)

calibration = calibrate_optical_mixing(
    known_component_values,  # calibration sample × component
    measured_channel_values,  # calibration sample × optical channel
    components,
    channels,
    calibration_id="phantom-2026-07-batch-04",
    spec=OpticalMixingCalibrationSpec(
        fit_intercept=True,
        minimum_samples=50,
        maximum_component_design_condition=100,
        maximum_mixing_condition_number=100,
    ),
)

mixing_design = calibration.design
```

The known-component design must identify every coefficient: collinear component
manipulations are refused. Each channel diagnostic records sample count, design
rank, condition number, in-sample RMSE, and in-sample R². These describe the
calibration fit; they are not biological-recording validation. The calibration
arrays, masks, identities, choices, and version are bound by an evidence
fingerprint.

## Route B: declare an external matrix

When coefficients were estimated elsewhere, construct the same artifact directly:

```python
from fiberphotometry.optical_mixing import (
    OpticalMixingChannel,
    OpticalMixingDesign,
    assess_optical_mixing_design,
)

mixing_design = OpticalMixingDesign(
    components=components,
    channels=(
        OpticalMixingChannel(channels[0], (1.00, -0.42), offset=10.1),
        OpticalMixingChannel(channels[1], (0.71, -0.18), offset=8.4),
        OpticalMixingChannel(channels[2], (0.09, -0.93), offset=12.7),
    ),
    coefficient_source="externally_calibrated",
    calibration_id="phantom-2026-07-batch-04",
    design_version="1",
)

assessment = assess_optical_mixing_design(mixing_design)
if assessment.status == "error":
    raise RuntimeError([issue.code for issue in assessment.issues])
```

Set `coefficient_source="user_declared"` for exploratory values. That remains a
warning in the result rather than being presented as calibration evidence.

## Apply without refitting

The biological recording matrix must follow the channel order in the design:

```python
from fiberphotometry.optical_mixing import (
    OpticalUnmixingSpec,
    extract_unmixed_component,
    unmix_optical_signals,
)

result = unmix_optical_signals(
    time_s,
    optical_values,  # time × optical channel
    mixing_design,
    OpticalUnmixingSpec(
        maximum_condition_number=100,
        require_wavelength_metadata=True,
        require_leave_one_channel_out=False,
        minimum_holdout_samples=50,
        gap_factor=3,
    ),
    valid=optical_valid,  # time × optical channel
)

sensor_series = extract_unmixed_component(result, "sensor_fluorescence")
```

No temporal interpolation, smoothing, or refitting occurs. Every distinct pattern
of available channels gets its own rank and conditioning check:

- a three-channel/two-component pattern can be solved;
- a two-channel/two-component subset can be solved only if its submatrix remains
  full rank and sufficiently conditioned; and
- a one-channel/two-component subset remains `NaN` with an exclusion reason.

`availability_patterns` records the channel IDs, sample count, rank, condition
number, solve status, and exclusion reason. The result also retains the original
clock, observation-validity matrix, solved component mask, timestamp-gap count,
reconstructed channel values, channel residuals, and an evidence fingerprint.

## Reconstruction diagnostics

When there are more channels than components, each channel can potentially be held
out while the remaining channels estimate the sources. The held-out channel is
then reconstructed without using its observed value. Diagnostics report RMSE,
RMSE normalized by observed standard deviation, and R².

A square two-channel/two-component matrix can unmix if it is full rank, but removing
either channel makes it underidentified. The result records unavailable holdout
diagnostics. Set `require_leave_one_channel_out=True` only when a redundant design
was prospectively required; it turns that limitation into a refusal gate.

Good reconstruction supports the declared linear optical model. It does not prove
that a component is neural, that a reference is inert, or that source values are
neurotransmitter concentrations.

## Relationship to reference correction

`reference_dff` fits a reference-to-signal relationship within each biological
recording and is useful as an explicit OLS/IRLS preprocessing family. Optical
unmixing answers a different question: given an independently identified
multichannel mixing system, what component values reproduce each simultaneous
measurement?

Do not substitute one silently for the other. Treat them as named alternatives in
a [robustness multiverse](multiverse-contract.md) when both are scientifically
defensible. Run [sensor/isobestic validity](optical-validity.md) and inspect
event-correlated controls; a numerically invertible matrix does not make a control
biologically valid.

## Assumptions and current limits

- Mixing is linear, additive, and fixed for the applied recording.
- Calibration units and the biological recording's channel units must match.
- Component units and coefficient scales remain those declared by calibration.
- Motion-dependent, saturation-dependent, or time-varying coefficients are not
  estimated.
- Non-negative, Bayesian, and nonlinear source models are not silently imposed.
- Sensor kinetics are not deconvolved, and source values are not concentrations.
- No public raw-recording validation has yet promoted this API beyond experimental.
