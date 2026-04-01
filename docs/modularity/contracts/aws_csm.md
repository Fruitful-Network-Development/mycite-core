# AWS CSM Tool

- Owns: AWS onboarding/backend logic, AWS tool contracts, AWS state adapter,
  AWS migrations.
- Does not own: portal runtime bootstrap, generic service-tool catalog rules,
  unrelated tool state.
- Reads: instance-scoped AWS tool state under
  `private/utilities/tools/aws-csm/`.
- Writes: AWS profile JSON and action/provision logs inside that tool bubble.
- Depends on: `tools/_shared`, `portal_core/shared`, `portal_core/shell`.
- Depended on by: FND admin integrations and future dedicated AWS tool routes.

