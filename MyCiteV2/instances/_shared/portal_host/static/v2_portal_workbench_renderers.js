/**
 * Tool-specific workbench renderers for the V2 portal shell.
 * These stay behind the server-issued `kind` registry so the browser remains
 * a renderer/dispatcher rather than a second shell model.
 */
(function () {
  var renderers = window.PortalShellWorkbenchRenderers || (window.PortalShellWorkbenchRenderers = {});

  function guidanceSectionHtml(escapeHtml, summary, title) {
    var items = (summary && summary.items) || [];
    var recommended = (summary && summary.recommended_action) || "";
    if (!items.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>' +
      escapeHtml(title || "Guidance") +
      "</h3>" +
      (recommended
        ? '<p class="ide-controlpanel__empty">Recommended action: <code>' + escapeHtml(recommended) + "</code></p>"
        : "") +
      "<dl class=\"v2-surface-dl\">" +
      items
        .map(function (item) {
          return (
            "<dt>" +
            escapeHtml(item.label || item.id || "item") +
            "</dt><dd><strong>" +
            escapeHtml((item.status || "unknown").replace(/_/g, " ")) +
            "</strong><br />" +
            escapeHtml(item.detail || "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl></section>"
    );
  }

  var ctsGisHelpers = window.PortalShellCtsGisHelpers || (window.PortalShellCtsGisHelpers = {});

  ctsGisHelpers.buildRequestBody = function (args, patch) {
    var requestContract = (args && args.requestContract) || {};
    var fixed = requestContract.fixed_request_fields || {};
    var selectedDocument = (args && args.selectedDocument) || {};
    var mediationState = (args && args.mediationState) || {};
    var selectionSummary = (args && args.selectionSummary) || {};
    var selectedRow = (args && args.selectedRow) || {};
    var selectedFeature = (args && args.selectedFeature) || {};
    var lensState = (args && args.lensState) || {};
    var baseMediationState = {
      attention_document_id: mediationState.attention_document_id || selectedDocument.document_id || "",
      attention_node_id: mediationState.attention_node_id || "",
      intention_token: mediationState.intention_token || "0",
    };
    var bodyOut = {
      schema: requestContract.request_schema || "mycite.v2.admin.cts_gis.read_only.request.v1",
      selected_document_id: selectedDocument.document_id || "",
      selected_row_address: selectionSummary.selected_row_address || selectedRow.datum_address || "",
      selected_feature_id: selectionSummary.selected_feature_id || selectedFeature.feature_id || "",
      overlay_mode: lensState.overlay_mode || "auto",
      raw_underlay_visible: !!lensState.raw_underlay_visible,
      mediation_state: baseMediationState,
    };
    Object.keys(fixed || {}).forEach(function (key) {
      bodyOut[key] = fixed[key];
    });
    Object.keys(patch || {}).forEach(function (key) {
      if (key === "mediation_state" || key === "clear_selection") return;
      bodyOut[key] = patch[key];
    });
    if (patch && patch.mediation_state) {
      Object.keys(patch.mediation_state || {}).forEach(function (key) {
        bodyOut.mediation_state[key] = patch.mediation_state[key];
      });
    }
    if (patch && patch.clear_selection) {
      bodyOut.selected_row_address = "";
      bodyOut.selected_feature_id = "";
    }
    return bodyOut;
  };

  ctsGisHelpers.profileButtonHtml = function (args) {
    var profile = (args && args.profile) || {};
    var escapeHtml = args.escapeHtml;
    var attrName = args.attrName || "data-cts-gis-node-id";
    var isActive = !!args.isActive;
    var label = profile.profile_label || profile.node_id || "profile";
    var meta = profile.feature_count != null ? " (" + String(profile.feature_count) + ")" : "";
    return (
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" ' +
      attrName +
      '="' +
      escapeHtml(profile.node_id || "") +
      '" style="border-radius:6px' +
      (isActive ? ";font-weight:700" : "") +
      '">' +
      escapeHtml(label) +
      meta +
      "</button>"
    );
  };

  ctsGisHelpers.overlayCellHtml = function (args) {
    var row = (args && args.row) || {};
    var escapeHtml = args.escapeHtml;
    var lensState = (args && args.lensState) || {};
    var overlays = row.overlay_preview || [];
    if (!overlays.length) {
      return "<code>" + escapeHtml(row.primary_value_token || "—") + "</code>";
    }
    return overlays
      .map(function (overlay) {
        var display = overlay.display_value || overlay.raw_value || "—";
        var raw = overlay.raw_value || "";
        var title = overlay.anchor_label || overlay.overlay_family || "value";
        var rawHtml =
          lensState.raw_underlay_visible && raw
            ? '<div><small>raw: <code>' + escapeHtml(raw) + "</code></small></div>"
            : "";
        return (
          '<div style="margin-bottom:6px"><strong>' +
          escapeHtml(String(title).replace(/_/g, " ")) +
          ":</strong> " +
          escapeHtml(display) +
          rawHtml +
          "</div>"
        );
      })
      .join("");
  };

  ctsGisHelpers.bindInteractions = function (args) {
    var body = args.body;
    var loadRuntimeView = args.loadRuntimeView;
    var requestContract = args.requestContract || {};
    var selectedDocument = args.selectedDocument || {};
    var mediationState = args.mediationState || {};
    var selectionSummary = args.selectionSummary || {};
    var selectedRow = args.selectedRow || {};
    var selectedFeature = args.selectedFeature || {};
    var lensState = args.lensState || {};

    function requestBody(patch) {
      return ctsGisHelpers.buildRequestBody(
        {
          requestContract: requestContract,
          selectedDocument: selectedDocument,
          mediationState: mediationState,
          selectionSummary: selectionSummary,
          selectedRow: selectedRow,
          selectedFeature: selectedFeature,
          lensState: lensState,
        },
        patch
      );
    }

    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-document-id]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            selected_document_id: el.getAttribute("data-cts-gis-document-id") || "",
            clear_selection: true,
            mediation_state: {
              attention_document_id: el.getAttribute("data-cts-gis-document-id") || "",
              attention_node_id: "",
              intention_token: "",
            },
          })
        );
      });
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-node-id]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            clear_selection: true,
            mediation_state: {
              attention_document_id: selectedDocument.document_id || mediationState.attention_document_id || "",
              attention_node_id: el.getAttribute("data-cts-gis-node-id") || "",
              intention_token: "0",
            },
          })
        );
      });
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-intention-token]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            clear_selection: true,
            mediation_state: {
              attention_document_id: selectedDocument.document_id || mediationState.attention_document_id || "",
              attention_node_id: mediationState.attention_node_id || "",
              intention_token: el.getAttribute("data-cts-gis-intention-token") || "0",
            },
          })
        );
      });
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-row-address]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        var rowNodeId = el.getAttribute("data-cts-gis-row-node-id") || "";
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            selected_row_address: el.getAttribute("data-cts-gis-row-address") || "",
            selected_feature_id: "",
            mediation_state: rowNodeId
              ? {
                  attention_document_id: selectedDocument.document_id || mediationState.attention_document_id || "",
                  attention_node_id: rowNodeId,
                  intention_token: "0",
                }
              : undefined,
          })
        );
      });
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-feature-id]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        var featureNodeId = el.getAttribute("data-cts-gis-feature-node-id") || "";
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            selected_feature_id: el.getAttribute("data-cts-gis-feature-id") || "",
            mediation_state: featureNodeId
              ? {
                  attention_document_id: selectedDocument.document_id || mediationState.attention_document_id || "",
                  attention_node_id: featureNodeId,
                  intention_token: "0",
                }
              : undefined,
          })
        );
      });
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-overlay-mode]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            overlay_mode: el.getAttribute("data-cts-gis-overlay-mode") || "auto",
          })
        );
      });
    });
    var rawToggle = body.querySelector("#v2-cts-gis-raw-underlay-toggle");
    if (rawToggle) {
      rawToggle.addEventListener("change", function () {
        loadRuntimeView(
          requestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
          requestBody({
            raw_underlay_visible: !!rawToggle.checked,
          })
        );
      });
    }
  };

  renderers.aws_csm_family_workbench = function (ctx) {
    var wb = ctx.region || {};
    var body = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var loadShell = ctx.loadShell;
    var familyHealth = wb.family_health || {};
    var domainStates = wb.domain_states || [];
    var selectedAuthor = wb.selected_author || {};
    var subnav = wb.subsurface_navigation || {};
    var readinessSummary = wb.readiness_summary || {};
    var recoverySummary = wb.recovery_summary || {};
    var familyCards =
      '<div class="v2-card-grid">' +
      '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
      escapeHtml(familyHealth.mailbox_readiness || familyHealth.status || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Verified sender</h3><p>' +
      escapeHtml(familyHealth.selected_verified_sender || selectedAuthor.address || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Queue</h3><p>' +
      escapeHtml(familyHealth.dispatch_queue_state || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Inbound rules</h3><p>' +
      escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
      " ready</p></article>" +
      "</div>";
    var familyHealthBlock =
      '<section class="v2-card" style="margin-top:12px"><h3>Family health</h3><dl class="v2-surface-dl">' +
      "<dt>STS identity</dt><dd><code>" +
      escapeHtml(familyHealth.sts_identity_arn || "—") +
      "</code></dd><dt>Ready domains</dt><dd>" +
      escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
      "/" +
      escapeHtml(String(familyHealth.domain_count != null ? familyHealth.domain_count : "0")) +
      "</dd><dt>Dispatch queue</dt><dd>" +
      escapeHtml(familyHealth.dispatch_queue_state || "—") +
      "</dd><dt>Dispatcher Lambda</dt><dd>" +
      escapeHtml(familyHealth.dispatcher_lambda_state || "—") +
      "</dd><dt>Inbound Lambda</dt><dd>" +
      escapeHtml(familyHealth.inbound_lambda_state || "—") +
      "</dd></dl></section>";
    var navButtons =
      '<section class="v2-card" style="margin-top:12px"><h3>Family navigation</h3><div style="display:flex;gap:8px;flex-wrap:wrap">' +
      [
        { key: "read_only_shell_request", label: "Open read-only overview" },
        { key: "narrow_write_shell_request", label: "Open sender selection" },
        { key: "onboarding_shell_request", label: "Open onboarding" },
      ]
        .map(function (item) {
          var req = subnav[item.key];
          if (!req) return '<span class="ide-controlpanel__empty">' + escapeHtml(item.label) + "</span>";
          return (
            '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-shell-request-key="' +
            escapeHtml(item.key) +
            '">' +
            escapeHtml(item.label) +
            "</button>"
          );
        })
        .join("") +
      "</div></section>";
    var domainCards =
      domainStates.length > 0
        ? domainStates
            .map(function (state) {
              return (
                '<section class="v2-card" style="margin-top:12px"><h3>' +
                escapeHtml(state.domain || "domain") +
                '</h3><dl class="v2-surface-dl"><dt>Selected author</dt><dd>' +
                escapeHtml(((state.selected_author || {}).address) || "—") +
                "</dd><dt>Contacts</dt><dd>" +
                escapeHtml(String(state.contact_count != null ? state.contact_count : "0")) +
                " total · " +
                escapeHtml(String(state.subscribed_contact_count != null ? state.subscribed_contact_count : "0")) +
                " subscribed</dd><dt>Inbound</dt><dd>" +
                escapeHtml(state.inbound_state || "—") +
                "</dd><dt>Dispatch</dt><dd>" +
                escapeHtml(state.dispatch_state || "—") +
                "</dd></dl></section>"
              );
            })
            .join("")
        : '<section class="v2-card" style="margin-top:12px"><h3>Domain groups</h3><p>No AWS-CSM domain groups are currently configured for this instance.</p></section>';
    body.innerHTML =
      familyCards +
      familyHealthBlock +
      guidanceSectionHtml(escapeHtml, readinessSummary, "Readiness summary") +
      guidanceSectionHtml(escapeHtml, recoverySummary, "Recovery guidance") +
      navButtons +
      domainCards;
    Array.prototype.forEach.call(body.querySelectorAll("[data-aws-shell-request-key]"), function (node) {
      node.addEventListener("click", function () {
        var key = node.getAttribute("data-aws-shell-request-key") || "";
        if (subnav[key]) loadShell(subnav[key]);
      });
    });
  };

  renderers.aws_csm_subsurface_workbench = function (ctx) {
    var wb = ctx.region || {};
    var body = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var postShellChrome = ctx.postShellChrome;
    var profileSummary = wb.profile_summary || {};
    var awsWarnings = wb.compatibility_warnings || [];
    var readinessSummary = wb.readiness_summary || {};
    var recoverySummary = wb.recovery_summary || {};
    var openPanelButton =
      wb.submit_route
        ? '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-open-aws-interface-panel">Open interface panel</button>'
        : "";
    body.innerHTML =
      '<div class="v2-card-grid">' +
      '<article class="v2-card"><h3>Profile</h3><p>' +
      escapeHtml(profileSummary.profile_id || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Domain</h3><p>' +
      escapeHtml(profileSummary.domain || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Selected sender</h3><p>' +
      escapeHtml(wb.selected_verified_sender || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
      escapeHtml(wb.mailbox_readiness || "—") +
      "</p></article>" +
      "</div>" +
      '<section class="v2-card" style="margin-top:12px"><h3>' +
      escapeHtml(wb.title || "AWS-CSM") +
      '</h3><p>' +
      escapeHtml(wb.help_text || "") +
      "</p>" +
      openPanelButton +
      "</section>" +
      guidanceSectionHtml(escapeHtml, readinessSummary, "Readiness summary") +
      guidanceSectionHtml(escapeHtml, recoverySummary, "Recovery guidance") +
      (awsWarnings.length
        ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
          awsWarnings
            .map(function (warning) {
              return "<li>" + escapeHtml(String(warning)) + "</li>";
            })
            .join("") +
          "</ul></section>"
        : "");
    var openPanel = document.getElementById("v2-open-aws-interface-panel");
    if (openPanel) {
      openPanel.addEventListener("click", function () {
        postShellChrome({ inspector_collapsed: false });
      });
    }
  };

  renderers.cts_gis_workbench = function (ctx) {
    var wb = ctx.region || {};
    var body = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var loadRuntimeView = ctx.loadRuntimeView;
    var envelope = (ctx.getEnvelope && ctx.getEnvelope()) || {};
    var ctsGisSurface = envelope.surface_payload || {};
    var ctsGisWarnings = ctsGisSurface.warnings || wb.warnings || [];
    var ctsGisDocumentCatalog = ctsGisSurface.document_catalog || [];
    var ctsGisSelectedDocument = ctsGisSurface.selected_document || {};
    var ctsGisSelectedRow = ctsGisSurface.selected_row || {};
    var ctsGisProjection = ctsGisSurface.map_projection || {};
    var ctsGisSelectedFeature = ctsGisProjection.selected_feature || {};
    var ctsGisMediation = ctsGisSurface.mediation_state || wb.mediation_state || {};
    var ctsGisSelectionSummary = ctsGisMediation.selection_summary || {};
    var ctsGisLens = ctsGisSurface.lens_state || wb.lens_state || {};
    var ctsGisDiagnosticSummary = ctsGisSurface.diagnostic_summary || wb.diagnostic_summary || {};
    var ctsGisRows = ctsGisSurface.rows || [];
    var ctsGisRequestContract = wb.request_contract || {};

    var ctsGisWarningBlock =
      ctsGisWarnings.length > 0
        ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
          ctsGisWarnings
            .map(function (warning) {
              return "<li>" + escapeHtml(String(warning)) + "</li>";
            })
            .join("") +
          "</ul></div>"
        : "";
    var documentButtonStrip =
      ctsGisDocumentCatalog.length > 0
        ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
          ctsGisDocumentCatalog
            .map(function (doc) {
              return (
                '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-document-id="' +
                escapeHtml(doc.document_id || "") +
                '" style="border-radius:6px' +
                (doc.selected ? ";font-weight:700" : "") +
                '">' +
                escapeHtml(doc.document_name || doc.document_id || "document") +
                " (" +
                escapeHtml(String(doc.profile_count != null ? doc.profile_count : doc.projectable_feature_count != null ? doc.projectable_feature_count : 0)) +
                ")</button>"
              );
            })
            .join("") +
          "</div>"
        : "<p>No authoritative CTS-GIS documents are cataloged for this tenant.</p>";
    var documentsSectionHtml =
      '<section class="v2-card" data-cts-gis-documents="true" style="margin-top:12px"><h3>Documents</h3><dl class="v2-surface-dl">' +
      "<dt>Selected</dt><dd><code>" +
      escapeHtml(ctsGisSelectedDocument.document_name || ctsGisSelectedDocument.document_id || "—") +
      "</code></dd><dt>Relative path</dt><dd><code>" +
      escapeHtml(ctsGisSelectedDocument.relative_path || "—") +
      "</code></dd><dt>Cataloged documents</dt><dd>" +
      escapeHtml(String(ctsGisDocumentCatalog.length || 0)) +
      "</dd></dl>" +
      documentButtonStrip +
      "</section>";
    var diagnosticHtml =
      '<section class="v2-card" style="margin-top:12px"><h3>Diagnostics</h3><dl class="v2-surface-dl">' +
      "<dt>Projection state</dt><dd>" +
      escapeHtml(ctsGisDiagnosticSummary.projection_state || ctsGisProjection.projection_state || "—") +
      "</dd><dt>Rendered rows</dt><dd>" +
      escapeHtml(String(ctsGisDiagnosticSummary.render_row_count != null ? ctsGisDiagnosticSummary.render_row_count : ctsGisRows.length || 0)) +
      "</dd><dt>Rendered features</dt><dd>" +
      escapeHtml(String(ctsGisDiagnosticSummary.render_feature_count != null ? ctsGisDiagnosticSummary.render_feature_count : ctsGisProjection.feature_count != null ? ctsGisProjection.feature_count : 0)) +
      "</dd><dt>Selected row</dt><dd><code>" +
      escapeHtml(ctsGisSelectedRow.datum_address || "—") +
      "</code></dd><dt>Selected feature</dt><dd><code>" +
      escapeHtml(ctsGisSelectedFeature.feature_id || "—") +
      "</code></dd></dl></section>";
    var selectedRowEvidence =
      '<section class="v2-card" style="margin-top:12px"><h3>Selected row evidence</h3><pre class="v2-json-panel">' +
      escapeHtml(JSON.stringify(ctsGisSelectedRow.raw || ctsGisSelectedRow || {}, null, 2)) +
      "</pre></section>";
    var featureRows = (((ctsGisProjection.feature_collection || {}).features) || []).slice(0, 24);
    var featureTable =
      featureRows.length > 0
        ? '<section class="v2-card" style="margin-top:12px"><h3>Projected features</h3><table class="v2-table"><thead><tr><th>Feature</th><th>Profile</th><th>Geometry</th><th>Row</th></tr></thead><tbody>' +
          featureRows
            .map(function (feature) {
              var props = feature.properties || {};
              return (
                '<tr><td><a href="#" data-cts-gis-feature-id="' +
                escapeHtml(feature.id || "") +
                '" data-cts-gis-feature-node-id="' +
                escapeHtml(props.samras_node_id || "") +
                '"><code>' +
                escapeHtml(feature.id || "") +
                "</code></a></td><td>" +
                escapeHtml(props.profile_label || props.label_text || "—") +
                "</td><td><code>" +
                escapeHtml((feature.geometry || {}).type || "—") +
                "</code></td><td><code>" +
                escapeHtml(props.row_address || "—") +
                "</code></td></tr>"
              );
            })
            .join("") +
          "</tbody></table></section>"
        : "";
    var rowTableRows = ctsGisRows.slice(0, 180);
    var rowTable =
      '<details class="v2-card" style="margin-top:12px"><summary>Raw datum underlay</summary><div style="margin-top:12px"><table class="v2-table"><thead><tr><th>Address</th><th>Profile</th><th>Diagnostics</th><th>Overlay values</th></tr></thead><tbody>' +
      rowTableRows
        .map(function (row) {
          return (
            '<tr><td><a href="#" data-cts-gis-row-address="' +
            escapeHtml(row.datum_address || "") +
            '" data-cts-gis-row-node-id="' +
            escapeHtml(row.samras_node_id || "") +
            '"><code>' +
            escapeHtml(row.datum_address || "") +
            "</code></a></td><td>" +
            escapeHtml(row.profile_label || row.label_text || "—") +
            "</td><td>" +
            escapeHtml(((row.diagnostic_states || []).join(", ")) || "ok") +
            "</td><td>" +
            ctsGisHelpers.overlayCellHtml({
              row: row,
              escapeHtml: escapeHtml,
              lensState: ctsGisLens,
            }) +
            "</td></tr>"
          );
        })
        .join("") +
      "</tbody></table>" +
      (ctsGisRows.length > rowTableRows.length
        ? '<p class="ide-controlpanel__empty" style="margin-top:8px">Showing first ' +
          escapeHtml(String(rowTableRows.length)) +
          " of " +
          escapeHtml(String(ctsGisRows.length)) +
          " rows.</p>"
        : "") +
      "</div></details>";
    body.innerHTML =
      '<div data-cts-gis-evidence-workbench="true">' +
      ctsGisWarningBlock +
      documentsSectionHtml +
      diagnosticHtml +
      selectedRowEvidence +
      featureTable +
      rowTable +
      "</div>";

    ctsGisHelpers.bindInteractions({
      body: body,
      loadRuntimeView: loadRuntimeView,
      requestContract: ctsGisRequestContract,
      selectedDocument: ctsGisSelectedDocument,
      mediationState: ctsGisMediation,
      selectionSummary: ctsGisSelectionSummary,
      selectedRow: ctsGisSelectedRow,
      selectedFeature: ctsGisSelectedFeature,
      lensState: ctsGisLens,
    });
  };

  renderers.fnd_ebi_workbench = function (ctx) {
    var wb = ctx.region || {};
    var body = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var compactJson = ctx.compactJson;
    var loadRuntimeView = ctx.loadRuntimeView;
    var envelope = (ctx.getEnvelope && ctx.getEnvelope()) || {};
    var fndSurface = envelope.surface_payload || {};
    var fndProfileCards = wb.profile_cards || fndSurface.profile_cards || [];
    var fndOverview = wb.overview || fndSurface.overview || {};
    var fndTraffic = wb.traffic || fndSurface.traffic || {};
    var fndEventsSummary = wb.events_summary || fndSurface.events_summary || {};
    var fndErrorsNoise = wb.errors_noise || fndSurface.errors_noise || {};
    var fndFiles = wb.files || fndSurface.files || {};
    var fndWarnings = wb.warnings || fndSurface.warnings || [];
    var fndRequestContract = wb.request_contract || {};
    var fndYearMonth = fndOverview.year_month || "";

    function fndRequestBody(patch) {
      var fixed = fndRequestContract.fixed_request_fields || {};
      var bodyOut = {
        schema: fndRequestContract.request_schema || "mycite.v2.admin.fnd_ebi.read_only.request.v1",
        selected_domain: fndSurface.selected_domain || fndOverview.domain || "",
        year_month: fndYearMonth,
      };
      Object.keys(fixed || {}).forEach(function (key) {
        bodyOut[key] = fixed[key];
      });
      Object.keys(patch || {}).forEach(function (key) {
        bodyOut[key] = patch[key];
      });
      return bodyOut;
    }

    function fndMetricCard(title, value, detail) {
      return (
        '<article class="v2-card"><h3>' +
        escapeHtml(title) +
        "</h3><p>" +
        escapeHtml(String(value)) +
        "</p>" +
        (detail ? '<p class="ide-controlpanel__empty">' + escapeHtml(detail) + "</p>" : "") +
        "</article>"
      );
    }

    function fndTopListHtml(title, rows, emptyLabel) {
      if (!rows || !rows.length) {
        return (
          '<section class="v2-card fnd-ebi-detail"><h3>' +
          escapeHtml(title) +
          "</h3><p>" +
          escapeHtml(emptyLabel) +
          "</p></section>"
        );
      }
      return (
        '<section class="v2-card fnd-ebi-detail"><h3>' +
        escapeHtml(title) +
        '</h3><ol class="fnd-ebi-list">' +
        rows
          .map(function (row) {
            return (
              "<li><span><code>" +
              escapeHtml(row.key || "—") +
              "</code></span><strong>" +
              escapeHtml(String(row.count != null ? row.count : 0)) +
              "</strong></li>"
            );
          })
          .join("") +
        "</ol></section>"
      );
    }

    function fndTrend(series) {
      if (!series || !series.length) return "—";
      return series
        .map(function (value) {
          var n = Number(value || 0);
          if (n <= 0) return "·";
          if (n < 3) return "▁";
          if (n < 8) return "▃";
          if (n < 16) return "▅";
          return "▇";
        })
        .join("");
    }

    var fndWarningBlock =
      fndWarnings.length > 0
        ? '<section class="v2-card fnd-ebi-detail"><h3>Warnings</h3><ul class="fnd-ebi-warnings">' +
          fndWarnings
            .map(function (warning) {
              return "<li>" + escapeHtml(String(warning)) + "</li>";
            })
            .join("") +
          "</ul></section>"
        : "";
    var fndProfileGallery =
      fndProfileCards.length > 0
        ? '<div class="fnd-ebi-gallery">' +
          fndProfileCards
            .map(function (card) {
              return (
                '<article class="v2-card fnd-ebi-card" data-fnd-ebi-select-domain="' +
                escapeHtml(card.domain || "") +
                '" style="' +
                (card.selected ? "border-color:#285943;box-shadow:0 0 0 1px rgba(40,89,67,0.22)" : "") +
                '">' +
                "<h3>" +
                escapeHtml(card.domain || "profile") +
                '</h3><div class="tool-valueGrid">' +
                '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">health</dt><dd class="tool-valueGrid__value">' +
                escapeHtml(card.health_label || "—") +
                '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">requests</dt><dd class="tool-valueGrid__value">' +
                escapeHtml(String(card.requests_30d != null ? card.requests_30d : 0)) +
                '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">events</dt><dd class="tool-valueGrid__value">' +
                escapeHtml(String(card.events_30d != null ? card.events_30d : 0)) +
                '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">visitors</dt><dd class="tool-valueGrid__value">' +
                escapeHtml(String(card.unique_visitors_approx_30d != null ? card.unique_visitors_approx_30d : 0)) +
                '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">warnings</dt><dd class="tool-valueGrid__value">' +
                escapeHtml(String(card.warning_count != null ? card.warning_count : 0)) +
                "</dd></div></div></article>"
              );
            })
            .join("") +
          "</div>"
        : "<p>No FND-EBI profiles are available for this instance.</p>";
    var fndFileRows = [
      { label: "Profile", key: "profile_file" },
      { label: "Access log", key: "access_log" },
      { label: "Error log", key: "error_log" },
      { label: "Events file", key: "events_file" },
    ];
    var fndMetricCards =
      '<div class="v2-card-grid">' +
      fndMetricCard("Requests (30d)", fndTraffic.requests_30d != null ? fndTraffic.requests_30d : 0, "page requests " + String(fndTraffic.real_page_requests_30d != null ? fndTraffic.real_page_requests_30d : 0)) +
      fndMetricCard("Visitors (30d)", fndTraffic.unique_visitors_approx_30d != null ? fndTraffic.unique_visitors_approx_30d : 0, "approximate unique IPs") +
      fndMetricCard("Events (30d)", fndEventsSummary.events_30d != null ? fndEventsSummary.events_30d : 0, "sessions " + String(fndEventsSummary.session_count_approx != null ? fndEventsSummary.session_count_approx : 0)) +
      fndMetricCard("Bot share", Math.round(Number(fndTraffic.bot_share || 0) * 1000) / 10 + "%", "probe count " + String(fndTraffic.suspicious_probe_count != null ? fndTraffic.suspicious_probe_count : 0)) +
      "</div>";

    body.innerHTML =
      fndWarningBlock +
      '<section class="v2-card"><h3>Window</h3><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
      '<label style="display:flex;gap:8px;align-items:center">Month <input id="v2-fnd-ebi-year-month" type="month" value="' +
      escapeHtml(fndYearMonth) +
      '"></label>' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-fnd-ebi-apply-month">Apply</button>' +
      "</div></section>" +
      '<section class="v2-card fnd-ebi-detail"><h3>Profiles</h3>' +
      fndProfileGallery +
      "</section>" +
      fndMetricCards +
      '<section class="v2-card fnd-ebi-detail"><h3>Overview</h3><div class="tool-valueGrid">' +
      '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">domain</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(fndOverview.domain || "—") +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">health</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(fndOverview.health_label || "—") +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">profile file</dt><dd class="tool-valueGrid__value"><code>' +
      escapeHtml(fndOverview.profile_file || "—") +
      '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">site root</dt><dd class="tool-valueGrid__value"><code>' +
      escapeHtml(fndOverview.site_root || "—") +
      '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">analytics root</dt><dd class="tool-valueGrid__value"><code>' +
      escapeHtml(fndOverview.analytics_root || "—") +
      '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">access seen</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(fndOverview.access_last_seen_utc || "—") +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">events seen</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(fndOverview.events_last_seen_utc || "—") +
      "</dd></div></div></section>" +
      '<section class="v2-card fnd-ebi-detail"><h3>Files</h3><table class="fnd-ebi-table"><thead><tr><th>Source</th><th>State</th><th>Records</th><th>Path</th></tr></thead><tbody>' +
      fndFileRows
        .map(function (row) {
          var fileState = fndFiles[row.key] || {};
          return (
            "<tr><td>" +
            escapeHtml(row.label) +
            "</td><td>" +
            escapeHtml(fileState.state || "—") +
            "</td><td>" +
            escapeHtml(String(fileState.record_count != null ? fileState.record_count : "—")) +
            "</td><td><code>" +
            escapeHtml(fileState.path || "—") +
            "</code></td></tr>"
          );
        })
        .join("") +
      "</tbody></table></section>" +
      '<section class="v2-card fnd-ebi-detail"><h3>Traffic</h3><div class="tool-valueGrid">' +
      '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">24h</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String(fndTraffic.requests_24h != null ? fndTraffic.requests_24h : 0)) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">7d</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String(fndTraffic.requests_7d != null ? fndTraffic.requests_7d : 0)) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">30d trend</dt><dd class="tool-valueGrid__value fnd-ebi-sparkline">' +
      escapeHtml(fndTrend(fndTraffic.trend_30d || [])) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">2xx / 4xx / 5xx</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(
        String(((fndTraffic.response_breakdown || {})["2xx"]) || 0) +
          " / " +
          String(((fndTraffic.response_breakdown || {})["4xx"]) || 0) +
          " / " +
          String(((fndTraffic.response_breakdown || {})["5xx"]) || 0)
      ) +
      "</dd></div></div></section>" +
      fndTopListHtml("Top pages", fndTraffic.top_pages || [], "No recent non-bot page requests.") +
      fndTopListHtml("Top requested paths", fndTraffic.top_requested_paths || [], "No recent path data.") +
      fndTopListHtml("Top referrers", fndTraffic.top_referrers || [], "No recent referrer data.") +
      '<section class="v2-card fnd-ebi-detail"><h3>Events</h3><div class="tool-valueGrid">' +
      '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">24h</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String(fndEventsSummary.events_24h != null ? fndEventsSummary.events_24h : 0)) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">7d</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String(fndEventsSummary.events_7d != null ? fndEventsSummary.events_7d : 0)) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">30d trend</dt><dd class="tool-valueGrid__value fnd-ebi-sparkline">' +
      escapeHtml(fndTrend(fndEventsSummary.trend_30d || [])) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">invalid lines</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String(fndEventsSummary.invalid_line_count != null ? fndEventsSummary.invalid_line_count : 0)) +
      "</dd></div></div></section>" +
      fndTopListHtml(
        "Event types",
        Object.keys(fndEventsSummary.event_type_counts || {}).map(function (key) {
          return { key: key, count: (fndEventsSummary.event_type_counts || {})[key] };
        }),
        "No event types were counted."
      ) +
      '<section class="v2-card fnd-ebi-detail"><h3>Errors and noise</h3><div class="tool-valueGrid">' +
      '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">probe routes</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(String((fndErrorsNoise.top_probe_routes || []).length)) +
      '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">error severities</dt><dd class="tool-valueGrid__value">' +
      escapeHtml(compactJson(fndErrorsNoise.error_severity_counts || {})) +
      "</dd></div></div></section>" +
      fndTopListHtml("Top error routes", fndErrorsNoise.top_error_routes || [], "No recent error routes.") +
      fndTopListHtml("Top probe routes", fndErrorsNoise.top_probe_routes || [], "No suspicious probe routes were counted.");

    Array.prototype.forEach.call(body.querySelectorAll("[data-fnd-ebi-select-domain]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadRuntimeView(
          fndRequestContract.route || "/portal/api/v2/admin/fnd-ebi/read-only",
          fndRequestBody({
            selected_domain: el.getAttribute("data-fnd-ebi-select-domain") || "",
          })
        );
      });
    });
    var fndMonthInput = document.getElementById("v2-fnd-ebi-year-month");
    var fndMonthApply = document.getElementById("v2-fnd-ebi-apply-month");
    function submitFndMonth() {
      loadRuntimeView(
        fndRequestContract.route || "/portal/api/v2/admin/fnd-ebi/read-only",
        fndRequestBody({
          year_month: (fndMonthInput && fndMonthInput.value) || fndYearMonth,
        })
      );
    }
    if (fndMonthApply) {
      fndMonthApply.addEventListener("click", function (ev) {
        ev.preventDefault();
        submitFndMonth();
      });
    }
    if (fndMonthInput) {
      fndMonthInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          submitFndMonth();
        }
      });
    }
  };
})();
