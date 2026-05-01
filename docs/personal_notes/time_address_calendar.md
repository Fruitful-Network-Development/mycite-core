# Agent Prompt for Time-Address Calendar

One correction should be made explicit before handing this to the agent: `13-787-2026-3-26` is not safely orderable by plain string sort unless the segments are normalized or compared numerically by segment position. The implementation should therefore define a canonical parser/comparator for mixed-radix time addresses and never rely on raw lexical ordering.

Implement a first-pass time-address calendar/workbench facet for the portal, using the attached visual reference as the target composition and using the existing SYSTEM shell/state-machine architecture already present in the repo.

Primary intent

This is not a normal calendar-event system. It is a deterministic time-address selector for contextualized objects. The user will select a year, month, or day, and that selected time address will be used in parallel with location/grouped objects so the workbench can show only the objects valid for that selected time scope.

This must be implemented in a way that fits the existing unified SYSTEM workbench model, not as a new mini-app or alternate shell. The SYSTEM page is already declared as a single canonical stateful workbench driven by attention, directive, and contextual facets, and tools/providers must remain subordinate to that shell state rather than inventing new page logic or top-level navigation. Preserve that architecture. :contentReference[oaicite:0]{index=0}

Relevant architectural framing already established in repo context

- The SYSTEM runtime is a state machine over canonical attention targets and directives, not a tabbed collection of sub-apps. Attention should continue to resolve to file/datum/facet, and the time UI should fit as a time facet or time mediation layer rather than a new shell. :contentReference[oaicite:1]{index=1}
- The declaration already identifies `time` as a first-class facet kind and says time context should only be active when time is explicitly being mediated. Keep that behavior. :contentReference[oaicite:2]{index=2}
- Tools/providers must remain providers, not shells. AGRO-ERP behavior should be added as capability within the unified shell. :contentReference[oaicite:3]{index=3}
- The SAMRAS document is relevant only as a modeling precedent: human-facing interaction should edit/select addresses while engine/core code owns validation, normalization, and canonical rebuild/write behavior. Do not make the UI responsible for raw address semantics. Do not overcomplicate this into encoded/decoded SAMRAS. Use the same discipline of engine-owned address logic and UI-owned address interaction. :contentReference[oaicite:4]{index=4}

What this time system is

Create a human-readable mixed-radix time address system that can represent different levels of specificity in the same ordered structure.

Examples:
- today: `13-787-2026-3-26`
- a whole century-level reference example: `13-786-979`

Important semantic rules:
1. Addresses are ordered by canonical address comparison, not raw string comparison.
2. Omitted trailing segments mean the address refers to the whole enclosing scope at that specificity level.
3. Time ranges must have start and end on the same specificity level.
4. If a range crosses multiple days and one side is more specific, the less specific side must be expanded to that same depth instead of mixing depths.
   Example:
   - invalid conceptual pair: `["13-787-2026-3-26", "13-787-2026-3-27-8-7"]`
   - normalized valid form: `["13-787-2026-3-26-0-0", "13-787-2026-3-27-8-7"]`
5. If an item refers to a single full day, start and end may be identical.
6. This first implementation only needs a year / month / day selection UI, but the parsing/validation model should already support deeper specificity such as hour and minute.

Do not redesign the user’s chosen cosmological prefixing scheme. Retain the existing address shape and examples exactly as given by the user. Do not reinterpret this into ISO timestamps or standard event objects internally as the primary authority. You may derive helper values for rendering, but the canonical authority must remain the mixed-radix time address model.

Visual target

Use the attached image as the design reference for the first-pass interface. The important compositional aspects are:
- a central year focus
- left/right year navigation controls
- a month-selection structure integrated into the visual, not a generic grid calendar
- a dense outer day/tick band suggesting ordinal day positions
- a workbench-style composed selector rather than a commodity calendar widget

This should be visually faithful in composition, but it does not need to implement every future layer immediately. Build the first working version around selecting:
- year
- month
- day

