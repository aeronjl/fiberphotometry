# Upstream interoperability fixtures

These files are retained only for format-parity tests and are not included in the
FiberPhotometry package wheel. `manifest.json` records their exact upstream path,
commit, checksum and license.

- `sleap-small-robot.analysis.h5` comes from the SLEAP test suite and retains its
  BSD-3-Clause-Clear terms.
- `boris-test-export-events-tabular.csv` comes from the BORIS test suite and
  retains its GPL-3.0-only terms.

Do not replace either fixture with a newly downloaded file under the same name.
Update the manifest, expected semantics and compatibility documentation together.
