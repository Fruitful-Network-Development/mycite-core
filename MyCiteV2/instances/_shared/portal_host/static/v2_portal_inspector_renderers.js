/**
 * Tool-specific inspector renderers for the V2 portal shell.
 * They consume server-issued contracts and dispatch bodies only.
 */
(function () {
  var renderers = window.PortalShellInspectorRenderers || (window.PortalShellInspectorRenderers = {});

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

  function renderCtsGisSvg(mapProjection, escapeHtml) {
    var featureCollection = (mapProjection && mapProjection.feature_collection) || {};
    var features = featureCollection.features || [];
    if (!features.length) {
      return (
        '<div class="v2-card" data-cts-gis-geojson-lens="true" style="margin-top:12px"><h3>Geographic pane</h3><p>No projectable features are available for this document.</p></div>'
      );
    }
    var bounds = featureCollection.bounds || [-180, -90, 180, 90];
    var minLon = Number(bounds[0]);
    var minLat = Number(bounds[1]);
    var maxLon = Number(bounds[2]);
    var maxLat = Number(bounds[3]);
    if (!isFinite(minLon) || !isFinite(minLat) || !isFinite(maxLon) || !isFinite(maxLat)) {
      minLon = -180;
      minLat = -90;
      maxLon = 180;
      maxLat = 90;
    }
    if (minLon === maxLon) {
      minLon -= 1;
      maxLon += 1;
    }
    if (minLat === maxLat) {
      minLat -= 1;
      maxLat += 1;
    }
    var width = 680;
    var height = 360;
    var pad = 18;
    function project(coord) {
      var lon = Number((coord || [0, 0])[0]);
      var lat = Number((coord || [0, 0])[1]);
      var x = pad + ((lon - minLon) / (maxLon - minLon)) * (width - pad * 2);
      var y = height - pad - ((lat - minLat) / (maxLat - minLat)) * (height - pad * 2);
      return [x.toFixed(2), y.toFixed(2)];
    }
    var shapes = features
      .map(function (feature) {
        var geometry = feature.geometry || {};
        var props = feature.properties || {};
        var featureId = feature.id || "";
        var selected = !!feature.selected;
        var attentionMember = !!props.attention_member;
        var stroke = selected ? "#0b57d0" : attentionMember ? "#9a5b00" : "#285943";
        var fill = selected
          ? "rgba(11,87,208,0.28)"
          : attentionMember
          ? "rgba(154,91,0,0.22)"
          : "rgba(40,89,67,0.18)";
        var title = escapeHtml(props.profile_label || props.label_text || featureId || "feature");
        if (geometry.type === "Point") {
          var point = project(geometry.coordinates || [0, 0]);
          return (
            '<g class="v2-map-feature" data-cts-gis-feature-id="' +
            escapeHtml(featureId) +
            '">' +
            "<title>" +
            title +
            "</title>" +
            '<circle cx="' +
            point[0] +
            '" cy="' +
            point[1] +
            '" r="' +
            (selected ? "7" : "5") +
            '" fill="' +
            fill +
            '" stroke="' +
            stroke +
            '" stroke-width="2"></circle></g>'
          );
        }
        if (geometry.type === "Polygon") {
          var ring = ((geometry.coordinates || [])[0] || []).map(project);
          var points = ring
            .map(function (point) {
              return point[0] + "," + point[1];
            })
            .join(" ");
          return (
            '<g class="v2-map-feature" data-cts-gis-feature-id="' +
            escapeHtml(featureId) +
            '">' +
            "<title>" +
            title +
            "</title>" +
            '<polygon points="' +
            points +
            '" fill="' +
            fill +
            '" stroke="' +
            stroke +
            '" stroke-width="' +
            (selected ? "2.8" : "1.6") +
            '"></polygon></g>'
          );
        }
        return "";
      })
      .join("");
    return (
      '<div class="v2-card" data-cts-gis-geojson-lens="true" style="margin-top:12px"><h3>Geographic pane</h3><svg viewBox="0 0 ' +
      width +
      " " +
      height +
      '" style="width:100%;height:auto;border:1px solid #d3d9df;background:linear-gradient(180deg,#f7fbf9,#eef4f1)">' +
      '<rect x="0" y="0" width="' +
      width +
      '" height="' +
      height +
      '" fill="transparent"></rect>' +
      shapes +
      "</svg></div>"
    );
  }

  renderers.cts_gis_interface_panel = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var renderMap = ctx.renderCtsGisSvg || function (projection) {
      return renderCtsGisSvg(projection, escapeHtml);
    };
    var loadRuntimeView = ctx.loadRuntimeView;
    var envelope = (ctx.getEnvelope && ctx.getEnvelope()) || {};
    var mapSurface = envelope.surface_payload || {};
    var mapAttentionProfile = mapSurface.attention_profile || {};
    var mapMediationState = mapSurface.mediation_state || {};
    var mapAvailableIntentions = mapMediationState.available_intentions || [];
    var mapRenderSetSummary = mapSurface.render_set_summary || {};
    var mapSelectedDocument = mapSurface.selected_document || {};
    var mapLineage = mapSurface.lineage || [];
    var mapChildren = mapSurface.children || [];
    var mapRelatedProfiles = mapSurface.related_profiles || [];
    var mapSelectedFeature = (mapSurface.map_projection || {}).selected_feature || {};
    var mapSelectedRow = mapSurface.selected_row || {};
    var mapDiagnosticSummary = mapSurface.diagnostic_summary || {};
    var mapLensState = mapSurface.lens_state || {};
    var mapSelectionSummary = mapMediationState.selection_summary || {};
    var mapWarnings = ((mapSurface.warnings || region.warnings) || [])
      .map(function (warning) {
        return "<li>" + escapeHtml(String(warning)) + "</li>";
      })
      .join("");
    var requestContract = region.request_contract || {};
    var ctsGisHelpers = window.PortalShellCtsGisHelpers || {};

    function profileButton(profile, isActive) {
      if (typeof ctsGisHelpers.profileButtonHtml === "function") {
        return ctsGisHelpers.profileButtonHtml({
          profile: profile,
          escapeHtml: escapeHtml,
          attrName: "data-cts-gis-node-id",
          isActive: isActive,
        });
      }
      return "";
    }

    function bindInteractions() {
      if (typeof ctsGisHelpers.bindInteractions !== "function") return;
      ctsGisHelpers.bindInteractions({
        body: content,
        loadRuntimeView: loadRuntimeView,
        requestContract: requestContract,
        selectedDocument: mapSelectedDocument,
        mediationState: mapMediationState,
        selectionSummary: mapSelectionSummary,
        selectedRow: mapSelectedRow,
        selectedFeature: mapSelectedFeature,
        lensState: mapLensState,
      });
    }

    var panelCards =
      '<div class="v2-card-grid">' +
      '<article class="v2-card"><h3>Document</h3><p>' +
      escapeHtml(mapSelectedDocument.document_name || mapSelectedDocument.document_id || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Attention</h3><p>' +
      escapeHtml(mapAttentionProfile.profile_label || mapAttentionProfile.node_id || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Intention</h3><p>' +
      escapeHtml(String(mapRenderSetSummary.render_mode || mapMediationState.intention_token || "—").replace(/_/g, " ")) +
      "</p></article>" +
      '<article class="v2-card"><h3>Features</h3><p>' +
      escapeHtml(String(mapDiagnosticSummary.render_feature_count != null ? mapDiagnosticSummary.render_feature_count : mapDiagnosticSummary.feature_count != null ? mapDiagnosticSummary.feature_count : "0")) +
      "</p></article>" +
      "</div>";
    var attentionShellHtml =
      mapLineage.length > 0
        ? '<section class="v2-card" style="margin-top:12px"><h3>Attention shell</h3><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
          mapLineage
            .map(function (profile) {
              return profileButton(
                profile,
                !!profile.selected || String(profile.node_id || "") === String(mapMediationState.attention_node_id || "")
              );
            })
            .join('<span aria-hidden="true">/</span>') +
          "</div></section>"
        : "";
    var intentionHtml =
      '<section class="v2-card" style="margin-top:12px"><h3>Intention controls</h3>' +
      (mapAvailableIntentions.length > 0
        ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
          mapAvailableIntentions
            .map(function (option) {
              return (
                '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-intention-token="' +
                escapeHtml(option.token || "") +
                '" style="border-radius:6px' +
                (option.active ? ";font-weight:700" : "") +
                '">' +
                escapeHtml(option.label || option.token || "intention") +
                " (" +
                escapeHtml(String(option.feature_count != null ? option.feature_count : 0)) +
                ")</button>"
              );
            })
            .join("") +
          "</div>"
        : "<p>No intention controls are available for the current attention state.</p>") +
      "</section>";
    var lensHtml =
      '<section class="v2-card" style="margin-top:12px"><h3>Lens</h3>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-overlay-mode="auto" style="border-radius:6px' +
      ((mapLensState.overlay_mode || "auto") === "auto" ? ";font-weight:700" : "") +
      '">Auto overlay</button>' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-overlay-mode="raw_only" style="border-radius:6px' +
      ((mapLensState.overlay_mode || "auto") === "raw_only" ? ";font-weight:700" : "") +
      '">Raw only</button>' +
      '<label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="v2-cts-gis-raw-underlay-toggle"' +
      (mapLensState.raw_underlay_visible ? " checked" : "") +
      "> show raw values</label></div></section>";
    var operatorSummaryHtml =
      '<section class="v2-card" style="margin-top:12px"><h3>Operator focus</h3><dl class="v2-surface-dl">' +
      "<dt>Document</dt><dd><code>" +
      escapeHtml(mapSelectedDocument.document_name || "—") +
      "</code></dd><dt>Relative path</dt><dd><code>" +
      escapeHtml(mapSelectedDocument.relative_path || "—") +
      "</code></dd><dt>Attention node</dt><dd><code>" +
      escapeHtml(mapAttentionProfile.node_id || "—") +
      "</code></dd><dt>Selected feature</dt><dd><code>" +
      escapeHtml(mapSelectedFeature.feature_id || "—") +
      "</code></dd><dt>Selected row</dt><dd><code>" +
      escapeHtml(mapSelectedRow.datum_address || "—") +
      "</code></dd><dt>Overlay mode</dt><dd>" +
      escapeHtml(mapLensState.overlay_mode || "—") +
      "</dd></dl></section>";
    var attentionProfileHtml =
      mapAttentionProfile && (mapAttentionProfile.node_id || mapAttentionProfile.profile_label)
        ? '<section class="v2-card" style="margin-top:12px"><h3>Attention profile</h3><dl class="v2-surface-dl">' +
          "<dt>Profile</dt><dd>" +
          escapeHtml(mapAttentionProfile.profile_label || "—") +
          "</dd><dt>Node</dt><dd><code>" +
          escapeHtml(mapAttentionProfile.node_id || "—") +
          "</code></dd><dt>Row</dt><dd><code>" +
          escapeHtml(mapAttentionProfile.row_address || "—") +
          "</code></dd><dt>Children</dt><dd>" +
          escapeHtml(String(mapAttentionProfile.child_count != null ? mapAttentionProfile.child_count : "0")) +
          "</dd><dt>Features</dt><dd>" +
          escapeHtml(String(mapAttentionProfile.feature_count != null ? mapAttentionProfile.feature_count : "0")) +
          "</dd></dl></section>"
        : "";
    var selectedFeatureHtml =
      mapSelectedFeature && mapSelectedFeature.feature_id
        ? '<section class="v2-card" style="margin-top:12px"><h3>Selected feature</h3><dl class="v2-surface-dl">' +
          "<dt>Feature</dt><dd><code>" +
          escapeHtml(mapSelectedFeature.feature_id || "") +
          "</code></dd><dt>Geometry</dt><dd>" +
          escapeHtml(mapSelectedFeature.geometry_type || "—") +
          "</dd><dt>Row</dt><dd><code>" +
          escapeHtml(mapSelectedFeature.row_address || "—") +
          "</code></dd><dt>Label</dt><dd>" +
          escapeHtml(mapSelectedFeature.profile_label || mapSelectedFeature.label_text || "—") +
          "</dd><dt>Node</dt><dd><code>" +
          escapeHtml(mapSelectedFeature.samras_node_id || "—") +
          "</code></dd></dl></section>"
        : "";
    var childrenHtml =
      '<section class="v2-card" style="margin-top:12px"><h3>Children</h3>' +
      (mapChildren.length > 0
        ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
          mapChildren
            .map(function (profile) {
              return profileButton(profile, false);
            })
            .join("") +
          "</div>"
        : "<p>No direct child profiles are available for the current attention node.</p>") +
      "</section>";
    var relatedHtml =
      mapRelatedProfiles.length > 0
        ? '<section class="v2-card" style="margin-top:12px"><h3>Related profiles</h3><ul>' +
          mapRelatedProfiles
            .map(function (profile) {
              return (
                "<li><strong>" +
                escapeHtml(profile.profile_label || profile.node_id || "profile") +
                "</strong> <small>" +
                escapeHtml(profile.relation || "related") +
                "</small></li>"
              );
            })
            .join("") +
          "</ul></section>"
        : "";
    if (titleEl) titleEl.textContent = region.title || "CTS-GIS";
    content.innerHTML =
      '<div data-cts-gis-interface-panel="true">' +
      panelCards +
      renderMap(mapSurface.map_projection || {}) +
      attentionShellHtml +
      intentionHtml +
      lensHtml +
      operatorSummaryHtml +
      attentionProfileHtml +
      selectedFeatureHtml +
      childrenHtml +
      relatedHtml +
      (mapWarnings
        ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
          mapWarnings +
          "</ul></section>"
        : "") +
      "</div>";
    bindInteractions();
  };

  renderers.cts_gis_summary = renderers.cts_gis_interface_panel;

  renderers.fnd_ebi_summary = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var fndSummary = region.summary || {};
    var fndSelectedProfile = region.selected_profile || {};
    var fndInspectorWarnings = (region.warnings || [])
      .map(function (warning) {
        return "<li>" + escapeHtml(String(warning)) + "</li>";
      })
      .join("");
    if (titleEl) titleEl.textContent = region.title || "FND-EBI";
    content.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Domain</dt><dd><code>" +
      escapeHtml(fndSummary.domain || "—") +
      "</code></dd>" +
      "<dt>Health</dt><dd>" +
      escapeHtml(fndSummary.health_label || "—") +
      "</dd>" +
      "<dt>Month</dt><dd>" +
      escapeHtml(fndSummary.year_month || "—") +
      "</dd>" +
      "<dt>Access state</dt><dd>" +
      escapeHtml(fndSummary.access_state || "—") +
      "</dd>" +
      "<dt>Events state</dt><dd>" +
      escapeHtml(fndSummary.events_state || "—") +
      "</dd>" +
      "<dt>Profile file</dt><dd><code>" +
      escapeHtml(fndSelectedProfile.profile_file || "—") +
      "</code></dd>" +
      "<dt>Site root</dt><dd><code>" +
      escapeHtml(fndSelectedProfile.site_root || "—") +
      "</code></dd>" +
      "<dt>Analytics root</dt><dd><code>" +
      escapeHtml(fndSelectedProfile.analytics_root || "—") +
      "</code></dd></dl>" +
      (fndInspectorWarnings
        ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
          fndInspectorWarnings +
          "</ul></section>"
        : "");
  };

  renderers.aws_csm_family_home = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var postJson = ctx.postJson;
    var loadShell = ctx.loadShell;
    var cloneRequestWithoutChrome = ctx.cloneRequestWithoutChrome;
    var getLastShellRequest = ctx.getLastShellRequest;
    var familyHealth = region.family_health || {};
    var primaryReadOnly = region.primary_read_only || {};
    var domainStates = region.domain_states || [];
    var newsletterContract = region.newsletter_request_contract || {};
    var newsletterFixed = newsletterContract.fixed_request_fields || {};
    var navigation = region.subsurface_navigation || {};
    var gatedSubsurfaces = region.gated_subsurfaces || {};
    var readinessSummary = region.readiness_summary || {};
    var recoverySummary = region.recovery_summary || {};
    var callerIdentity = familyHealth.caller_identity || {};
    var queueHealth = familyHealth.dispatch_queue || {};
    var dispatcherHealth = familyHealth.dispatcher_lambda || {};
    var inboundHealth = familyHealth.inbound_processor_lambda || {};

    function familyNewsletterBody(patch) {
      var bodyOut = {
        schema: newsletterContract.request_schema || "mycite.v2.admin.aws_csm.newsletter.request.v1",
      };
      Object.keys(newsletterFixed || {}).forEach(function (key) {
        bodyOut[key] = newsletterFixed[key];
      });
      Object.keys(patch || {}).forEach(function (key) {
        bodyOut[key] = patch[key];
      });
      return bodyOut;
    }

    var domainSections = domainStates.length
      ? domainStates
          .map(function (state, index) {
            var profile = state.profile || {};
            var readiness = state.readiness || {};
            var latestDispatch = state.latest_dispatch || {};
            var verifiedAuthors = state.verified_author_profiles || [];
            var options = verifiedAuthors
              .map(function (author) {
                var profileId = author.profile_id || "";
                return (
                  '<option value="' +
                  escapeHtml(profileId) +
                  '"' +
                  (profileId === (profile.selected_author_profile_id || "") ? " selected" : "") +
                  ">" +
                  escapeHtml((author.send_as_email || profileId || "author") + (author.role ? " · " + author.role : "")) +
                  "</option>"
                );
              })
              .join("");
            var warnings = (state.warnings || [])
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("");
            return (
              '<section class="v2-card" style="margin-top:12px" data-aws-csm-domain="' +
              escapeHtml(state.domain || "") +
              '">' +
              "<h3>" +
              escapeHtml(state.domain || "domain") +
              "</h3>" +
              '<dl class="v2-surface-dl">' +
              "<dt>Selected author</dt><dd><code>" +
              escapeHtml(profile.selected_author_address || "—") +
              "</code></dd>" +
              "<dt>Contacts</dt><dd>" +
              escapeHtml(String(state.contact_count != null ? state.contact_count : "0")) +
              " total · " +
              escapeHtml(String(state.subscribed_count != null ? state.subscribed_count : "0")) +
              " subscribed</dd>" +
              "<dt>Inbound</dt><dd>" +
              escapeHtml(readiness.inbound_capture_status || "—") +
              "</dd>" +
              "<dt>Dispatch</dt><dd>" +
              escapeHtml(readiness.dispatch_configured ? "configured" : "not configured") +
              "</dd>" +
              "<dt>Latest dispatch</dt><dd><code>" +
              escapeHtml(latestDispatch.dispatch_id || "—") +
              "</code></dd>" +
              "</dl>" +
              (options
                ? '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
                  '<select data-aws-csm-author-select="' +
                  escapeHtml(state.domain || "") +
                  '" style="min-width:280px;padding:6px 8px">' +
                  options +
                  "</select>" +
                  '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-csm-select-author="' +
                  escapeHtml(state.domain || "") +
                  '" style="border-radius:6px">Select author</button>' +
                  "</div>"
                : '<p class="ide-controlpanel__empty">No verified authors are available for this domain yet.</p>') +
              '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">' +
              '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-csm-reprocess="' +
              escapeHtml(state.domain || "") +
              '" style="border-radius:6px">Reprocess latest inbound</button>' +
              "</div>" +
              (warnings
                ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' + warnings + "</ul></section>"
                : "") +
              (index === 0
                ? '<pre id="v2-aws-csm-newsletter-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>'
                : "") +
              "</section>"
            );
          })
          .join("")
      : '<section class="v2-card" style="margin-top:12px"><h3>Newsletter operations</h3><p>No newsletter domains are currently visible for this AWS-CSM family surface.</p></section>';

    if (titleEl) titleEl.textContent = region.title || "AWS-CSM";
    content.innerHTML =
      '<div class="v2-card-grid">' +
      '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
      escapeHtml(primaryReadOnly.mailbox_readiness || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Verified sender</h3><p><code>' +
      escapeHtml(primaryReadOnly.selected_verified_sender || "") +
      "</code></p></article>" +
      '<article class="v2-card"><h3>Queue</h3><p>' +
      escapeHtml(queueHealth.status || "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>Inbound rules</h3><p>' +
      escapeHtml(String((familyHealth.receipt_rules || []).filter(function (row) { return row.status === "ok"; }).length)) +
      " ready</p></article>" +
      "</div>" +
      '<section class="v2-card" style="margin-top:12px"><h3>Family health</h3><dl class="v2-surface-dl">' +
      "<dt>STS identity</dt><dd><code>" +
      escapeHtml(callerIdentity.arn || callerIdentity.status || "—") +
      "</code></dd>" +
      "<dt>Ready domains</dt><dd>" +
      escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
      " / " +
      escapeHtml(String(familyHealth.domain_count != null ? familyHealth.domain_count : "0")) +
      "</dd>" +
      "<dt>Dispatch queue</dt><dd>" +
      escapeHtml(queueHealth.status || "—") +
      "</dd>" +
      "<dt>Dispatcher Lambda</dt><dd>" +
      escapeHtml(dispatcherHealth.status || "—") +
      "</dd>" +
      "<dt>Inbound Lambda</dt><dd>" +
      escapeHtml(inboundHealth.status || "—") +
      "</dd>" +
      "</dl></section>" +
      guidanceSectionHtml(escapeHtml, readinessSummary, "Readiness summary") +
      guidanceSectionHtml(escapeHtml, recoverySummary, "Recovery guidance") +
      '<section class="v2-card" style="margin-top:12px"><h3>Family navigation</h3><div style="display:flex;gap:8px;flex-wrap:wrap">' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-read-only" style="border-radius:6px">Open read-only overview</button>' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-write" style="border-radius:6px">Open sender selection</button>' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-onboarding" style="border-radius:6px">Open onboarding</button>' +
      (gatedSubsurfaces.sandbox
        ? '<span class="ide-controlpanel__empty" style="align-self:center">Sandbox is intentionally gated for this instance.</span>'
        : '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-sandbox" style="border-radius:6px">Open sandbox</button>') +
      "</div></section>" +
      domainSections;

    var resultPanel = document.getElementById("v2-aws-csm-newsletter-result");

    function submitNewsletterAction(bodyPatch) {
      if (!newsletterContract.route) return Promise.resolve();
      if (resultPanel) {
        resultPanel.hidden = false;
        resultPanel.textContent = "…";
      }
      return postJson(newsletterContract.route, familyNewsletterBody(bodyPatch)).then(function (res) {
        if (resultPanel) resultPanel.textContent = JSON.stringify(res.json, null, 2);
        if (res.ok) {
          var lastShellRequest = getLastShellRequest && getLastShellRequest();
          if (lastShellRequest) {
            return loadShell(cloneRequestWithoutChrome(lastShellRequest));
          }
        }
        return Promise.resolve();
      });
    }

    var readOnlyButton = document.getElementById("v2-aws-csm-open-read-only");
    if (readOnlyButton) {
      readOnlyButton.addEventListener("click", function (ev) {
        ev.preventDefault();
        postJson("/portal/api/v2/admin/aws/read-only", {
          schema: "mycite.v2.admin.aws.read_only.request.v1",
          tenant_scope: newsletterFixed.tenant_scope || {},
        }).then(function (res) {
          if (resultPanel) {
            resultPanel.hidden = false;
            resultPanel.textContent = JSON.stringify(res.json, null, 2);
          }
        });
      });
    }
    var writeButton = document.getElementById("v2-aws-csm-open-write");
    if (writeButton) {
      writeButton.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (navigation.narrow_write_shell_request) loadShell(navigation.narrow_write_shell_request);
      });
    }
    var onboardingButton = document.getElementById("v2-aws-csm-open-onboarding");
    if (onboardingButton) {
      onboardingButton.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (navigation.onboarding_shell_request) loadShell(navigation.onboarding_shell_request);
      });
    }
    var sandboxButton = document.getElementById("v2-aws-csm-open-sandbox");
    if (sandboxButton) {
      sandboxButton.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (navigation.sandbox_shell_request) loadShell(navigation.sandbox_shell_request);
      });
    }
    Array.prototype.forEach.call(content.querySelectorAll("[data-aws-csm-select-author]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        var domain = el.getAttribute("data-aws-csm-select-author") || "";
        var select = content.querySelector('[data-aws-csm-author-select="' + domain.replace(/"/g, '\\"') + '"]');
        var profileId = select ? select.value : "";
        submitNewsletterAction({
          domain: domain,
          action: "select_author",
          selected_author_profile_id: profileId,
        });
      });
    });
    Array.prototype.forEach.call(content.querySelectorAll("[data-aws-csm-reprocess]"), function (el) {
      el.addEventListener("click", function (ev) {
        ev.preventDefault();
        submitNewsletterAction({
          domain: el.getAttribute("data-aws-csm-reprocess") || "",
          action: "reprocess_latest_inbound",
        });
      });
    });
  };

  renderers.aws_read_only_surface = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var ps = region.profile_summary || {};
    var doms = (region.allowed_send_domains || []).join(", ");
    var cw = (region.compatibility_warnings || [])
      .map(function (w) {
        return "<li>" + escapeHtml(String(w)) + "</li>";
      })
      .join("");
    if (titleEl) titleEl.textContent = region.title || "AWS read-only";
    content.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Tenant scope</dt><dd>" +
      escapeHtml(region.tenant_scope_id || "—") +
      "</dd>" +
      "<dt>Mailbox readiness</dt><dd>" +
      escapeHtml(region.mailbox_readiness || "—") +
      "</dd>" +
      "<dt>SMTP</dt><dd>" +
      escapeHtml(region.smtp_state || "—") +
      "</dd>" +
      "<dt>Gmail</dt><dd>" +
      escapeHtml(region.gmail_state || "—") +
      "</dd>" +
      "<dt>Verified sender</dt><dd><code>" +
      escapeHtml(region.selected_verified_sender || "") +
      "</code></dd>" +
      "<dt>Allowed send domains</dt><dd>" +
      escapeHtml(doms || "—") +
      "</dd>" +
      "<dt>Profile</dt><dd>" +
      escapeHtml(ps.profile_id || "—") +
      " · " +
      escapeHtml(ps.domain || "—") +
      "</dd>" +
      "<dt>Write capability</dt><dd>" +
      escapeHtml(region.write_capability || "—") +
      "</dd></dl>" +
      (cw ? '<section class="v2-card" style="margin-top:12px"><h3>Compatibility</h3><ul>' + cw + "</ul></section>" : "");
  };

  renderers.aws_tool_error = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var wn = (region.warnings || [])
      .map(function (w) {
        return "<li>" + escapeHtml(String(w)) + "</li>";
      })
      .join("");
    if (titleEl) titleEl.textContent = region.title || "Tool error";
    content.innerHTML =
      '<div class="v2-card" style="border-color:#c5221f"><h3>' +
      escapeHtml(region.error_code || "error") +
      "</h3><p>" +
      escapeHtml(region.error_message || "") +
      "</p>" +
      (wn ? "<ul>" + wn + "</ul>" : "") +
      "</div>";
  };

  renderers.narrow_write_form = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var postJson = ctx.postJson;
    var loadShell = ctx.loadShell;
    var cloneRequestWithoutChrome = ctx.cloneRequestWithoutChrome;
    var getLastShellRequest = ctx.getLastShellRequest;
    var contract = region.submit_contract || {};
    var initial = contract.initial_values || {};
    var fixed = contract.fixed_request_fields || {};
    var html =
      '<form id="v2-narrow-write-form" class="v2-card" style="max-width:520px">' +
      "<h3>Bounded write</h3>" +
      '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
      escapeHtml(contract.request_schema || "") +
      "</code></p>" +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
      '<input name="profile_id" value="' +
      escapeHtml(initial.profile_id || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">selected_verified_sender</label>' +
      '<input name="selected_verified_sender" value="' +
      escapeHtml(initial.selected_verified_sender || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
      '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply narrow write</button>' +
      "</form>" +
      '<pre id="v2-narrow-write-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
    if (titleEl) titleEl.textContent = region.title || "Bounded write";
    content.innerHTML = html;
    var form = document.getElementById("v2-narrow-write-form");
    var out = document.getElementById("v2-narrow-write-result");
    if (form && out) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var fd = new FormData(form);
        var body = {
          schema: contract.request_schema,
          profile_id: (fd.get("profile_id") || "").toString().trim(),
          selected_verified_sender: (fd.get("selected_verified_sender") || "").toString().trim(),
        };
        if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
        if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
        out.hidden = false;
        out.textContent = "…";
        postJson(contract.route || "/portal/api/v2/admin/aws/narrow-write", body).then(function (res) {
          out.textContent = JSON.stringify(res.json, null, 2);
          var lastShellRequest = getLastShellRequest && getLastShellRequest();
          if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
        });
      });
    }
  };

  renderers.csm_onboarding_form = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var postJson = ctx.postJson;
    var loadShell = ctx.loadShell;
    var cloneRequestWithoutChrome = ctx.cloneRequestWithoutChrome;
    var getLastShellRequest = ctx.getLastShellRequest;
    var contract = region.submit_contract || {};
    var initial = contract.initial_values || {};
    var fixed = contract.fixed_request_fields || {};
    var options = contract.onboarding_action_options || [];
    var readinessSummary = region.readiness_summary || {};
    var recoverySummary = region.recovery_summary || {};
    var optHtml = options
      .map(function (a) {
        return (
          '<option value="' +
          escapeHtml(a) +
          '"' +
          (a === (initial.onboarding_action || "") ? " selected" : "") +
          ">" +
          escapeHtml(a) +
          "</option>"
        );
      })
      .join("");
    var html =
      '<form id="v2-csm-onboarding-form" class="v2-card" style="max-width:560px">' +
      "<h3>AWS-CSM onboarding</h3>" +
      '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
      escapeHtml(contract.request_schema || "") +
      "</code></p>" +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">onboarding_action</label>' +
      '<select name="onboarding_action" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px">' +
      optHtml +
      "</select>" +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
      '<input name="profile_id" value="' +
      escapeHtml(initial.profile_id || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
      '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply onboarding step</button>' +
      "</form>" +
      guidanceSectionHtml(escapeHtml, readinessSummary, "Readiness summary") +
      guidanceSectionHtml(escapeHtml, recoverySummary, "Recovery guidance") +
      '<pre id="v2-csm-onboarding-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
    if (titleEl) titleEl.textContent = region.title || "AWS-CSM onboarding";
    content.innerHTML = html;
    var form = document.getElementById("v2-csm-onboarding-form");
    var out = document.getElementById("v2-csm-onboarding-result");
    if (form && out) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var fd = new FormData(form);
        var body = {
          schema: contract.request_schema,
          profile_id: (fd.get("profile_id") || "").toString().trim(),
          onboarding_action: (fd.get("onboarding_action") || "").toString().trim(),
        };
        if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
        if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
        out.hidden = false;
        out.textContent = "…";
        postJson(contract.route || "/portal/api/v2/admin/aws/csm-onboarding", body).then(function (res) {
          out.textContent = JSON.stringify(res.json, null, 2);
          var lastShellRequest = getLastShellRequest && getLastShellRequest();
          if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
        });
      });
    }
  };

  renderers.empty = function (ctx) {
    var region = ctx.region || {};
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Interface panel";
    ctx.target.innerHTML = '<p class="ide-inspector__empty">' + ctx.escapeHtml(region.body_text || "") + "</p>";
  };

  renderers.json_document = function (ctx) {
    if (ctx.titleEl) ctx.titleEl.textContent = (ctx.region || {}).title || "Interface panel";
    ctx.target.innerHTML =
      '<pre class="v2-json-panel">' +
      ctx.escapeHtml(JSON.stringify(((ctx.region || {}).document) || {}, null, 2)) +
      "</pre>";
  };

  renderers.datum_summary = function (ctx) {
    var region = ctx.region || {};
    var selectedDocument = region.selected_document || {};
    var escapeHtml = ctx.escapeHtml;
    var datumWarnings = (region.warnings || [])
      .map(function (warning) {
        return "<li>" + escapeHtml(String(warning)) + "</li>";
      })
      .join("");
    var totals = selectedDocument.diagnostic_totals || {};
    var totalItems = Object.keys(totals)
      .filter(function (key) {
        return Number(totals[key] || 0) > 0;
      })
      .map(function (key) {
        return "<li><code>" + escapeHtml(String(key)) + "</code>: " + escapeHtml(String(totals[key])) + "</li>";
      })
      .join("");
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Datum summary";
    ctx.target.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Document</dt><dd><code>" +
      escapeHtml(selectedDocument.document_name || "—") +
      "</code></dd><dt>Relative path</dt><dd><code>" +
      escapeHtml(selectedDocument.relative_path || "—") +
      "</code></dd><dt>Source kind</dt><dd>" +
      escapeHtml(selectedDocument.source_kind || "—") +
      "</dd><dt>Anchor file</dt><dd><code>" +
      escapeHtml(selectedDocument.anchor_document_name || "—") +
      "</code></dd><dt>Anchor resolution</dt><dd>" +
      escapeHtml(selectedDocument.anchor_resolution || "—") +
      "</dd><dt>Rows</dt><dd>" +
      escapeHtml(String(selectedDocument.row_count != null ? selectedDocument.row_count : "—")) +
      "</dd></dl>" +
      (totalItems
        ? '<section class="v2-card" style="margin-top:12px"><h3>Diagnostic totals</h3><ul>' + totalItems + "</ul></section>"
        : "") +
      (datumWarnings
        ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' + datumWarnings + "</ul></section>"
        : "");
  };

  renderers.network_summary = function (ctx) {
    var region = ctx.region || {};
    var escapeHtml = ctx.escapeHtml;
    var networkSummary = region.summary || {};
    var networkInstance = region.portal_instance || {};
    var notes = (region.notes || [])
      .map(function (note) {
        return "<li>" + escapeHtml(String(note)) + "</li>";
      })
      .join("");
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Network summary";
    ctx.target.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>State</dt><dd>" +
      escapeHtml(region.network_state || "—") +
      "</dd><dt>Active tab</dt><dd>" +
      escapeHtml(region.active_tab || "—") +
      "</dd><dt>Hosted root</dt><dd>" +
      escapeHtml(networkSummary.hosted_root || "—") +
      "</dd><dt>Portal instance</dt><dd><code>" +
      escapeHtml(networkInstance.portal_instance_id || networkSummary.portal_instance_id || "—") +
      "</code></dd><dt>Domain</dt><dd><code>" +
      escapeHtml(networkInstance.domain || networkSummary.domain || "—") +
      "</code></dd><dt>Host aliases</dt><dd>" +
      escapeHtml(String(networkSummary.host_alias_count != null ? networkSummary.host_alias_count : "0")) +
      "</dd><dt>Progeny links</dt><dd>" +
      escapeHtml(String(networkSummary.progeny_link_count != null ? networkSummary.progeny_link_count : "0")) +
      "</dd><dt>P2P contracts</dt><dd>" +
      escapeHtml(String(networkSummary.contract_count != null ? networkSummary.contract_count : "0")) +
      "</dd><dt>Request-log events</dt><dd>" +
      escapeHtml(String(networkSummary.request_log_event_count != null ? networkSummary.request_log_event_count : "0")) +
      "</dd><dt>Local audit</dt><dd>" +
      escapeHtml(networkSummary.local_audit_state || "—") +
      "</dd><dt>Visible utilities</dt><dd>" +
      escapeHtml(String(networkSummary.visible_utility_count != null ? networkSummary.visible_utility_count : "0")) +
      "</dd></dl>" +
      (notes
        ? '<section class="v2-card" style="margin-top:12px"><h3>Notes</h3><ul>' + notes + "</ul></section>"
        : "");
  };

  renderers.tenant_profile_summary = function (ctx) {
    var region = ctx.region || {};
    var summary = region.summary || {};
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Tenant profile";
    ctx.target.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Profile title</dt><dd>" +
      ctx.escapeHtml(summary.profile_title || "—") +
      "</dd><dt>Tenant</dt><dd>" +
      ctx.escapeHtml(summary.tenant_id || "—") +
      "</dd><dt>Domain</dt><dd>" +
      ctx.escapeHtml(summary.tenant_domain || "—") +
      "</dd><dt>Entity type</dt><dd>" +
      ctx.escapeHtml(summary.entity_type || "—") +
      "</dd><dt>Profile summary</dt><dd>" +
      ctx.escapeHtml(summary.profile_summary || "—") +
      "</dd><dt>Contact email</dt><dd>" +
      ctx.escapeHtml(summary.contact_email || "—") +
      "</dd><dt>Public website</dt><dd>" +
      ctx.escapeHtml(summary.public_website_url || "—") +
      "</dd><dt>Available documents</dt><dd>" +
      ctx.escapeHtml((summary.available_documents || []).join(", ") || "—") +
      "</dd></dl>";
  };

  renderers.operational_status_summary = function (ctx) {
    var region = ctx.region || {};
    var operational = region.audit_persistence || {};
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Operational status";
    ctx.target.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Rollout band</dt><dd>" +
      ctx.escapeHtml(region.current_rollout_band || "—") +
      "</dd><dt>Exposure</dt><dd>" +
      ctx.escapeHtml(region.exposure_status || "—") +
      "</dd><dt>Read/write posture</dt><dd>" +
      ctx.escapeHtml(region.read_write_posture || "—") +
      "</dd><dt>Audit health</dt><dd>" +
      ctx.escapeHtml(String(operational.health_state || "—").replace(/_/g, " ")) +
      "</dd><dt>Storage state</dt><dd>" +
      ctx.escapeHtml(String(operational.storage_state || "—").replace(/_/g, " ")) +
      "</dd><dt>Recent records</dt><dd>" +
      ctx.escapeHtml(String(operational.recent_record_count != null ? operational.recent_record_count : "—")) +
      "</dd><dt>Latest persisted at</dt><dd>" +
      ctx.escapeHtml(
        String(
          operational.latest_recorded_at_unix_ms != null
            ? operational.latest_recorded_at_unix_ms
            : "—"
        )
      ) +
      "</dd></dl>";
  };

  renderers.audit_activity_summary = function (ctx) {
    var region = ctx.region || {};
    var activity = region.recent_activity || {};
    var previewRecords = activity.records || [];
    var previewHtml =
      previewRecords.length > 0
        ? '<section class="v2-card" style="margin-top:12px"><h3>Latest records</h3><ul>' +
          previewRecords
            .slice(0, 5)
            .map(function (record) {
              return (
                "<li><strong>" +
                ctx.escapeHtml(record.event_type || "event") +
                "</strong> · " +
                ctx.escapeHtml(String(record.recorded_at_unix_ms != null ? record.recorded_at_unix_ms : "—")) +
                " · <code>" +
                ctx.escapeHtml(record.focus_subject || "") +
                "</code></li>"
              );
            })
            .join("") +
          "</ul></section>"
        : "";
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Audit activity";
    ctx.target.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Rollout band</dt><dd>" +
      ctx.escapeHtml(region.current_rollout_band || "—") +
      "</dd><dt>Exposure</dt><dd>" +
      ctx.escapeHtml(region.exposure_status || "—") +
      "</dd><dt>Read/write posture</dt><dd>" +
      ctx.escapeHtml(region.read_write_posture || "—") +
      "</dd><dt>Activity state</dt><dd>" +
      ctx.escapeHtml(String(activity.activity_state || "—").replace(/_/g, " ")) +
      "</dd><dt>Recent records</dt><dd>" +
      ctx.escapeHtml(String(activity.recent_record_count != null ? activity.recent_record_count : "—")) +
      "</dd><dt>Latest recorded at</dt><dd>" +
      ctx.escapeHtml(
        String(
          activity.latest_recorded_at_unix_ms != null
            ? activity.latest_recorded_at_unix_ms
            : "—"
        )
      ) +
      "</dd></dl>" +
      previewHtml;
  };

  renderers.profile_basics_write_form = function (ctx) {
    var region = ctx.region || {};
    var contract = region.submit_contract || {};
    var initial = contract.initial_values || {};
    var fixed = contract.fixed_request_fields || {};
    var html =
      '<form id="v2-profile-basics-form" class="v2-card" style="max-width:620px">' +
      "<h3>Profile basics</h3>" +
      '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
      ctx.escapeHtml(contract.request_schema || "") +
      "</code></p>" +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_title</label>' +
      '<input name="profile_title" value="' +
      ctx.escapeHtml(initial.profile_title || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_summary</label>' +
      '<textarea name="profile_summary" style="width:100%;min-height:96px;box-sizing:border-box;margin-bottom:10px;padding:6px 8px">' +
      ctx.escapeHtml(initial.profile_summary || "") +
      "</textarea>" +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">contact_email</label>' +
      '<input name="contact_email" value="' +
      ctx.escapeHtml(initial.contact_email || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
      '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">public_website_url</label>' +
      '<input name="public_website_url" value="' +
      ctx.escapeHtml(initial.public_website_url || "") +
      '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
      '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply profile update</button>' +
      "</form>" +
      '<pre id="v2-profile-basics-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
    if (ctx.titleEl) ctx.titleEl.textContent = region.title || "Profile basics";
    ctx.target.innerHTML = html;
    var form = document.getElementById("v2-profile-basics-form");
    var out = document.getElementById("v2-profile-basics-result");
    if (form && out) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var fd = new FormData(form);
        var body = {
          schema: contract.request_schema,
          profile_title: (fd.get("profile_title") || "").toString().trim(),
          profile_summary: (fd.get("profile_summary") || "").toString().trim(),
          contact_email: (fd.get("contact_email") || "").toString().trim(),
          public_website_url: (fd.get("public_website_url") || "").toString().trim(),
        };
        Object.keys(fixed || {}).forEach(function (key) {
          body[key] = fixed[key];
        });
        out.hidden = false;
        out.textContent = "…";
        ctx.postJson(contract.route || "/portal/api/v2/tenant/profile-basics", body).then(function (res) {
          out.textContent = JSON.stringify(res.json, null, 2);
          var lastShellRequest = ctx.getLastShellRequest && ctx.getLastShellRequest();
          if (lastShellRequest) ctx.loadShell(ctx.cloneRequestWithoutChrome(lastShellRequest));
        });
      });
    }
  };

  renderers.__fallback = function (ctx) {
    ctx.target.innerHTML = '<pre class="v2-json-panel">' + ctx.escapeHtml(JSON.stringify(ctx.region || {}, null, 2)) + "</pre>";
  };

  window.PortalShellInspectorRenderer = {
    render: function (ctx) {
      var region = ctx.region || {};
      var kind = region.kind || "empty";
      var renderer = renderers[kind];
      if (typeof renderer !== "function") {
        throw new Error("No inspector renderer for kind: " + kind);
      }
      renderer(ctx);
    },
  };
})();
