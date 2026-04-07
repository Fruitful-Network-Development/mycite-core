# Plan for continued development of Tools

> Tools should be packaged with all of their code in the live implementations under `mycite-state/instances/<portal>/private/utilities/tools/<tool>/code/`
> Tools should be kept seperate from their sandboxes for any datum files at `mycite-state/instances/<portal>/data/sandbox/<tool>/`
> Tool data can be kept in `repo/mycite-core/instances/deployed/<portal>/data/sandbox/<tool>/`, but no tool directory is kept per deployed instance, since that is spesific to the tool package that should be isolated in `repo/mycite-core/packages/tools/<tool>/`
* Tool code, either service or general, should only consist of using core portal functionailties.
* If tool use must go beyond this, only aceptiable for service tools, then it can use a singular service modulae that exists as a part of the portal core logic as a `peripheral` module.


- The main goal is to keep with a canotical portal core that maintains tool ports for tools to attach to for use of functionaility.

- Ideally, every tool functionality can be deffined for an existing module of the portal, where in the portal can maintain portas for the tools use of those capacities.

- The one exception is for service tools that may be used to acomplish current functioniality that goes byeond what has been accounted for my the portal.

- This only appllies for the FND portal, but not all tool employed in the FND portal.

- Some tools are daulted like the maps tool, and may offer the design basses for further developed tools later.

- Other base development largly invloves how tool operates with in their sandbox, rather than providing a datum/file workbench, tools ommit the 3rd panel to only have the left-side `control panel`, and the expanded right side `interface panel`. The Interface panel is meannt to provide a space for a more custome mediation viewing. Where as the same NIMM AITAS State machine logic acts as the backbone to the interfacing and use of the sandboxes contents, those are the operational methods in the brackground. Its only in the main portal sandbox, the `system sandbox`, that the workbench is provided for a true to form statemachine UI, where mediation is a tool on the rigth side interface panel for visualizing lenses.

- The only exeption to the ater portion above, is that lenses may be used to represent datums in a human reasable form. Made possible by the data engines recodnition of abstraction paths by consider the hyphae form of a datum.

- Form certain datums, the abstraction path is only needed for the patriach of a family datum, there after the data engine can use the abstraction rules to understand how that datum exists.

> {Using a nested `<datum>:<reference>;<magnitude>;<optinal 'with respect to'>` convention of denoting datums}:
> E.g. datum_a:(datum_b:(datum_c:(datum_d:0-0-6;magnitude_w);magnitude_x);0);magnitude_z

* In this example, note that `datum_d` is the patriarch, and its given its identify by `magnitude_w`.
* If `magnitude_w` is `8` we identify the octet family of abstractions, `256` is the ASCII family, etc.
* Now if for any datum `datum_c` that refferences a 'nominal-bacillete', then has a `magnitude_x` of `0`, this would deffect from any family and be considered a 'name-space' (might be called `nominal-bacillete-w`)
* The most important aspect of this is the size requirement that gets deffined for `magnitude_z`:

> E.g. For any `datum_a` that makes refference to `datum_b` (`datum_b:(datum_c:(datum_d:0-0-6;magnitude_256);magnitude_64);0`), this means that the `magnitude_z` must be the number of bits needed to represent 64 entries into a sequence of 64 values, where each value can be 1 through 256. Therefore, we expect a 512 sized bit string. If a word is smaller than this for its representation, its understoof to have empty trailling 0's, so so two words can be shown the same, but different in how they exist.
    - In this examplewe are just deffinning a 64 position sized array, where each entry of that array can be any of the ASCII values. 

* In this same logic but with different `lens` handling from the data engine, would the octet family:

> E.g. For any `datum_a` that makes refference to `datum_b` (`datum_b:(datum_c:(datum_d:0-0-6;magnitude_8);magnitude_255);0`), this means that the `magnitude_z` must be the number of bits needed to represent a domain name website address representation. Where each entry is still an octet of 8 bits, inturpretation of those octets would varry depending on whether they are DNS standardized encoded or email DNS with 320 octate and different convention.

* The Most important take away here is that even if a family or datum is unkown, general rules can always be made more narrow, so for datums that create arrays of sized entryies the minmum lense can be applied to at least have binary shown as into decimal values. Or even more importantly have those entries each be in their own cell with a bottom right water mark for the lense being applied (E.g. a tiny gray '8' for base 8 octets cells or base 10 for a local object id namespace). If the entire magnitude is understood as a particular datum abstraction then it can be a single cell with that lens as a bottom right watermark letter.
* Maybe even more important is that these lens functions are employed based on the canotical hyphae forms of datums. By creating the mss form, but only for the necisarry datums needed in one particular datums abstraction path, then you create a canotical form that is not impacted by how it might be ordered in a given sandbox. This is why its easier to only keep track of families and rules when possible. However, this is meant to outline that the base workbench provided must operate with out any lenses, looking more similar to excel with colapable grouppings of layers grouped rows or valuegroup-groupped rows. This way when lenses are added, they only need to overlay a collection of cells, and the data backed form can always be viewed in needed.

