"""Interchange adapters for external photometry formats."""

from fiberphotometry.io.acquisition import (
    AcquisitionField,
    AcquisitionFormat,
    AcquisitionInspection,
    detect_acquisition_format,
    validate_acquisition_input,
)
from fiberphotometry.io.dandi_000351 import from_dandi_000351_nwb
from fiberphotometry.io.dandi_000971 import (
    from_dandi_000971_nwb,
    rewarded_unrewarded_nose_pokes,
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
from fiberphotometry.io.pyphotometry import (
    PyPhotometryChannel,
    PyPhotometryDigitalEvents,
    PyPhotometrySchema,
    inspect_pyphotometry,
    load_pyphotometry_input,
)
from fiberphotometry.io.tabular import (
    TabularChannel,
    TabularChannelInspection,
    TabularEventColumn,
    TabularEventInspection,
    TabularEvents,
    TabularEventSchema,
    TabularInputInspection,
    TabularInspection,
    TabularRecordingSchema,
    inspect_loaded_tabular_input,
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

__all__ = [
    "AcquisitionField",
    "AcquisitionFormat",
    "AcquisitionInspection",
    "DoricChannel",
    "DoricDigitalEvents",
    "DoricSchema",
    "DoricSeries",
    "NeurophotometricsChannel",
    "NeurophotometricsDigitalEvents",
    "NeurophotometricsSchema",
    "PyPhotometryChannel",
    "PyPhotometryDigitalEvents",
    "PyPhotometrySchema",
    "TDTBlockSchema",
    "TDTEpocEvents",
    "TDTEpocValue",
    "TDTStreamChannel",
    "TabularChannel",
    "TabularChannelInspection",
    "TabularEventColumn",
    "TabularEventInspection",
    "TabularEventSchema",
    "TabularEvents",
    "TabularInputInspection",
    "TabularInspection",
    "TabularRecordingSchema",
    "detect_acquisition_format",
    "from_dandi_000351_nwb",
    "from_dandi_000971_nwb",
    "from_ibl_tables",
    "inspect_doric",
    "inspect_loaded_tabular_input",
    "inspect_neurophotometrics",
    "inspect_pyphotometry",
    "inspect_tabular_input",
    "inspect_tabular_recording",
    "load_doric_input",
    "load_neurophotometrics_input",
    "load_pyphotometry_input",
    "load_tabular_events",
    "load_tabular_input",
    "load_tabular_recording",
    "load_tdt_input",
    "rewarded_unrewarded_nose_pokes",
    "validate_acquisition_input",
]
