# Recreation Sequence

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Future implementation must recreate v1 concepts in this order:

1. Core structures and utilities
   - datum refs, identities, HOPS, SAMRAS, MSS, crypto splits
2. State machine
   - AITAS, NIMM, Hanus shell, mediation surface
3. Ports
   - datum store, payload store, audit log, event log, session keys, time projection, resource resolution, shell surface
4. Domain and cross-domain modules
   - contracts, publication, reference exchange, external events, local audit
5. Adapters
6. Tools
7. Sandboxes
8. Runtime composition

## Recreation warning

If a future agent feels pressure to implement a later step because a current step is underspecified, the correct action is to update the earlier authority surface, not to skip the order.