## Maps
* Maps is a default tool that is meant to have a primary mediation on the SAMRAS structure. 
* It loads layers of the SAMRAS strucure by investigating the 'structure facet' of the datum for an attention value of 4, where it is focussing on a facet of a datum, not even perse the datum itself. This allows for the context of achetype to set the context for the current datum being a SAMRAS strucure, there in navigation is made by exploring the space deffined by the strucure.
* Now as the navigation goes from 0 to 3 to 2 to 3, it is narrowing the the node it is mediating on
    - This mediation is done with respect to the coresponding resource profile of that administrative entity.
    - Since their is currently only `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json` as the highest level node profile, then the tool should default a starting view of the msn SAMRAS node of `3-2-3-17-77`. 
> conceptual NIMM-AITAS denotation as <directive>[{attention}{Intention}{tme}{archetype}{space}]:<msn_SAMRAS_datum_address>:<with_respect_to_subject_with_in_facet>
> <mediate>[{facet}{mediate}{null}{SAMRAS}{4}]:1-1-2;3-2-3-17-77

* This would then enable a tool mediation view of the nodes profile by visualizing the geocoordinates via the geo coordinate HOPS address lense. In this case the 'cell' provided is the adminitrative profile:
    - with its node address path, correlating the direct parents nodes
    - Child nodes for further navigation
    - name
    - adminstrative entity governing body. (for `3-2-3-17-77` this would be `3-2-3-17-77-1-1-1-1-1`)
* The most important part of developing this tool is the avility to focus on mutltiple layers at once by pulling in the respetive child nodes or other facets to see what will initiatlly be summit county ohio and all the communities with in that county.
* This conceptual aproach but precise outcome it open to creative materialization given the the design provided by the data state machine to make this a use of the portals core logic.

---


## AWS-CMS ~ 

### News Letter Considerations:

There are three separate issues.

The same SMTP username/password for both technical-contact users is expected under the implementation your agent described. It is explicitly using one shared IAM principal, `aws-cms-smtp`, and “create or reuse a real IAM access key on `aws-cms-smtp`,” then deriving the SES SMTP password and writing that into Secrets Manager for the mailbox profiles . So this is not a Secrets Manager bug. It means the current model is “one shared SMTP credential source, many mailbox profiles.” If you want per-mailbox or per-domain credentials later, that is a design change.

The Gmail “unverified” labels are a real mismatch, and the portal is the part that is wrong. Your agent’s own output says the remaining manual boundary after provisioning is still Gmail send-as initiation and verification, and that provisioning only moves the mailbox to `ready_for_gmail_handoff` . So if AWS-CMS is currently showing the two technical contacts as “Gmail verified,” that is a state-model bug. The portal should show them as SMTP-ready / Gmail-pending until the actual Gmail verification completes.

The daily `dcmontgomery` emails are a separate legacy-mail issue. The message you attached is a forwarded DMARC report, sent through SES, with `From: forwarder@fruitfulnetworkdevelopment.com`, a `Return-Path` on `dcmontgomery.fruitfulnetworkdevelopment.com`, and subject `[FWD] Report domain: fruitfulnetworkdevelopment.com...` . So deleting the old Gmail send-as entry for `dcmontgomery@fruitfulnetworkdevelopment.com` will not stop those daily messages. They are being generated by the legacy SES/forwarder/DMARC reporting path.

So the clean reading is:

* shared SMTP creds: current design behavior
* Gmail “unverified” vs portal “verified”: bug in AWS-CMS state logic
* daily `dcmontgomery` messages: legacy inbound/DMARC-forwarding issue

What your agent should do next is:

1. Fix AWS-CMS status semantics so `stage_smtp_credentials` and `prepare_send_as` never mark a mailbox as Gmail-verified. They should only mark:

   * secret provisioned / SMTP ready
   * ready for Gmail handoff
   * Gmail pending
     and only flip to verified after actual confirmation evidence.

2. Leave the shared `aws-cms-smtp` model alone unless you explicitly want a redesign to per-mailbox credentials.

3. Do a separate legacy mail cleanup pass for `dcmontgomery`, focused on:

   * identifying the DMARC report destination and forward path,
   * removing or rerouting that report flow,
   * then retiring the old `dcmontgomery` mail artifacts.

The important caution is that the `dcmontgomery` cleanup should not be mixed into the Gmail-verification status fix. They are related historically, but operationally they are different problems.

