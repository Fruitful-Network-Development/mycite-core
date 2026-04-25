# Audit & Refactor Guidance for mycite‑core

Date: 2026-04-24

Doc type: `diagnosis-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Planning Registry

- Canonical seed report for stream: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Canonical active plan: `docs/plans/code_bloat_deep_audit_program_plan_2026-04-24.md`
- Follow-on audit task IDs: `TASK-CODE-BLOAT-AUDIT-001`, `TASK-CODE-BLOAT-AUDIT-002`, `TASK-CODE-BLOAT-AUDIT-003`, `TASK-CODE-BLOAT-AUDIT-004`, `TASK-CODE-BLOAT-AUDIT-005`, `TASK-CODE-BLOAT-AUDIT-006`, `TASK-CODE-BLOAT-AUDIT-007`
- Lifecycle note: this report remains the diagnosis seed; the seven follow-on audit plans define deeper evidence collection and do not mark the audits complete.
- Corrective execution follow-on stream: `STREAM-CODE-BLOAT-REMEDIATION`
  with tasks `TASK-CODE-BLOAT-REMEDIATION-001` through
  `TASK-CODE-BLOAT-REMEDIATION-008`, tracked in
  `docs/plans/code_bloat_remediation_execution_plan_2026-04-25.md` and
  `docs/audits/reports/code_bloat_remediation_execution_report_2026-04-25.md`.

## Deep Audit Plan Evidence Matrix

The contextual planning loop completed the planning phase for the seven
follow-on audit tasks. These entries evidence audit-plan readiness only; they
do not assert that the audits or remediation work have been performed.

| Task ID | Audit plan | Problem area extended | Planning evidence |
| --- | --- | --- | --- |
| `TASK-CODE-BLOAT-AUDIT-001` | `docs/audits/code_bloat_shell_topology_audit_plan_2026-04-24.md` | Multi-shell complexity, renderer branching, first-load divergence | Requires route-to-renderer reachability, active/historical shell-path classification, deletion-candidate risk, and regression gates. |
| `TASK-CODE-BLOAT-AUDIT-002` | `docs/audits/code_bloat_legacy_filesystem_snapshot_audit_plan_2026-04-24.md` | Legacy filesystem code, JSON bootstrap paths, deployed snapshots | Requires authority proof, runtime reachability, repository-footprint accounting, archival disposition, and retained-exception rationale. |
| `TASK-CODE-BLOAT-AUDIT-003` | `docs/audits/code_bloat_python_import_modularity_audit_plan_2026-04-24.md` | Heavy imports and monolithic Python modules | Requires import-time profiling, import graph ownership, module-size thresholds, side-effect review, and lazy-import safety classification. |
| `TASK-CODE-BLOAT-AUDIT-004` | `docs/audits/code_bloat_data_io_caching_audit_plan_2026-04-24.md` | Large JSON/data payloads, synchronous I/O, missing cache boundaries | Requires route timing, payload-size accounting, freshness classification, invalidation design, and failure-mode review. |
| `TASK-CODE-BLOAT-AUDIT-005` | `docs/audits/code_bloat_frontend_bundle_audit_plan_2026-04-24.md` | Monolithic frontend assets and first-load script weight | Requires asset sizing, parse/execute assessment, route-level dependency maps, cache/compression review, and no-second-frontend-stack constraints. |
| `TASK-CODE-BLOAT-AUDIT-006` | `docs/audits/code_bloat_normalization_drift_audit_plan_2026-04-24.md` | Duplicated normalization helpers and behavioral drift | Requires contract-linked helper inventory, equivalence fixtures, alias review, security/correctness analysis, and canonical ownership decisions. |
| `TASK-CODE-BLOAT-AUDIT-007` | `docs/audits/code_bloat_test_tooling_overhead_audit_plan_2026-04-24.md` | Test fixture/import overhead and missing bloat-regression tooling | Requires test import timing, fixture duplication review, suite partitioning analysis, maintainability gates, and closure-confidence preservation. |

## Repository overview

mycite‑core is the canonical source for the live MyCite portal shell. The README describes the runtime boundaries and key entry points: the V2 portal code lives under MyCiteV2, deployment snapshots reside in deployed, and runtime state lives under /srv/mycite-state/instances/[\[1\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md#:~:text=,exceptions%20outside%20SQL%20datum%20authority). The portal is built around a shell that orchestrates several tools (AWS‑CSM, CTS‑GIS, FND‑DCM, FND‑EBI and Workbench UI) using a complex state‑machine and multiple region renderers[\[2\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md#:~:text=). A separate set of docs defines contracts for the shell, routing, surface catalogues and tool operations, and there are numerous audit reports and plan documents.

The portal load time (\~20 seconds) and the size of the codebase suggest that the project has accumulated significant technical debt. Below is an aggressive analysis of the core issues along with recommendations to cut bloat and improve maintainability.

## Identified issues & bloat points

### 1 Multi‑shell complexity and branching

The repository still contains support for multiple shell variants and numerous branch‑specific renderers. The "One‑Shell Portal Refactor" plan acknowledges this and imposes **freeze rules**: no new shell regions or renderer kinds should be introduced and no query‑widening for CTS‑GIS tool navigation[\[3\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=%23%23%20Non). It also defines a **wave‑based stability programme** to centralize shell authority, unify normalization boundaries and reduce region payload families[\[4\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=,load%20posture). The fact that such a plan is necessary indicates that the current architecture suffers from duplicated normalization logic and divergent first‑load behaviours.

* **Impact:** Having multiple shell branches increases code size, inflates the number of files that need to be loaded and parsed, and introduces subtle bugs. It also spreads normalization logic across modules, making it difficult to understand and optimize request handling.

### 2 Legacy filesystem code and preserved snapshots

Audit documents show that the MOS cut‑over program retired the legacy filesystem authority for migrated SYSTEM surfaces and replaced it with SQL‑backed authority[\[5\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,migration%2C%20parity%2C%20or%20fixture%20support). However, it notes that **remaining filesystem parsing/bootstrap code is retained** only for migration parity and test support[\[5\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,migration%2C%20parity%2C%20or%20fixture%20support). This leftover code and the numerous snapshots under deployed likely contribute to the repository’s bloat.

* **Impact:** Old adapters that scan the filesystem or parse large JSON files (e.g., anthology.json or system\_log.json) still exist in the runtime code, even though SQL is now authoritative. Loading these files during portal initialization can slow down startup.

### 3 Heavy global imports and monolithic modules

The portal host (app.py) imports a large number of runtime modules and registers tool surfaces at the top of the file[\[6\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=from%20MyCiteV2,PORTAL_RUNTIME_ENVELOPE_SCHEMA%2C%20SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA%2C%20WORKBENCH_UI_TOOL_REQUEST_SCHEMA%2C%20build_tool_exposure_policy%2C). Monolithic modules like portal\_shell\_runtime.py are over 1,000 lines long[\[7\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py#:~:text=from%20__future__%20import%20annotations), making them difficult to navigate and leading to lengthy import times. The Medium article on Python start‑up performance notes that large import trees can cause significant delays and recommends using python \-X importtime and the tuna tool to profile imports[\[8\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=In%20order%20to%20understand%20what,we%20focused%20on%20Python%20imports). It also advises moving initialization code out of \_\_init\_\_.py files and splitting huge files into smaller, more focused modules[\[9\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files).

* **Impact:** Importing all tool‑specific modules on startup causes the portal to load code paths that may not be needed for the first request. Large files with many classes or functions hinder readability and hinder Python’s ability to lazily import only what is required.

### 4 Large JSON assets and synchronous I/O

The contract documents explain that SYSTEM anchors like anthology.json and logs like system\_log.json are core to the portal[\[10\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/contracts/portal_shell_contract.md#:~:text=). If these files are read synchronously during startup, they can block the event loop. app.py uses a helper \_load\_optional\_json\_object() that reads a JSON file with path.read\_text()[\[11\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=def%20_load_optional_json_object%28path%3A%20Path%29%20,payload%2C%20dict%29%20else). Without caching, repeatedly reading large JSON files for each request can be expensive.

* **Impact:** Synchronous file reads during initialization or request handling increase latency and memory usage, especially when the files are large or stored on network‑attached storage.

### 5 Monolithic JavaScript bundles

The portal host registers multiple front‑end modules (v2\_portal\_shell\_core.js, v2\_portal\_system\_workspace.js, etc.) and treats them as a single bundle[\[12\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=,%7D%2C%20%29%2C%20%7D%2C). These bundles are probably compiled without code splitting or tree‑shaking. Google’s performance guidance notes that **loading large JavaScript resources blocks the main thread** and causes delayed interaction; splitting your JavaScript into smaller chunks and only downloading what is necessary improves responsiveness[\[13\]](https://web.dev/learn/performance/code-split-javascript#:~:text=Loading%20large%20JavaScript%20resources%20impacts,improve%20your%20page%27s%20%2048).

* **Impact:** A single large bundle forces browsers to download, parse and execute all code up front, even if many tools or renderers are not used immediately. This contributes to the 20‑second portal load time.

### 6 Lack of caching, lazy loading and asynchronous I/O

There is little evidence of server‑side caching or asynchronous file/database access in the runtime code. Data‑store adapters return complete payloads, and the Flask app does not appear to use caching middleware or HTTP caching headers. The Medium article demonstrates that deferring expensive imports until functions are called (local imports) and using relative imports for heavy modules like numpy or AWS SDKs can reduce startup time[\[14\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files).

* **Impact:** Without caching or deferred loading, each request triggers full initialization of services and data retrieval. For AWS‑CTS tools, repeated loading of AWS SDKs or large manifest files may be wasting CPU cycles.

### 7 Code duplication and inconsistent normalization

Multiple normalization helpers exist across runtime modules. The refactor plan specifically calls out the need to “remove request/query drift caused by duplicated normalization logic” and “enforce request/query normalization through one shared helper layer”[\[15\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=,load%20posture). Redundant logic increases the codebase size and makes it hard to audit for security or correctness.

### 8 Testing and audit overhead

The audit reports list numerous unit tests that must pass for closure[\[16\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,m%20unittest). While comprehensive testing is critical, the test suite may be slowed by heavy fixtures or redundant test helpers. Splitting large test factories and using fixture caching can reduce execution time.

## Recommendations

The following steps focus on cutting bloat, improving maintainability and making the codebase test‑friendly. Many of these are already hinted at in the one\_shell\_portal\_refactor plan; the aim here is to provide concrete actions.

### 1 Consolidate to a single shell and remove unused paths

* **Complete the one‑shell migration.** Follow the freeze rules and remove unused shell regions or renderer families[\[3\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=%23%23%20Non). All tools should communicate through the canonical build\_shell\_composition\_payload(); delete branch‑specific dispatchers and adapters.

* **Centralize request normalization.** Implement a shared normalization utility and replace duplicated per‑surface normalization functions. This reduces cognitive overhead and ensures consistent query handling[\[15\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=,load%20posture).

### 2 Remove legacy filesystem code and unused snapshots

* **Delete unused adapters.** Since SQL is the authoritative source for SYSTEM surfaces, drop filesystem adapters and legacy bootstrapping code, retaining them only in a separate migration or test support repository[\[5\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,migration%2C%20parity%2C%20or%20fixture%20support).

* **Archive or prune deployed snapshots.** Preserved deployment snapshots contribute to repository size and are rarely referenced in runtime. Move them to a separate archival repository or S3 bucket. Keep only the latest snapshot needed for regression testing.

### 3 Refactor imports and modularize code

* **Profile imports.** Use python \-X importtime and tuna to identify modules that dominate startup time[\[8\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=In%20order%20to%20understand%20what,we%20focused%20on%20Python%20imports). Focus on modules that import AWS SDKs, large JSON helpers or heavy scientific libraries.

* **Move initialization code out of \_\_init\_\_.py.** Avoid executing business logic at module import time; instead, put initialization in dedicated functions or class methods[\[17\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files).

* **Split large files.** Break monolithic modules (e.g., portal\_shell\_runtime.py) into smaller modules grouped by domain. The Medium article highlights that a 5 000‑line test factory file with 300 imports was a major source of bloat, and splitting it improved performance[\[18\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Break%20down%20big%20files%20into,smaller).

* **Use local imports for heavy dependencies.** For modules that are only used under certain conditions (e.g., AWS SDKs, geospatial libraries or large third‑party packages), import them inside functions so they load only when needed[\[19\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=What%3F).

### 4 Migrate to streaming and caching for large data

* **Stream large JSON files or migrate them entirely to SQL.** Avoid reading the entire anthology.json or system\_log.json on each request. Instead, load these data lazily into a cache (e.g., Redis) at startup or replace them with SQL queries with pagination. Provide endpoints that stream results for large logs.

* **Implement server‑side caching.** Use Flask caching (e.g., Flask‑Cache or a reverse proxy) to cache static responses such as the portal shell composition and tool surface schemas. For assets that rarely change, add Cache‑Control headers.

### 5 Optimize front‑end bundles

* **Implement code splitting.** Adopt Webpack (or similar) chunking to produce separate bundles for core shell, each tool and shared vendor code. Only load the JS modules needed for the currently viewed tool. Google’s guidance notes that splitting JavaScript into smaller chunks and deferring non‑critical code improves responsiveness and reduces blocking[\[13\]](https://web.dev/learn/performance/code-split-javascript#:~:text=Loading%20large%20JavaScript%20resources%20impacts,improve%20your%20page%27s%20%2048).

* **Tree‑shake and minify.** Remove unused exports in JS modules and ensure the bundler performs tree‑shaking. Use Brotli or gzip compression for the bundles.

* **Defer loading of heavy third‑party libraries.** For example, load AWS‑SDK or geospatial visualization libraries only when the user opens the AWS‑CSM or CTS‑GIS tool.

### 6 Adopt asynchronous I/O and background tasks

* **Use asynchronous frameworks.** Consider moving runtime endpoints from Flask to an async framework like FastAPI or using Flask‑async. Async endpoints can fetch SQL results or call AWS services without blocking other requests.

* **Background jobs.** Offload heavy operations (such as computing AWS‑CTS metrics) to Celery or AWS Lambda invoked asynchronously, and provide progress indicators in the UI.

### 7 Improve testing and tooling

* **Refactor test factories.** Split large test helper modules into focused factories to reduce import time and memory usage during tests. Use caching or fixtures from pytest to avoid re‑creating expensive objects.

* **Introduce linters and static analysis.** Adopt tools like flake8, mypy and radon to enforce style, type hints and maintainable complexity. The Medium article describes using custom flake8 linters to communicate best practices[\[20\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Our%20tiny%20team%20worked%20hard,time%20to%20creep%20back%20up).

* **Monitor performance regressions.** Integrate import‑time profiling and bundle size checks into continuous integration to prevent performance regressions.

## Conclusion

The mycite‑core repository has grown into a complex monolith with duplicated logic, retained legacy code and large front‑end assets. To achieve a faster, maintainable and AWS‑CTS‑friendly platform, an aggressive reduction is necessary. Completing the one‑shell refactor, removing filesystem relics, modularizing code, lazy‑loading heavy dependencies and implementing caching and code‑splitting will significantly reduce load times and simplify future development. Using import‑time profiling tools and adhering to clear contracts during refactors will ensure that the portal remains performant as new features are added.

---

[\[1\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md#:~:text=,exceptions%20outside%20SQL%20datum%20authority) [\[2\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md#:~:text=) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/README.md)

[\[3\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=%23%23%20Non) [\[4\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=,load%20posture) [\[15\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md#:~:text=,load%20posture) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one\_shell\_portal\_refactor.md](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/plans/one_shell_portal_refactor.md)

[\[5\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,migration%2C%20parity%2C%20or%20fixture%20support) [\[16\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md#:~:text=,m%20unittest) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos\_program\_closure\_report\_2026-04-21.md](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/audits/reports/mos_program_closure_report_2026-04-21.md)

[\[6\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=from%20MyCiteV2,PORTAL_RUNTIME_ENVELOPE_SCHEMA%2C%20SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA%2C%20WORKBENCH_UI_TOOL_REQUEST_SCHEMA%2C%20build_tool_exposure_policy%2C) [\[11\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=def%20_load_optional_json_object%28path%3A%20Path%29%20,payload%2C%20dict%29%20else) [\[12\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py#:~:text=,%7D%2C%20%29%2C%20%7D%2C) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/\_shared/portal\_host/app.py](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/portal_host/app.py)

[\[7\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py#:~:text=from%20__future__%20import%20annotations) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/\_shared/runtime/portal\_shell\_runtime.py](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py)

[\[8\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=In%20order%20to%20understand%20what,we%20focused%20on%20Python%20imports) [\[9\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files) [\[14\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files) [\[17\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Move%20code%20out%20of%20init,files) [\[18\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Break%20down%20big%20files%20into,smaller) [\[19\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=What%3F) [\[20\]](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8#:~:text=Our%20tiny%20team%20worked%20hard,time%20to%20creep%20back%20up) How we improved our Python backend start-up time | by Emma Goldblum | Alan Product and Technical Blog | Medium

[https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8](https://medium.com/alan/how-we-improved-our-python-backend-start-up-time-2c33cd4873c8)

[\[10\]](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/contracts/portal_shell_contract.md#:~:text=) raw.githubusercontent.com

[https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/contracts/portal\_shell\_contract.md](https://raw.githubusercontent.com/Fruitful-Network-Development/mycite-core/main/docs/contracts/portal_shell_contract.md)

[\[13\]](https://web.dev/learn/performance/code-split-javascript#:~:text=Loading%20large%20JavaScript%20resources%20impacts,improve%20your%20page%27s%20%2048) Code-split JavaScript  |  web.dev

[https://web.dev/learn/performance/code-split-javascript](https://web.dev/learn/performance/code-split-javascript)