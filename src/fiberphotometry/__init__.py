"""Composable fiber photometry analysis.

The root namespace is the curated core path: ingest, preprocess, dF/F, resample,
quality control, event alignment, summarisation, the pipeline runner, and the
evidence, archive, and publication surface built on top of them. Advanced method
families keep their full public API in their own module, for example
``fiberphotometry.spectral.welch_psd`` or ``fiberphotometry.encoding``. Every
name re-exported here is declared ``supported`` or ``experimental`` in
:mod:`fiberphotometry.stability`.
"""

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _version

from fiberphotometry.archive import (
    ArchiveCreator,
    ArchiveMetadata,
    ArchivePackage,
    ArchiveRelatedIdentifier,
    create_archive_package,
    load_archive_metadata,
    verify_archive_package,
)
from fiberphotometry.comparison import (
    BundleComparison,
    EvidenceDifference,
    compare_project_evidence,
)
from fiberphotometry.config import EventAnalysisConfig
from fiberphotometry.coverage import (
    EventCoverageCounts,
    EventCoverageRecord,
    EventCoverageReport,
    EventCoverageStratum,
    assess_event_coverage,
)
from fiberphotometry.design import (
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    validate_design,
)
from fiberphotometry.event_qc import assess_event_confounds
from fiberphotometry.events import align_events, summarize_event_windows
from fiberphotometry.inference import (
    Contrast,
    Estimand,
    TIntervalResult,
    hierarchical_bootstrap,
    permutation_test,
    unit_t_interval,
)
from fiberphotometry.io.acquisition import (
    detect_acquisition_format,
    validate_acquisition_input,
)
from fiberphotometry.io.dandi import (
    resolve_dandi_download_url,
    validate_remote_nwb_asset,
)
from fiberphotometry.io.doric import (
    DoricChannel,
    DoricDigitalEvents,
    DoricSchema,
    DoricSeries,
    inspect_doric,
    load_doric_input,
)
from fiberphotometry.io.ibl import from_ibl_tables
from fiberphotometry.io.neurophotometrics import (
    NeurophotometricsChannel,
    NeurophotometricsDigitalEvents,
    NeurophotometricsSchema,
    inspect_neurophotometrics,
    load_neurophotometrics_input,
)
from fiberphotometry.io.nwb import (
    NWBAcquisitionMetadata,
    NWBChannelMetadata,
    NWBDeviceMetadata,
    NWBIndicatorMetadata,
    add_recording_to_nwb,
    from_nwb_series,
)
from fiberphotometry.io.nwb_project import (
    export_project_multiverse_nwb,
    export_project_nwb,
)
from fiberphotometry.io.pyphotometry import (
    PyPhotometryChannel,
    PyPhotometryDigitalEvents,
    PyPhotometrySchema,
    inspect_pyphotometry,
    load_pyphotometry_input,
)
from fiberphotometry.io.tabular import (
    TabularChannel,
    TabularEventColumn,
    TabularEventSchema,
    TabularRecordingSchema,
    inspect_tabular_input,
    inspect_tabular_recording,
    load_tabular_events,
    load_tabular_input,
    load_tabular_recording,
)
from fiberphotometry.io.tdt import (
    TDTBlockSchema,
    TDTEpocEvents,
    TDTEpocValue,
    TDTStreamChannel,
    load_tdt_input,
)
from fiberphotometry.model import make_recording, validate_recording
from fiberphotometry.pipeline import (
    BaselineDFFOperation,
    EventSummarySpec,
    LowpassFilterOperation,
    PipelineResult,
    PipelineSpec,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    ReferenceDFFOperation,
    ResampleOperation,
    run_pipeline,
)
from fiberphotometry.plotting import (
    SpecificationCurveEntry,
    plot_event_diagnostics,
    plot_specification_curve,
)
from fiberphotometry.preprocess import (
    baseline_dff,
    lowpass_filter,
    reference_dff,
    resample_recording,
)
from fiberphotometry.project import (
    ProjectConfig,
    TabularProjectConfig,
    TDTProjectConfig,
    load_project_config,
)
from fiberphotometry.publication import (
    PublicationAttestation,
    PublicationVerification,
    sign_publication_manifest,
    verify_publication_manifest,
)
from fiberphotometry.qc import assess_recording, assess_signal_recording
from fiberphotometry.results import (
    EvidenceFile,
    ProjectEvidenceBundle,
    read_project_evidence,
)
from fiberphotometry.stability import artifact_schema
from fiberphotometry.timecourse import (
    PeriEventInferenceResult,
    PeriEventInferenceSpec,
    infer_peri_event_contrast,
)
from fiberphotometry.transients import (
    TransientDetectionResult,
    TransientDetectionSpec,
    detect_transients,
)
from fiberphotometry.workflow import (
    EventAnalysis,
    EventAnalysisResult,
    EventSession,
    Preprocessing,
)
from fiberphotometry.zenodo import ZenodoDraftReceipt, create_zenodo_draft