If you want, I can turn this into a precise agent prompt for:

* “fix Gmail verification state reporting,”
  and a second one for:
* “retire legacy `dcmontgomery` DMARC/forwarder mail flow.”

---


## FND-WDM
> Website Development Managment

### Designing a Site‑Editor Tool for the Portal

Here's the design document I prepared that explains how to integrate image changes, content editing and section inclusion/exclusion into the existing portal using the current manifest structure. You can download and read it:

* How the existing JSON manifest defines pages, sections, images and navigation with stable IDs.
* A proposal for adding `enabled` flags and editor metadata to make fields editable.
* Guidelines for building a three-pane site editor tool in the portal, with hover-based selection, an inspector panel and a publish workflow.
* Suggestions for API endpoints and backend handling of draft, preview and publish states.
* Recommended refinements to the manifest to support toggling and consistent structures.

#### Context and goals
The webDZ client sites use a JSON manifest as their single source of truth for navigation, page structure, content, images and icons. The render_manifest.py script loads this manifest and calls site_builder.build_site to produce static HTML pages. For example, the Trapp Family Farm manifest defines the site shell (wordmark lines, menu label and assets such as favicon and header/footer graphics), navigation items (each with an id, label, href and icon), and pages such as the home_featured landing page and the crops, animals and info pages. Each page has a template, a title and description, and contains content fields (e.g., lead, sidebar_cards on the home page) or a list of sections with rich data like quotes, headings, body paragraphs, lists of images and so on[1][2]. Individual sections and cards have stable id fields (vegetables, ready‑to‑lay‑hens, etc.) and arrays of blocks such as lists of items, rich cards, or subsections[3][4].
The portal already includes a Data Tool for editing structured data. It uses a three‑pane workbench layout and modal overlays; the client‑side logic lives in data_tool.js and the HTML structure comes from data_tool_shell.html. The user would like to edit images, wording and inclusion/exclusion of sections directly within the portal. Rather than building a separate CMS, we can build a site‑editor tool that edits the same manifest and reuses the existing render pipeline and publish controls.
#### Manifest‑driven editing
    1. Use the manifest as the canonical schema. Fields already map cleanly to UI components:
    2. Page structure – Each page defines its template (e.g., home_featured, section_stack), order of sections, and page‑level metadata (title, description, body class). Section arrays include stable id values such as intro, vegetables, layers, etc., which uniquely identify each editable block[3][5].
    3. Editable content – Each block exposes headings, kicker text, quotes and lists of paragraphs in arrays (e.g., lead.body is an array of strings for the home page[2]). Cards and lists have heading, items and summary fields[4].
    4. Media references – Images are defined by src and alt fields, and icons are stored under the icons section; both are relative paths into the site assets[1][4].
    5. Visibility – At present the manifest lacks explicit booleans for toggling sections, so adding enabled: true/false flags to optional sections or cards makes inclusion/exclusion first‑class instead of deletion. Similarly, adding optional variant properties allows style changes without structural edits.
    6. Editor metadata – To simplify mapping between the DOM and manifest, add optional editor metadata to each editable node specifying a human‑readable label, a type (text, rich_text, image, icon, link, boolean, collection_ref), and optional visible_if expressions. These hints avoid brittle DOM‑to‑JSON inference.
    7. Stable path addressing. Each UI selection should resolve to a manifest path such as pages.home.content.lead.heading or pages.crops.sections[2].images[0].src. Using stable id values for sections and cards makes these paths predictable. For arrays, include an id property on each object so that reordering does not break the path mapping.
    8. Draft–preview–publish states. Editing should never directly modify the live manifest. Instead:
    9. When the user edits a field, the tool writes changes into a draft manifest stored in portal state (e.g., state/<portal>/data/site_editor/projects/<site‑id>/draft/manifest.json). A PATCH /portal/tools/site_builder/draft endpoint can accept updates to arbitrary manifest paths.
    10. Clicking Render Preview runs the existing render_manifest.py on the draft and writes output to a staging directory, then displays the result in an iframe. This corresponds to the build_site call in render_manifest.py.
    11. Clicking Publish promotes the draft manifest and any staged assets into the repository’s live assets/docs/manifest.json, triggers a re‑render of the live site and writes a publish log. This pattern parallels the Data Tool’s staging and commit process.
