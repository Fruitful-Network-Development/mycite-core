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

  renderers.cts_gis_summary = function (ctx) {
    var region = ctx.region || {};
    var titleEl = ctx.titleEl;
    var content = ctx.target;
    var escapeHtml = ctx.escapeHtml;
    var envelope = (ctx.getEnvelope && ctx.getEnvelope()) || {};
    var mapSurface = envelope.surface_payload || {};
    var mapAttentionProfile = mapSurface.attention_profile || {};
    var mapMediationState = mapSurface.mediation_state || {};
    var mapRenderSetSummary = mapSurface.render_set_summary || {};
    var mapSelectedDocument = mapSurface.selected_document || {};
    var mapSelectedFeature = (mapSurface.map_projection || {}).selected_feature || {};
    var mapSelectedRow = mapSurface.selected_row || {};
    var mapDiagnosticSummary = mapSurface.diagnostic_summary || {};
    var mapLensState = mapSurface.lens_state || {};
    var mapWarnings = ((mapSurface.warnings || region.warnings) || [])
      .map(function (warning) {
        return "<li>" + escapeHtml(String(warning)) + "</li>";
      })
      .join("");
    if (titleEl) titleEl.textContent = region.title || "CTS-GIS";
    content.innerHTML =
      '<dl class="v2-surface-dl">' +
      "<dt>Document</dt><dd><code>" +
      escapeHtml(mapSelectedDocument.document_name || "—") +
      "</code></dd>" +
      "<dt>Relative path</dt><dd><code>" +
      escapeHtml(mapSelectedDocument.relative_path || "—") +
      "</code></dd>" +
      "<dt>Attention</dt><dd>" +
      escapeHtml(mapAttentionProfile.profile_label || mapAttentionProfile.node_id || "—") +
      "</dd>" +
      "<dt>Intention</dt><dd>" +
      escapeHtml(String(mapRenderSetSummary.render_mode || mapMediationState.intention_token || "—").replace(/_/g, " ")) +
      "</dd>" +
      "<dt>Feature count</dt><dd>" +
      escapeHtml(String(mapDiagnosticSummary.render_feature_count != null ? mapDiagnosticSummary.render_feature_count : mapDiagnosticSummary.feature_count != null ? mapDiagnosticSummary.feature_count : "0")) +
      "</dd>" +
      "<dt>Selected feature</dt><dd><code>" +
      escapeHtml(mapSelectedFeature.feature_id || "—") +
      "</code></dd>" +
      "<dt>Selected row</dt><dd><code>" +
      escapeHtml(mapSelectedRow.datum_address || "—") +
      "</code></dd>" +
      "<dt>Overlay mode</dt><dd>" +
      escapeHtml(mapLensState.overlay_mode || "—") +
      "</dd></dl>" +
      '<section class="v2-card" style="margin-top:12px"><h3>Selected row</h3><pre class="v2-json-panel">' +
      escapeHtml(JSON.stringify(mapSelectedRow.raw || mapSelectedRow || {}, null, 2)) +
      "</pre></section>" +
      (mapWarnings
        ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
          mapWarnings +
          "</ul></section>"
        : "");
  };

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
})();
