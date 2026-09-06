# Security Policy

## Supported version

GenReplay is currently alpha (`0.1.x`). Security fixes are applied to the latest release line.

## Reporting a vulnerability

Please open a private GitHub security advisory for vulnerabilities that could cause GenReplay to misrepresent capsule integrity, execute unintended network-changing operations, disclose secrets, or mis-handle untrusted archives.

For ordinary bugs, use the public issue tracker.

## Threat model

### Untrusted RPC responses

RPC data is untrusted input. GenReplay validates JSON-RPC envelopes and records source endpoint/chain metadata, but a malicious RPC can still lie about chain history. For high-assurance investigations, capture from independently operated nodes and compare capsules.

### Untrusted capsules

Capsules are ZIP files. GenReplay reads only manifest-declared entries and does not extract them to arbitrary filesystem paths during normal inspection/replay. Digest verification is enabled by default.

### Secrets

GenReplay does not require private keys for capture or `gen_call` replay. Do not place wallet keys, API tokens or provider credentials into scenario notes or capsules.

### Sensitive state/logs

A capsule may contain contract state, source, stderr/stdout and GenVM logs. Review it before publishing.

### Read-only network behavior

The implemented RPC workflow uses read/debug calls and `gen_call`, which executes without creating a blockchain transaction. GenReplay v1 contains no transaction-signing code.