#### Tool UI within the portal
**Shell integration**
Reuse the portal’s workbench layout by registering a new tool (e.g., site_builder) alongside data_tool. The tool’s UI can follow the same three‑pane pattern:
    1. Preview pane. An iframe shows the rendered draft site. During rendering, augment the HTML templates to output data‑editor‑node and data‑editor‑field attributes for each manifest field. For example, when rendering a home page heading, add data-editor-node="pages.home.content.lead" data-editor-field="heading" data-editor-type="text" to the <h1> element. For images and icons, include similar attributes with type="image" or type="icon". This instrumentation lets the tool detect the hovered element and map it back to the manifest path.
    2. Inspector/control pane. When a user hovers over an element in the preview, highlight it and display a breadcrumb trail (Home / Lead / Heading) along with editable fields. Each field uses a control matching the metadata type: a text input for plain text, a rich‑text editor for arrays of paragraphs, a toggle switch for booleans (enabled flags), a file chooser linked to an asset browser for images and icons, and a link picker for href fields. For lists of items or sections, show an array editor that allows reordering (drag‑and‑drop), adding new entries, or toggling their enabled flags.
    3. Publish/status pane. At the bottom or in a dedicated panel, show the current draft status (modified/unmodified), the last preview render time, and a history of previous publishes. Provide buttons for Render Preview and Publish with confirmation dialogs. This pane can also expose an asset browser for uploading new images; images are stored in a staging area (e.g., state/.../assets/) and only copied into the site’s asset folder on publish.
**Interaction verbs**
Define high‑level actions mirroring the Data Tool’s verbs:
Verb
Action
Select
Hover and click within the preview to select a manifest node; highlight the area and show its controls.
Edit
Edit text fields, alt tags, link labels and URLs directly in the inspector pane.
Media
Choose or upload an image or icon; update the manifest’s src or icon path accordingly.
Publish
Validate the draft, run the renderer, and promote the draft manifest and assets to live.
**Handling images and icons**
Images and icons live in the site’s assets folder and are referenced in the manifest by relative paths (e.g., /assets/images/Home_front_door_address.avif or /assets/icon/ui/icon-data.svg)[1]. The Media tab should:
    1. Display the current asset preview and alt text.
    2. Provide an asset browser that lists available images and icons, grouped by type (image, icon) with metadata (filename, dimensions, tags).
    3. Allow uploading new assets into the draft staging directory; on publish, copy them into the site’s assets directory and update the manifest paths.
    4. Update only the src or icon path in the manifest; alt text remains editable separately. Icons can reuse the same search‑and‑choose interface already used in the existing Data Tool for datum icons.
**Section inclusion/exclusion and variant selection**
Optional sections or cards should not be removed from the manifest but toggled via an enabled boolean. For example, adding "enabled": false to the newsletter card in the home page’s sidebar lets the editor hide or show that card without deleting its content. A drop‑down for a variant field can switch between style variants (e.g., featured, compact). The inspector pane should therefore render toggle switches and variant selectors for each section or card.
#### Backend API endpoints
Implement a small set of endpoints (similar to existing tool APIs) to support the editor:
    • GET /portal/tools/site_builder/session/:site – returns the current draft manifest, schema information (e.g., allowed section templates), asset index and preview URL.
    • PATCH /portal/tools/site_builder/draft – applies a JSON Patch or a list of path/value updates to the draft manifest.
    • POST /portal/tools/site_builder/upload – handles asset uploads into the draft staging directory.
    • POST /portal/tools/site_builder/render – runs the render pipeline (calls the existing render_manifest.py) and returns the URL of the preview output for the iframe.
    • POST /portal/tools/site_builder/publish – promotes the draft manifest and assets to live, re‑runs rendering and records a publish log.
    • GET /portal/tools/site_builder/history – optional endpoint to list previous publishes for rollback or audit.
These endpoints can be thin wrappers around your existing tool_state_api for state storage and the build scripts in render_manifest.py and site_builder.py.
#### Recommended manifest refinements
Before implementing the UI, refine the manifest slightly:
    1. Stable IDs everywhere – Ensure every editable section, card and list item includes an id property. The Trapp Family Farm manifest already does this for sections like vegetables, ready‑to‑lay‑hens and cards like cle-foodcast[3][4]; apply the same pattern uniformly across all pages and blocks.
    2. Enabled flags – Add an enabled boolean to each optional section or card; default true. This allows the editor to toggle inclusion/exclusion without structural changes.
    3. Editor metadata – Add an optional editor object per field or block with a label, type and optional group and visible_if conditions. These hints drive the inspector UI and help non‑technical editors understand each field.
    4. Normalize repeated structures – Use consistent shapes for lists of cards or subsections, e.g., rich_cards always have an id, title, optional subtitle and summary, and an image with src and alt. Consistency makes the editor easier to generate.
#### Getting started
A minimal first version of the site editor should:
    1. Render the draft manifest into a preview iframe with data‑editor attributes for all editable fields.
    2. Allow hovering and selecting sections, headings and images in the preview and editing their text, alt text and media in the inspector panel.
    3. Provide toggles to hide/show sections via the new enabled flags.
    4. Support uploading or selecting images and icons, updating only the manifest path.
    5. Implement Render Preview and Publish buttons to stage and commit changes, using the existing render pipeline.
