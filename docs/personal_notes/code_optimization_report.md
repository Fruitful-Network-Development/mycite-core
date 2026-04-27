# Investigation into CTS‑GIS semi‑legacy concerns and performance optimizations (mycite‑core repo)

## Background – original concerns

The CTS‑GIS tool is a core part of the **MyCite** portal used to navigate county tract survey (CTS) geospatial data. In the past it was developed as a **“read‑only portal tool”** that assembled large geospatial surfaces at runtime. A discussion uploaded by the user (summarised in “Pasted text.txt”) noted that the tool contained **heavy runtime logic** that validated requests, decoded row chains, built geometry models, checked fallback conditions, and assembled large UI payloads. This made the tool **slow** and hard to maintain. The analysis recommended that the runtime be split into a thin layer and replaced with **pre‑compiled artifacts**, along with stricter invariants and simplified interfaces to reduce complexity and improve performance.

This report investigates whether these semi‑legacy concerns have been addressed within the mycite‑core repository and provides recommendations for further optimization.

## Evidence of modernization and new contracts

### 1\. One‑shell portal refactor and stability program

A document dated 2026‑04‑21 outlines a **one‑shell portal refactor** plan. It sets **freeze rules**: no new shell regions and no widening of CTS‑GIS queries. The plan aims to **stabilize the portal** by centralizing shell authority, unifying normalization, and adopting a single universal widget host. It notes that current CTS‑GIS functionality suffers from **environment‑sensitive failures** due to data drift and recommends hardening fixtures without relaxing shell contracts[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md#L1-L199). This plan aligns with the user’s goal to reduce complexity and suggests a governance structure to prevent further drift.

### 2\. Compiled artifact approach

The repository introduces a compiled path to remove heavy runtime computation:

* **Compilation script:** MyCiteV2/scripts/compile\_cts\_gis\_artifact.py builds a **compiled artifact** for CTS‑GIS. The script imports the read‑only service and uses build\_compiled\_artifact to generate a navigation model, projection model, evidence and invariants, writing the result to a compiled file[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/scripts/compile_cts_gis_artifact.py#L21-L48). This moves many expensive operations (e.g., decoding lineage and computing projections) from runtime to an **offline build step**.

* **Compiled artifact contract:** The cts\_gis\_compiled\_artifact\_contract.md defines the schema for compiled artifacts. It requires fields such as navigation\_model, projection\_model, and evidence\_model, along with invariants enforcing one authority and one namespace[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/modules/cross_domain/cts_gis/compiled_artifact.py#L167-L188). The contract also ensures that dropdown options are **transport‑safe**[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_compiled_artifact_contract.md#L44-L53). This formalizes the expectation that runtime will read pre‑validated, static data rather than recomputing surfaces.

* **Operating contract:** The cts\_gis\_operating\_contract.md describes two runtime modes: **production\_strict** and **audit\_forensic**. In production\_strict mode, the tool fails fast if a compiled artifact is missing or invalid and never falls back to the heavy runtime service. audit\_forensic mode allows raw reconstruction for diagnostics but is not used in production[\[5\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_operating_contract.md#L2-L20). This ensures that production relies exclusively on pre‑compiled data and eliminates expensive fallback logic.

* **Runtime implementation:** portal\_cts\_gis\_runtime.py implements these contracts. When a compiled artifact exists and is valid, the runtime reads the artifact and uses its navigation and projection models to build the surface. If the artifact is invalid or absent and audit\_forensic mode is enabled, it falls back to CtsGisReadOnlyService to rebuild and write a new compiled artifact. The runtime also defines canonical actions (select\_node, set\_intention, set\_time, etc.) that operate on the compiled navigation model and update the tool state. By default in production the fallback path is disabled, addressing the slowness from heavy runtime logic.

### 3\. Integration with SAMRAS state machine and UI refactoring

A development note (development\_notes\_cts\_gis\_and\_state\_machine\_directives.md) outlines how the CTS‑GIS tool should integrate with the new **SAMRAS** state machine. It warns that SAMRAS is the authoritative structural engine and that the navigation tree must not be derived from administrative rows. The document emphasises that UI overlays must maintain the structural tree—the engine must manage **attention**, **intention**, and **time** contexts, and the UI cannot reorder or mutate the tree[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L26-L39). The plan introduces a new **“Garland”** geospatial projection section and suggests reorganizing precincts sources for performance[\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L36-L46).

The note includes a **gap assessment and recommendations**: validating HOPS entries, modularizing large JSON files, verifying authority chains, and designing directives for Garland to unify UI semantics[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L79-L94). These recommendations align with the compiled artifact approach by moving heavy validation and assembly offline and ensuring structural integrity.

### 4\. Portal UI and tools audit

Other documents highlight mismatches and provide further context:

* **UI mismatch report** (tools\_ui\_implementation\_mismatch\_report\_2026-04-16.md): lists contract, projection, renderer, mode and fallback mismatches across tools, noting that CTS‑GIS lacks parity in loading and error semantics and recommending consolidation[\[9\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L37-L41). This underscores the need for a unified implementation.

* **Portal work writings** (v2.5portal\_work\_writtings.md): describes plans to normalize the control panel and interface panel, restructure the CTS‑GIS UI into a two‑pane layout (“Diktataograph” and “Garland”), unify terminology, and align time and intention states with SAMRAS. This indicates an effort to simplify the UI and align it with the compiled data model.

* **Runtime authority report** (mos\_runtime\_authority\_and\_access\_reality\_report\_2026-04-21.md): while primarily about MOS/SQL, it notes that runtime modules sometimes load incorrectly due to environment drift, highlighting the importance of compiled artifacts.

## Evaluation of whether concerns have been addressed

The new infrastructure demonstrates **significant progress** toward addressing the semi‑legacy concerns:

1. **Pre‑compiled artifacts:** The introduction of compile\_cts\_gis\_artifact.py and the compiled artifact contract confirms that heavy computations (geometry decoding, lineage building, projection generation) can be done offline. Runtime now reads the compiled artifact and operates only on static models, eliminating the previous expensive on‑the‑fly calculations.

2. **Fail‑fast production mode:** The operating contract ensures that production will only serve compiled artifacts. The fallback to the heavy runtime service is restricted to audit mode, preventing performance degradation in the user portal.

3. **Structural integrity and SAMRAS integration:** The development notes emphasise that the state machine must drive navigation and that UI overlays cannot mutate structural trees. The plan to centralize SAMRAS authority and unify the navigation model ensures that the compiled artifact remains consistent with the authoritative data.

4. **UI refactoring:** Work writings and the mismatch report show ongoing efforts to standardize the portal UI and reduce implementation drift. By removing duplicate headers, normalizing the control panel, and aligning states across tools, the portal can more effectively leverage the compiled data without additional complexity.

Despite these improvements, some areas require further attention:

* **Normalization and duplication:** The one‑shell refactor plan acknowledges that normalization is still fragmented across regions and tools. Consolidating normalization logic into a single module and enforcing freeze rules will help prevent future drift.

* **Large JSON sources:** The gap assessment notes that some HOPS and precinct files are large and inconsistent. Modularizing these sources and adding validation scripts can reduce parsing overhead and make compilation more robust[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L79-L94).

* **Diagnostic vs. production mode:** While audit mode allows reconstructing the surface, there is a risk that developers use it during normal usage and inadvertently accept slower performance. Clear guidelines and CI checks should ensure production always uses compiled artifacts.

* **Garland and profile projections:** The Garland section is still conceptual. Once implemented, compiled artifacts should incorporate the new data and ensure that the UI properly separates geospatial rendering from textual profile data.

* **UI semantics and concurrency:** The mismatch report highlights differences in error handling and fallback semantics across tools. Consolidating these semantics and ensuring that navigation decode readiness and evidence readiness invariants are respected will improve user experience and reliability.

## Recommendations for further optimization

1. **Enforce compiled artifact usage:** Introduce CI tests that refuse to start the portal if a valid compiled artifact is missing or outdated. Provide a script in the build pipeline to generate updated artifacts whenever source evidence changes.

2. **Centralize normalization and authority logic:** Implement a shared normalization module that all tools (CTS‑GIS, AWS‑CSM, FND‑EBI) use. Follow the freeze rules and unify the get\_region\_payload functions to avoid duplicate conversions and mismatches.

3. **Modularize data sources:** Break large HOPS and precinct JSON files into smaller modules grouped by HOPS ID or region. Provide validation scripts to ensure each module meets the SAMRAS invariants (one authority, one namespace) before compilation[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L79-L94).

4. **Simplify runtime code paths:** Remove dead code and heavy fallback branches from CtsGisReadOnlyService now that the compiled path is authoritative. Retain the fallback only in a separate diagnostic module, reducing the runtime footprint and improving readability.

5. **Implement caching/invalidation:** When compiled artifacts are generated, embed a generated\_at timestamp and portal\_scope\_id as defined in the contract[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/modules/cross_domain/cts_gis/compiled_artifact.py#L167-L188). At runtime, check these fields to ensure the artifact is still valid; if not, trigger regeneration. This helps maintain consistency without manual intervention.

6. **User interface and accessibility:** Continue refactoring the UI to clearly separate the Diktataograph (navigation/profile) and Garland (geospatial) panes. Provide lazy loading for large map layers and implement progressive disclosure of detail to reduce initial load times.

7. **Documentation and training:** Maintain up‑to‑date documentation on how to compile artifacts, run the portal in production and audit modes, and integrate with SAMRAS. Train developers to avoid using audit mode for performance tests.

## Conclusion

The mycite‑core repository has made **substantial progress** toward addressing the semi‑legacy concerns about CTS‑GIS slowness and complexity. By introducing pre‑compiled artifacts, enforcing strict runtime modes, and planning UI and normalization refactors, the project is moving away from the heavy runtime computations that previously slowed the portal. Remaining tasks involve unifying normalization, modularizing data, implementing the Garland projection, and consolidating UI semantics. Following the recommendations above will help complete the migration to a clean, efficient, and maintainable CTS‑GIS tool.

---

[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md#L1-L199) one\_shell\_portal\_refactor.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one\_shell\_portal\_refactor.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md)

[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/scripts/compile_cts_gis_artifact.py#L21-L48) compile\_cts\_gis\_artifact.py

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/scripts/compile\_cts\_gis\_artifact.py](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/scripts/compile_cts_gis_artifact.py)

[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/modules/cross_domain/cts_gis/compiled_artifact.py#L167-L188) compiled\_artifact.py

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/modules/cross\_domain/cts\_gis/compiled\_artifact.py](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/modules/cross_domain/cts_gis/compiled_artifact.py)

[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_compiled_artifact_contract.md#L44-L53) cts\_gis\_compiled\_artifact\_contract.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts\_gis\_compiled\_artifact\_contract.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_compiled_artifact_contract.md)

[\[5\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_operating_contract.md#L2-L20) cts\_gis\_operating\_contract.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts\_gis\_operating\_contract.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/contracts/cts_gis_operating_contract.md)

[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L26-L39) [\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L36-L46) [\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L79-L94) [\[9\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md#L37-L41) development\_notes\_cts\_gis\_and\_state\_machine\_directives.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal\_notes/CTS-GIS-prototype-mockup/development\_notes\_cts\_gis\_and\_state\_machine\_directives.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/personal_notes/CTS-GIS-prototype-mockup/development_notes_cts_gis_and_state_machine_directives.md)