Keep the structure open for later expansion into more complex timeline/time-band interactions.

Implementation requirements

1. Audit the repository first and identify the actual shell/state/workbench modules, the current SYSTEM page implementation, and the appropriate extension points for a time facet/provider. Do not invent new root architecture if the repo already has the right seams.

2. Implement this as a time mediation/facet inside the existing shell model:
- no alternate top-level page
- no separate calendar application shell
- no parallel navigation model
- no hard fork of AGRO-ERP UI

3. Introduce an engine-owned time address module with at least:
- parse_time_address(address: str) -> structured segments
- compare_time_addresses(a, b) -> deterministic ordering by segment position/value
- normalize_time_address(address) -> canonical string form
- infer_specificity(address) -> year/month/day/hour/minute/etc.
- normalize_range(start, end) -> same-depth validation/repair when allowed
- contains_address(container, candidate) for scope matching
- same_scope(selected_scope, object_range) to support filtering
- helper functions to derive year/month/day projections for the UI

4. Define the canonical time-address rules in code and comments. Do not scatter time parsing logic across templates/components/routes.

5. The UI should drive a selected time context value and filter contextualized objects by that value. For this first pass, selecting:
- a year shows objects whose range intersects that year scope
- a month shows objects whose range intersects that month scope
- a day shows objects whose range intersects that day scope

6. Introduce or extend state in a way consistent with the existing SYSTEM declaration. The natural fit is:
- keep current attention model intact
- use a `time` facet or time mediation context
- set/clear `time_context` canonically
- ensure resets follow the existing reset model when attention/file/directive changes. :contentReference[oaicite:5]{index=5}

7. The selection UI must not directly own domain filtering semantics. It should emit a clean selected time context and let a core/service layer resolve filtering.

8. Create a minimal but real data contract for time-addressed objects. For this first pass, support something like:
```json
{
  "time_stamp": ["13-787-2026-3-26", "13-787-2026-3-26"],
  "location_id": "…",
  "object_id": "…"
}
```

and multi-day/time examples such as:

```json
{
  "time_stamp": ["13-787-2026-3-26-0-0", "13-787-2026-3-27-8-7"],
  "location_id": "…",
  "object_id": "…"
}
```

9. Explicitly reject invalid mixed-specificity ranges unless normalization rules define the conversion.

10. Preserve future extensibility for:

* hour/minute selection
* broader historical ranges
* non-day-only object scopes
* richer timeline bands
* location/time co-filtering

Expected deliverables

Return:

1. a concise repo audit showing the exact files/modules touched and why
2. a short design note defining the time-address grammar, specificity levels, comparator behavior, and range-normalization rules
3. the implementation
4. any new tests
5. a brief explanation of how the selected time context flows through the existing SYSTEM state model
6. a note on what is intentionally deferred

Guardrails

* Do not convert this into a standard CRUD calendar-event feature.
* Do not introduce a second shell.
* Do not rely on lexical string sorting for mixed-radix addresses.
* Do not overfit to Gregorian library assumptions as the system of record.
* Do not overengineer this into SAMRAS encoding; keep it human-readable, deterministic, and engine-validated.
* Do not break existing AGRO-ERP or SYSTEM shell homogeneity.
* Prefer a clean first slice that correctly models year/month/day selection and canonical time-address behavior.

If there are ambiguities in unused future radices, preserve the user’s examples and implement the first slice with year/month/day UI plus hour/minute-capable parsing and validation, leaving deeper cosmological/time-base interpretation documented but not overcommitted.

The two architectural anchors for this prompt are that the SYSTEM page remains one stateful workbench with attention/directive/time as derived state, not a new sub-application :contentReference[oaicite:6]{index=6}, and that address logic should be owned by engine/core code while the UI operates on address-level interaction rather than raw low-level semantics :contentReference[oaicite:7]{index=7}.