Once this is working, add more advanced features like section reordering, adding/removing cards, editing collection‑driven pages (e.g., newsletter items), and variant selection. Throughout, rely on the manifest as the single source of truth and keep all changes in the portal’s state until published.

[1] [2] [3] [4] [5] manifest.json
https://github.com/Fruitful-Network-Development/webDZ/blob/6ab3cf8164a00f2d4ad9a8fd8c3c0de051d16615/clients/trappfamilyfarm.com/frontend/assets/docs/manifest.json


---


## Datum handling Discussion

### Prompt:
Notices the chnages that I have made in the repo and the live instances, focus on the FND instance.


I have also updated the HOPS addressing system use in the new convention.


Much of this has to do with a comprehensive audit to make sure that code and logic are algined to the carfully created dataum files.



Consider that this is meant to also further modularize tools, for their use of sandboxes, while leaving portal configuration of tools up to the config.json, and tool configations that are not datums statying under utilities.

After you audit, fix any faults, errors, drifts, but don't chnage the datum files I have created, the resources. Any human errors in my creation of these should simply result in the code produce errors messages. The one exceptions is the generation of the payload binaries based on the cache files.



Consider the further notes below for your comprehensive audit and correction, then finally address the issue outlined in the file at [news_letter_workflow_correction.md](repo/mycite-core/docs/plans/news_letter_workflow_correction.md)
 
I have organized the tools to reflect what the convention should be.
Expecially note that tools may use none datum JSON files, and those are kepts in the tools' respective directory under `uitility/`, but datum files exist in the tools respective sandbox.
All code, logic, and documentation must me made to reflect this.
Also consider and correct for any logic or documentation that contradicts the format or organization represented in the fnd data directory.
Additionally, note that the files that are made avaible for access by the contact card, those are payload JSON that carry hyphae datum that is identified as the target datum to contrct the hyphae form from, using its minimum abstractions to create that datum.
All binary forms are kepts, and called from the same place, their in `data/payloads/`, even those that are updated or orginated from outside the portal, the convention of where it is kept and acessed, as well as it form, are the same.
If portal logic or a tool wants to refference one of these, it can double check that the cache verion is up to date if it is managed by a contract.
The only default resource is registrar for locating portals by either DNS, IP-v4, IP-v6 or how ever it should end up looking like.
Default tools include the maps while exception datum files that arn't resources but help divide up contents would `system_log.json` for use of calendar viewing. But this calendar viewing would be a mediation of that file and not a differnt tool sandbox.

The system sandbox or a tool sandbox may use a source by making a copy of the cached, decoded, file, but it is then inegrated into that sandbox as a source, so this only carries over necisary datum that are not deffined in the anchor datum file of that sandbox (the anthology is the anchor datum of the system sandbox.)
Some of these hyphae may need to be reloaded to match the datum content of the cache files, which would not usally be the workflow.
If a file is created locally and then exported from the sandbox as a hyphae payload binary file, then it would exists there, then if a sandbox wanted to use that file, it would innitiate the decoded cache form and then initiate adding it to the sandboxes own sources.

This requires that use of migrating a datum to a sanbox, which entails adjusting its refferenced datums for its abractions and even possibly adjusting its datum addreses, since leaving out datums that are deffined in the anchor datum file may chnage the order of instances.
Notice that refference-magnitude tuples have refference values of `rf.<datum_address>`, that corealates to the datum in the anchor datum file.

### Plan

# FND Convention + Newsletter Workflow Realignment

## Summary
- The repo mirror at `instances/deployed/fnd` and the live FND instance are aligned, so the repair should target shared code, tests, and docs rather than a one-off live-state patch.
- The main drift clusters are: utility tool collections being treated as datum anchors, AGRO/HOPS docs and loaders still sourcing anchor truth from utility paths, stale reference/resource boundary contracts around `rf`/payload handling, and newsletter existing both as a standalone `newsletter-admin` tool and as AWS/progeny newsletter metadata with conflicting live values.
- Current audit signal: HOPS/runtime/newsletter route tests are green under `python3 -m unittest`, but config-loader reference normalization is failing and resource-registry boundary tests are failing or blocked by legacy `portals` imports.

