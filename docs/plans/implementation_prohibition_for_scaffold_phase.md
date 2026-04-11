# Implementation Prohibition For Scaffold Phase

Authority: [authority_stack.md](authority_stack.md)

During the scaffold phase, future agents must not:

- implement working domain logic
- create runtime routes
- add adapter logic
- add tool behavior
- recreate v1 modules behind new names
- add compatibility shims not already demanded by a phase doc

Allowed work in the scaffold phase:

- directory creation
- inert `__init__.py`
- README and contract files
- ontology, ADR, migration, and test-planning documents

If a change would reasonably be described as “starting the application code,” it is prohibited in this phase.
