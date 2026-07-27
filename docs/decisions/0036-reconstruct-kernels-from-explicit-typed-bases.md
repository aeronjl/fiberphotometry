# SDR-0036: Reconstruct kernels from explicit typed bases

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related protocol/report: [event-kernel method contract](../event-kernel-encoding-v0.1.md)

## Context

An unconstrained finite impulse response model estimates one coefficient per lag.
That is transparent but can be high-dimensional and noisy for long windows. Smooth
bases reduce dimension by assuming nearby lags share structure, yet reporting only
basis weights makes results depend on an arbitrary parameterization and difficult
to compare on physical time.

The package also needs a type boundary that can later admit splines, history bases
or study-specific validated families without accepting an unstructured dictionary
of parameters.

## Decision

Keep a full sampled FIR basis as the backward-compatible default. Add a typed
linear raised-cosine basis with an explicit positive number of functions. Reject
more functions than sampled lags and every rank-deficient construction.

Each event retains its basis type inside `EventKernelSpec`. New basis families must
be new validated dataclass variants in the `EventKernelBasisSpec` union; irrelevant
parameters are not accepted or silently ignored.

Fit ridge coefficients in basis space, but reconstruct the reported event kernel
and grouped-jackknife uncertainty onto the original physical lag grid. The result
also stores basis-family identity, component labels, basis weights and every
sampled basis function, making reconstruction independently reproducible.

Normalize raised-cosine functions to sum to one at each sampled lag. This makes a
constant vector of basis weights reconstruct a constant lag curve while retaining
the declared lower-dimensional constraint.

## Consequences

Scientists can compare unconstrained and smooth event representations within the
common-evidence multiverse. Plots, uncertainty intervals and downstream summaries
continue to use seconds and response units rather than opaque basis coordinates.
The exact fitted parameterization remains auditable.

Raised-cosine smoothness is a modeling assumption, not a universally preferred
default. Ridge penalties act on basis weights, so equal numeric alpha values need
not imply equal effective regularization across basis families; each model retains
its own grouped cross-validated selection.

The event-kernel fit artifact advances to schema v5.

## Alternatives considered

- **Replace FIR with a smooth default:** rejected because this would silently
  impose a new shape assumption on existing analyses.
- **Store only reconstructed curves:** rejected because exact model reproduction
  requires basis functions and weights.
- **Store only basis weights:** rejected because their meaning is
  parameterization-specific and not located directly in physical time.
- **Accept arbitrary basis callables or parameter dictionaries:** rejected for the
  serialized public boundary because validation and reproducibility would be weak.
- **Orthogonalize bases automatically:** deferred because it changes weight and
  penalty interpretation; a future typed family may declare it explicitly.

## Revisit trigger

Add a basis variant when a literature-backed use case and recovery fixture define
its construction, identifiability and serialization. Revisit penalty calibration
when simulations compare effective smoothness across families or nested selection
is introduced.

## Evidence added later

None.