## Implementation Changes
- Re-establish the authority chain so `private/config.json` only controls tool exposure and mount status, `private/utilities/tools/<tool>/` only holds non-datum tool specs/profile collections, `data/sandbox/<tool>/` is the only tool-datum authority, and `data/payloads/` plus `data/payloads/cache/` remain the only binary/decoded payload locations.
- Update shared tool mediation to stop describing `tools_configuration[].anchor` as a sandbox datum anchor; treat it as a utility collection/config file selector only, and convert the remaining legacy utility manifests (`aws-csm`, `fnd-ebi`, `keycloak-sso`, and similar) to the plain `tool_collection`/`member_files` contract instead of compact datum-shaped JSON.
- Move AGRO time/HOPS schema resolution off utility anchors and onto the actual sandbox datum anchor in `data/sandbox/agro-erp/`; keep the current mixed-radix decoder intact because the decoder/tests are already passing.
- Keep canonical reference naming as `rf.<source_msn_id>.<name>` with canonical MSS form `rf.<source_msn_id>.<name>.bin`; accept legacy `refferences` and legacy `ref.*.json` only at compatibility boundaries, normalize them to the canonical `rf` form, and emit explicit warnings/errors for malformed entries instead of silently redefining authority.
- Bring resource-registry behavior back in line with the stricter boundary model: canonical local/inherited files stay in their scoped layouts, legacy root files are surfaced as read-only compatibility entries with migration guidance, explicit migration actually moves them, and only payload-bin/cache materialization is allowed to rewrite derived artifacts.
- Remove newsletter as a standalone tool surface from the service catalog, tool tabs, utilities status UI, and dedicated tool mediation while keeping the existing newsletter profile JSON files under `private/utilities/tools/newsletter-admin/` as the canonical newsletter-profile store for now.
- Fold newsletter mediation into AWS-CSM domain cards. The AWS-CSM surface becomes the only admin UI for newsletter profiles, selected verified sender choice, dispatch history, and contact-log health.
- Make the newsletter profile JSON the canonical operational source for `list_address`, selected author/sender, queue/Lambda config, and dispatch behavior. Treat progeny `email_policy.newsletter` and `profile_refs.newsletter_*` as compatibility-read inputs only; when they disagree with the canonical profile, show a warning and do not auto-rewrite the conflicting human-authored file.
- Replace portal manual newsletter composition/dispatch with inbound-only triggering: a message sent from the selected verified mailbox to `news@<domain>` is the only send trigger, and the portal mediation becomes config/status only.
- Generalize the existing AWS inbound-capture helpers so the live inbound path for `news@<domain>` can resolve the captured message, validate the sender against the selected verified AWS-CSM profile, extract subject/body, read the canonical website contact log, enqueue one SQS message per subscribed recipient, and record success/failure back into the same contact log.
- Keep public subscribe, unsubscribe, and dispatch-result flows, but change admin newsletter send endpoints to return an explicit “inbound-mail workflow only” error so the runtime no longer presents two competing control planes.
- Refresh the runtime-build/tooling/newsletter docs so they match the FND directory truth, the new HOPS/tool-sandbox authority model, and the inbound-only newsletter workflow.

## Test Plan
- Update and run targeted `unittest` suites for config normalization, service-tool mediation, newsletter workflow, AGRO anchor resolution, HOPS/coordinate decoding, and resource-registry boundaries.
- Add tests proving utility collection manifests can be plain JSON while sandbox datums remain authoritative, AGRO reads its schema from the sandbox anchor, and malformed reference/resource inputs fail with explicit diagnostics rather than silent mutation.
- Add AWS-CSM newsletter tests proving canonical newsletter profile JSON wins over conflicting progeny newsletter fields, the selected verified sender must match the inbound author, inbound mail to `news@<domain>` produces queued dispatch rows, and unsubscribed contacts are skipped.
- Stabilize the resource tests that still import `portals...` so they run against the current package layout during the audit suite.

## Assumptions
- Newsletter mediation should live inside AWS-CSM domain cards.
- Newsletter sending should be triggered by inbound mail to `news@<domain>` only, with no manual admin send path in steady state.
- Canonical newsletter operational config remains in the existing newsletter profile JSON files for now; no datum/resource files are edited except derived payload-bin/cache regeneration.
- The current live FND drift between newsletter profiles and progeny newsletter metadata should be handled by canonical precedence plus visible diagnostics, not silent rewrites.


---


### Output

Implemented the FND realignment across shared code, the FND runtime, the live FND utility collections, tests, and docs.

The main contract fixes are in [config_loader.py](/srv/repo/mycite-core/instances/_shared/portal/core_services/config_loader.py), [resource_registry.py](/srv/repo/mycite-core/instances/_shared/portal/data_engine/resource_registry.py), and [__init__.py](/srv/repo/mycite-core/instances/_shared/runtime/flavors/tff/portal/tools/agro_erp/__init__.py). `private/config.json` now behaves as tool exposure plus utility-collection selection only, legacy `refferences` and `ref.*.json` normalize to canonical `rf.<source>.<name>.bin`, resource indexes use scoped layouts with read-only legacy-root compatibility, and AGRO time-schema authority now resolves from `data/sandbox/agro-erp/` instead of utility files. I also added a small legacy import shim at [portals/__init__.py](/srv/repo/mycite-core/portals/__init__.py) so the older `portals._shared...` tests keep working.

