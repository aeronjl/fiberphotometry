# SDR-0025: Stop Zenodo automation at validated drafts

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Archival deposition v0.1](../archive-deposition-v0.1.md)

## Context

Manual repository upload is error-prone after generating a validated archive, but
publishing a Zenodo draft registers a DOI and changes the long-lived public record.
API tokens are secrets, sandbox and production use separate accounts and tokens,
and API-provided upload links must not become a credential-exfiltration path.

## Decision

Automate creation, metadata transfer, streamed file upload, and read-back
validation of a Zenodo draft. Default to `sandbox.zenodo.org`; require an explicit
production flag to create a production draft. Read tokens only from a named
environment variable and send them only to HTTPS URLs on the selected Zenodo host.

Do not implement a publish operation. Return a non-secret receipt that confirms
the environment, unpublished state, draft location, archive checksum, and project
fingerprint. Leave final visual review and publication to a separately authorized
human action.

## Consequences

The repetitive handoff is testable without allowing analysis automation to make
an output public. A failed upload may leave an empty or partial draft; the error
reports its draft ID so the user can inspect or remove it in Zenodo. Sandbox
tokens remain separate from production credentials.

## Alternatives considered

- Publish after upload: rejected because upload success does not constitute
  scientific, licensing, authorship, or presentation approval.
- Accept access tokens as CLI arguments: rejected because shell history and
  process inspection can expose them.
- Follow arbitrary bucket URLs returned by the API: rejected because bearer
  credentials must remain constrained to the selected Zenodo host.

## Revisit trigger

Only add programmatic publication if a reviewed release workflow supplies a
separate one-time authorization, immutable preview evidence, and an explicit
confirmation boundary outside ordinary analysis execution.
