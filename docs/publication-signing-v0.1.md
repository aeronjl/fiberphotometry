# Publication manifest signing v0.1

FiberPhotometry authenticates a completed evidence bundle with a detached OpenSSH
signature. The signed payload is a canonical JSON attestation binding the exact
`manifest.json` SHA-256, project fingerprint, signer identity, signing time,
signature method, and a fixed application namespace.

## Why an attestation

The manifest already binds every analysis, report, and NWB artifact by checksum.
Signing its digest authenticates that complete evidence root without modifying the
manifest after signing. The detached signature and attestation remain external to
the manifest and can be copied alongside the bundle.

Only bundles with a verified manifest and `complete` status may be signed. Signing
refuses to replace existing files unless the caller explicitly requests overwrite.

## OpenSSH trust model

The namespace is fixed to
`fiberphotometry-publication@aeronjl.github.io`, preventing a signature made for a
different application from being accepted here. Verification supplies the signed
identity to `ssh-keygen -Y verify` and requires a matching key in an independently
maintained `allowed_signers` file. Restricting each entry with a `namespaces=`
option is strongly recommended.

OpenSSH documents that `-Y sign` accepts a private key or a public key backed by
`ssh-agent`, that namespaces provide domain separation, and that `-Y verify`
requires an identity and allowed-signers file and reports success through exit
status zero: [OpenSSH `ssh-keygen(1)`](https://man.openbsd.org/OpenBSD-7.6/ssh-keygen.1).

## Verification sequence

`verify_publication_manifest`:

1. verifies every ordinary artifact against `manifest.json`;
2. strictly parses attestation schema v1;
3. recalculates and compares the manifest and project fingerprints;
4. verifies the detached SSHSIG under the fixed namespace;
5. requires the signed identity to be authorized by `allowed_signers`.

The verifier returns a `PublicationVerification` only after all five checks pass.
Trust files and private keys must not be stored inside the publication bundle.