The newsletter workflow is now folded into AWS-CMS instead of a standalone tool. The service/runtime changes are in [service_catalog.py](/srv/repo/mycite-core/packages/tools/_shared/tool_contracts/service_catalog.py), [runtime.py](/srv/repo/mycite-core/packages/tools/_shared/tool_state_api/runtime.py), [service_tools.py](/srv/repo/mycite-core/instances/_shared/portal/application/service_tools.py), [state_adapter.py](/srv/repo/mycite-core/packages/tools/newsletter_admin/state_adapter.py), [newsletter_admin.py](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/portal/api/newsletter_admin.py), and [system_shell_runtime.js](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/portal/ui/static/shared/system_shell_runtime.js). The old `newsletter-admin` tool surface is suppressed, AWS-CMS now mediates canonical newsletter profile JSON plus contact-log health, progeny newsletter fields are compatibility-read only with visible drift warnings, manual admin send now returns an explicit inbound-only error, and the new processing path consumes captured inbound mail to `news@<domain>`, validates the selected verified sender, queues one SQS job per subscribed recipient, and records dispatch state back into the canonical website contact log. I also converted the FND utility manifests to plain `tool_collection.v1` JSON in both repo and live state, including [tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json](/srv/repo/mycite-core/instances/deployed/fnd/private/utilities/tools/aws-csm/tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json).

The documentation now matches the corrected layout and workflow, including [portal-config-model.md](/srv/repo/mycite-core/docs/wiki/runtime-build/portal-config-model.md), [time-address-schema.md](/srv/repo/mycite-core/docs/wiki/tools/time-address-schema.md), [agro-erp-datum-decision-ledger.md](/srv/repo/mycite-core/docs/wiki/tools/agro-erp-datum-decision-ledger.md), [tool_development_guide.md](/srv/repo/mycite-core/docs/modularity/tool_development_guide.md), and [news_letter_workflow_correction.md](/srv/repo/mycite-core/docs/plans/news_letter_workflow_correction.md).

Verification: `python3 -m unittest tests.test_config_loader_contract tests.test_tool_runtime tests.test_service_tool_mediation tests.test_newsletter_service_tool_mediation tests.test_newsletter_admin_api tests.test_coordinate_hops tests.test_runtime_paths tests.test_shell_tool_runtime_contracts tests.test_resource_registry_boundaries tests.test_external_resource_catalog tests.test_external_resource_identity_and_planner tests.test_agro_erp_tool_flow tests.test_time_address_schema tests.test_fnd_portal_shell_routes` from `/srv/repo/mycite-core` passed with `73` tests OK and `16` skipped.



---



# Review/Alignment Accessment

Reviewed against [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), the live FND/TFF instances, the running services, and `/srv/compose`. The plan’s direction is strong, but the current system still has multiple competing operational authorities.