try:
    __version__ = _version("fiberphotometry")
except _PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"

__all__ = [
    "ArchiveCreator",
    "ArchiveMetadata",
    "ArchivePackage",
    "ArchiveRelatedIdentifier",
    "BaselineDFFOperation",
    "BundleComparison",
    "Contrast",
    "DoricChannel",
    "DoricDigitalEvents",
    "DoricSchema",
    "DoricSeries",
    "Estimand",
    "EventAnalysis",
    "EventAnalysisConfig",
    "EventAnalysisResult",
    "EventCoverageCounts",
    "EventCoverageRecord",
    "EventCoverageReport",
    "EventCoverageStratum",
    "EventSession",
    "EventSummarySpec",
    "EvidenceDifference",
    "EvidenceFile",
    "Factor",
    "LowpassFilterOperation",
    "NWBAcquisitionMetadata",
    "NWBChannelMetadata",
    "NWBDeviceMetadata",
    "NWBIndicatorMetadata",
    "NeurophotometricsChannel",
    "NeurophotometricsDigitalEvents",
    "NeurophotometricsSchema",
    "ObservationTable",
    "PeriEventInferenceResult",
    "PeriEventInferenceSpec",
    "PipelineResult",
    "PipelineSpec",
    "Preprocessing",
    "PreprocessingSpec",
    "ProjectConfig",
    "ProjectEvidenceBundle",
    "PublicationAttestation",
    "PublicationVerification",
    "PyPhotometryChannel",
    "PyPhotometryDigitalEvents",
    "PyPhotometrySchema",
    "QualityGateSpec",
    "RecordingInput",
    "ReferenceDFFOperation",
    "ResampleOperation",
    "SpecificationCurveEntry",
    "StudyDesign",
    "TDTBlockSchema",
    "TDTEpocEvents",
    "TDTEpocValue",
    "TDTProjectConfig",
    "TDTStreamChannel",
    "TIntervalResult",
    "TabularChannel",
    "TabularEventColumn",
    "TabularEventSchema",
    "TabularProjectConfig",
    "TabularRecordingSchema",
    "TransientDetectionResult",
    "TransientDetectionSpec",
    "Unit",
    "ZenodoDraftReceipt",
    "__version__",
    "add_recording_to_nwb",
    "align_events",
    "artifact_schema",
    "assess_event_confounds",
    "assess_event_coverage",
    "assess_recording",
    "assess_signal_recording",
    "baseline_dff",
    "compare_project_evidence",
    "create_archive_package",
    "create_zenodo_draft",
    "detect_acquisition_format",
    "detect_transients",
    "export_project_multiverse_nwb",
    "export_project_nwb",
    "from_ibl_tables",
    "from_nwb_series",
    "hierarchical_bootstrap",
    "infer_peri_event_contrast",
    "inspect_doric",
    "inspect_neurophotometrics",
    "inspect_pyphotometry",
    "inspect_tabular_input",
    "inspect_tabular_recording",
    "load_archive_metadata",
    "load_doric_input",
    "load_neurophotometrics_input",
    "load_project_config",
    "load_pyphotometry_input",
    "load_tabular_events",
    "load_tabular_input",
    "load_tabular_recording",
    "load_tdt_input",
    "lowpass_filter",
    "make_recording",
    "permutation_test",
    "plot_event_diagnostics",
    "plot_specification_curve",
    "read_project_evidence",
    "reference_dff",
    "resample_recording",
    "resolve_dandi_download_url",
    "run_pipeline",
    "sign_publication_manifest",
    "summarize_event_windows",
    "unit_t_interval",
    "validate_acquisition_input",
    "validate_design",
    "validate_recording",
    "validate_remote_nwb_asset",
    "verify_archive_package",
    "verify_publication_manifest",
]
