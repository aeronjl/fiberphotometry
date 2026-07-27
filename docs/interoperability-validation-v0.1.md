# Behavioral interoperability validation

This report separates three different claims that are easy to conflate:

1. an adapter accepts an in-memory array shaped like a source tool;
2. a file reader accepts the source tool's documented on-disk schema; and
3. a checksum-pinned file produced or retained by the upstream project passes a
   semantic parity test.

Only the third is a real-file fixture result. It still validates file semantics,
not a biological analysis.

## Compatibility matrix

| Source | In-memory boundary | File reader | Upstream fixture | Current evidence |
|---|---|---|---|---|
| DeepLabCut | MultiIndex scorer/bodypart/x-y-likelihood; multi-animal identity may be selected explicitly | prediction CSV and pandas HDF5 | **Missing** | documented three- and four-row header schemas are generated in tests; likelihood range and identity ambiguity are checked |
| SLEAP | standard and MATLAB-compatible Analysis HDF5 axis orders | Analysis HDF5 with stored or explicitly declared dimensions | **Pass: official legacy format-v1 HDF5** | coordinates and point scores match the pinned three-frame upstream artifact |
| Keypoint-MoSeq | frame-level integer syllable sequence to duration-preserving bouts | `results.h5/<recording>/syllable` | **Missing** | the documented HDF5 hierarchy is generated in tests and the resulting bout boundaries are checked |
| BORIS | aggregated POINT/STATE columns | tabular CSV with metadata preamble and START/STOP pairing | **Pass: official BORIS test export** | explicit subject selection and three paired state intervals match the pinned upstream artifact |
| Unspool | canonical trial-level column handoff | optional `Study` construction | **Pass: public cross-package benchmark** | explicit chronology, retained neural columns, fingerprint and prospective fold composition |
| Clock synchronization | explicit one-to-one source/target pulse pairs | versioned JSON evidence artifact | **Synthetic only** | known affine offset/drift recovery, residual and drift refusal, bounded extrapolation, and pose/covariate/annotation composition are tested |

The two missing upstream fixtures remain provisional. A schema-generated HDF5 file
does not prove that a current DeepLabCut or Keypoint-MoSeq release writes every
field exactly as expected.

## Pinned artifacts

| Tool | Upstream artifact | Commit | SHA-256 |
|---|---|---|---|
| SLEAP | [`small_robot...analysis.h5`](https://github.com/talmolab/sleap/blob/8ab323e060d827adc03e629122723aa54e1ca950/tests/data/hdf5_format_v1/small_robot.000_small_robot_3_frame.analysis.h5) | `8ab323e060d8` | `21446732fe6a…6f82de` |
| BORIS | [`test_export_events_tabular.csv`](https://github.com/olivierfriard/BORIS/blob/1f6149f68e7c4df28d92fb50a8f8a38ed7a377d2/tests/files/test_export_events_tabular.csv) | `1f6149f68e7c` | `54554a4c9cc3…7131442` |

The complete source URLs, repository heads, checksums, notes and licenses live in
`tests/fixtures/interoperability/manifest.json`. The SLEAP fixture retains its
BSD-3-Clause-Clear terms. The BORIS fixture retains its GPL-3.0-only terms, is used
only for tests, and is excluded from the package wheel.

## What the real files changed

### SLEAP scores are not universally probabilities

The legacy official fixture contains finite `point_scores` above one. The shared
`PoseTrajectory` therefore treats SLEAP confidence-like scores as non-negative,
not as probabilities. DeepLabCut's source-specific adapter continues to enforce
likelihood in `[0, 1]`.

Legacy SLEAP Analysis HDF5 also omits dimension attributes. Its reader refuses to
guess and requires:

```python
pose = pose_from_sleap_analysis_h5(
    path,
    subject="robot-1",
    session="three-frames",
    node="front",
    dims=("track", "xy", "node", "frame"),
    fps=25.0,
)
```

Newer `sleap-io` files can carry JSON dimension names on the `tracks` and score
datasets; those are read automatically.

### BORIS has two useful export shapes

The original in-memory adapter covers aggregated events, where STATE rows already
contain start and stop. The official upstream fixture is instead a tabular export:
it contains a metadata preamble, then individual START and STOP rows. The file
reader locates the semantic header, requires explicit selection when multiple
subjects are present, pairs rows by behavior, and rejects unmatched or consecutive
state boundaries.

```python
annotations = annotations_from_boris_tabular_file(
    path,
    subject="canonical-mouse-1",
    session="observation-1",
    source_subject="subject1",
)
```

Blank or `POINT` status rows are point events. START/STOP rows are retained as
positive-duration intervals.

## Remaining validation work

1. Obtain or generate a redistributable prediction file using a pinned current
   DeepLabCut release, including one multi-animal file.
2. Obtain a redistributable `results.h5` produced by a pinned current
   Keypoint-MoSeq release, including any syllable reindexing provenance.
3. Add a current `sleap-io` standard-preset fixture alongside the legacy one.
4. Add a BORIS aggregated-export file containing both POINT and STATE events.
5. Exercise all four against photometry timestamps with a real synchronization
   record; synthetic affine recovery and file parity do not validate
   acquisition-specific clock alignment.