**Findings**
- Critical: live tool utility state is not fully represented in the repo deployment mirrors. The only live-vs-repo delta for both instances is `private/utilities/tools`, which means tool collections can exist in live state outside the tracked deployed mirror. See [fnd live state](/srv/mycite-state/instances/fnd/private/utilities/tools) and [fnd deployed mirror](/srv/repo/mycite-core/instances/deployed/fnd).
- Critical: process supervision is split. `tff` is cleanly supervised, but `fnd` is still serving on port `5101` while `fnd-portal.service` is inactive, and [`paypal-proxy.service`](/srv/repo/srv-infra/systemd/paypal-proxy.service) is restart-looping because it points at the old non-existent `tools/paypal_csm/backend` path.
- High: newsletter is only half-migrated. [`tool_state_api runtime.py`](/srv/repo/mycite-core/packages/tools/_shared/tool_state_api/runtime.py) suppresses `newsletter_admin` as a standalone tool, but [`fnd config.json`](/srv/mycite-state/instances/fnd/private/config.json) still declares `newsletter-admin`, [`fnd app.py`](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/app.py) still registers newsletter routes, and [`newsletter_admin state_adapter.py`](/srv/repo/mycite-core/packages/tools/newsletter_admin/state_adapter.py) still uses hidden secret dotfiles in [newsletter-admin live root](/srv/mycite-state/instances/fnd/private/utilities/tools/newsletter-admin). That directly conflicts with your goal of eliminating hidden operational state.
- High: datum authority is still semantically blurry. [`service_tools.py`](/srv/repo/mycite-core/instances/_shared/portal/application/service_tools.py) correctly treats config anchors as utility collection selectors, and the AGRO runtime in [`agro_erp`](/srv/repo/mycite-core/instances/_shared/runtime/flavors/tff/portal/tools/agro_erp/__init__.py) reads from `data/sandbox/agro-erp`; but [`time_address_schema.py`](/srv/repo/mycite-core/instances/_shared/portal/application/time_address_schema.py) still resolves tool anchors under `private/utilities/tools`, and [`view_model.py`](/srv/repo/mycite-core/mycite_core/state_machine/view_model.py) exposes that utility root as `sandbox_root`. The codebase is still teaching two different meanings for “sandbox.”
- High: docs and tests still describe the old `portals/...` and `/srv/compose/portals/state/...` world. See [`README.md`](/srv/repo/mycite-core/README.md), [`portal-config-model.md`](/srv/repo/mycite-core/docs/wiki/runtime-build/portal-config-model.md), and [`time-address-schema.md`](/srv/repo/mycite-core/docs/wiki/tools/time-address-schema.md). Several portal and AGRO tests fail for stale-path reasons, which means part of the safety net is validating a layout that no longer exists.
- Medium-high: the data engine still keeps too many legal homes for reference and binary material. [`resource_registry.py`](/srv/repo/mycite-core/instances/_shared/portal/data_engine/resource_registry.py) supports `data/resources`, `data/references`, and compatibility fallbacks in addition to `data/payloads` and `data/payloads/cache`. That preserves backward compatibility, but it also preserves the exact kind of hidden placement surface you want to remove.
- Medium: there is still state-like content inside the code tree. [paypal-csm runtime data](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/private/utilities/tools/paypal-csm) contains NDJSON records under a runtime flavor path, which mixes code and mutable records in one place.
- Medium: the repo already has the right primitives for your datum-centered direction. [`datum_identity.py`](/srv/repo/mycite-core/instances/_shared/portal/data_engine/datum_identity.py), [`config_loader.py`](/srv/repo/mycite-core/instances/_shared/portal/core_services/config_loader.py), and [`bacillete_rules.py`](/srv/repo/mycite-core/instances/_shared/portal/data_engine/rules/bacillete_rules.py) give you canonical identity, legacy-reference normalization, and structure-aware validation. The missing piece is stricter authority enforcement, not a brand-new core model.

**Alignment**
- The clean contract implied by [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md) is the right one: `private/config.json` should only declare enabled tool collections, `private/utilities/tools/<tool>/` should only hold non-datum specs/profiles, `data/sandbox/<tool>/` should be the only tool datum authority, and `data/payloads/` should be the only binary/payload/cache authority.
- Inference from the current code: the maps-default-tool, hyphae, and contract alignment work should be treated as a boundary-enforcement problem first. If those flows keep resolving through utility manifests, legacy references, or ad hoc binary surfaces, datum-family logic will stay fragmented no matter how good the schema rules are.
- The portal shell should be stricter than it is now. It should only expose state-machine-declared surfaces plus narrow extension points for datum/tool visualizers. Right now the shell and view model still know too much about legacy storage layout, which weakens the interface boundary you want.
- I did not do a semantic-by-semantic sweep of every datum file in every sandbox, so I would not recommend an encoding-policy change yet. Structural enforcement should come first; dynamic “illegal datum” alerts should be layered on after the authority model is singular.

**`/srv/compose`**
- Safe delete candidates now: [/srv/compose/portals/docker-compose.yml.bak.20260401T000618Z](/srv/compose/portals/docker-compose.yml.bak.20260401T000618Z), [/srv/compose/portals/fnd_portal-state-backup-20260331-231553.tgz](/srv/compose/portals/fnd_portal-state-backup-20260331-231553.tgz), and [/srv/compose/portals/tff_portal-state-backup-20260331-231553.tgz](/srv/compose/portals/tff_portal-state-backup-20260331-231553.tgz).
- Likely deletable after confirming no active dependency: [/srv/compose/portals/host_control_api](/srv/compose/portals/host_control_api), because the active control API appears to be sourced from [/srv/repo/srv-infra/compose/portals/host_control_api](/srv/repo/srv-infra/compose/portals/host_control_api).
- Hold off on deleting the rest of [/srv/compose/portals](/srv/compose/portals) until `paypal-proxy` is re-homed and the last old-path references are removed. I did not find obvious deletion candidates under [/srv/compose/platform](/srv/compose/platform); that stack is active.

**Verification**
- I ran the core contract suites around tool runtime, config loading, resource registry, time-address schema, datum rules, newsletter, AGRO, and the portal shell.
- The meaningful failures were stale-path failures tied to the removed `portals/...` layout, plus one newsletter behavior mismatch where inbound processing lowercases `author_address`. No files were changed.