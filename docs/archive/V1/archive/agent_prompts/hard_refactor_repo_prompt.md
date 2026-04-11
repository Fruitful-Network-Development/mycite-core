You are performing a hard refactor of the repo.

This is not a compatibility-first cleanup.
Prefer breaking legacy surfaces now and rebuilding later over preserving confusing ownership and duplicated logic.
The goal is to make the architectural separations dominant in the repo layout, module ownership, naming, and code paths.

Authoritative architecture to enforce

1. Contract line state
Contracts are the canonical communication-line record state.
They own:
- line identity
- peer ids
- contract status/type/policy
- typed line payload registry/history
- payload version records
- shared-context objects carried on that line

Contracts do not own:
- raw cryptographic key material
- public publication
- imported reference registry state
- generic resource sync bookkeeping
- UI-thread/event presentation logic

2. Vault-backed key/session management
Vault/session logic owns:
- private key material
- symmetric key material
- handshake crypto operations
- nonce/replay policy
- session activation and renewal mechanics
- session references back to contract lines

Contract lines may point to session/key refs, but do not own crypto material.

3. Externally meaningful system events
There is one canonical external event stream for all externally meaningful system events.
It is not `request_log` in architecture, even if legacy names still exist in the repo.
Local-only operational chatter belongs in local audit, not the canonical external stream.

4. Publication and reference exchange
Public publication is independent from contracts.
Resources are native-portal artifacts.
References are network-carried forms.
Imported references, exported references, and sandbox-local decoded copies must be treated explicitly as such.

5. Payload typing and versioning
Line payloads are the dominant contract model.
Payload handling must be uniform:
- typed
- timestamped
- hashed
- revisioned/versioned
Top-level compatibility mirrors should be removed unless truly essential during the cutover.

6. Unified SYSTEM shell remains primary
Do not solve any ownership fault by moving logic into tools or flavor apps.
Core subsystem boundaries must become clearer, not more distributed.
