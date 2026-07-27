# SDR-0041: Use format-specific readers behind one acquisition boundary

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

Doric, Neurophotometrics, and pyPhotometry do not differ only in file extension.
Doric stores heterogeneous series in an acquisition-dependent HDF5 tree;
Neurophotometrics interleaves wavelengths in rows and encodes LED/digital state
in a bit field; pyPhotometry packs analog values and digital state into versioned
16-bit binary words. A single column-oriented reader would either discard these
semantics or hide consequential transformations.

Channel names and positions are not authoritative evidence of biological
identity. This extends SDR-0005 and SDR-0007 to native acquisition files.

## Decision

Each acquisition system has a format-specific parser and schema. All parsers
must return the same validated `RecordingInput` boundary and retain:

- explicit anatomical channel and signal/reference mappings;
- the source format, filename, complete-file SHA-256, and serialized schema;
- native digital transitions when the user declares their meaning;
- acquisition evidence that affects interpretation, including pyPhotometry raw
  LED-on/baseline arrays and clipping masks.

Structural inspection may identify candidate signal, time, digital, and metadata
fields. It must not infer anatomical identity or signal/reference meaning.

Reference interpolation is permitted only when the acquisition format supplies
separate signal/reference clocks and the target remains within observed support.
Different signal-channel clocks are rejected; general resampling remains an
explicit preprocessing operation.

## Alternatives considered

- **Route every format through generic CSV.** Rejected because it requires
  manual export, loses native metadata, and cannot faithfully represent packed
  binary or alternating-wavelength semantics.
- **One permissive HDF5/table autodiscovery loader.** Rejected because file-tree
  names and column positions do not establish biological meaning.
- **Copy upstream preprocessing into import.** Rejected because import must not
  silently filter, bleach-correct, normalize, or motion-correct raw acquisition.

## Consequences

Users write a short explicit mapping after inspecting their source. In return,
all downstream workflows receive the same labelled model and auditable
provenance. Adding another acquisition system requires a new parser but not a
new analysis stack.

Real-file validation is format-version specific. A legacy pyPhotometry fixture
does not validate v1.1 pulsed storage, and a Doric example does not imply every
hardware hierarchy is known.

## Revisit trigger

Revisit if a vendor publishes stable, machine-readable biological channel
metadata, or real multi-device fixtures demonstrate that bounded interpolation
cannot represent a common valid acquisition clock relationship.
