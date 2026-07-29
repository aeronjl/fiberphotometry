# SDR-0023: Sign manifest attestations with domain-separated OpenSSH

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Publication signing v0.1](../publication-signing.md)

## Context

Manifest checksums detect modified bundle contents but do not identify who endorsed
the evidence root. A new bespoke signing format would add cryptographic and key-
management risk, while researchers and GitHub contributors commonly already have
OpenSSH keys and agents.

## Decision

Sign a versioned JSON attestation containing the exact manifest digest, project
fingerprint, signer identity, and signing time. Use OpenSSH SSHSIG with the fixed
namespace `fipha-publication@aeronjl.github.io`. Keep the detached
signature and attestation outside the manifest so signing does not mutate the
evidence root.

Require complete, checksum-verified bundles for signing. Verification must repeat
bundle integrity checks, validate both digest bindings, and authorize the signed
identity through an externally maintained OpenSSH `allowed_signers` file. Refuse
implicit overwrites and never copy private keys into evidence bundles.

## Consequences

Publication consumers can authenticate both content and publisher using standard
OpenSSH tooling. Trust remains local and explicit rather than globally inferred.
Encrypted keys may require an agent or interactive OpenSSH support; automated CI
must provision signing authority deliberately.

## Alternatives considered

- Self-sign and trust any embedded public key: rejected because it proves integrity
  but not publisher identity.
- Add a package-specific Ed25519 implementation: rejected because bespoke key
  formats and verification code expand the security surface.
- Sign each artifact separately: rejected because the manifest already forms a
  complete checksum tree and one signature is easier to review and rotate.

## Revisit trigger

Add Sigstore or archival-service attestations when a concrete repository or DOI
workflow requires transparency-log identity, keyless CI signing, or long-term
timestamping. Preserve the exact manifest-binding invariant.

## Evidence added later

None yet.
