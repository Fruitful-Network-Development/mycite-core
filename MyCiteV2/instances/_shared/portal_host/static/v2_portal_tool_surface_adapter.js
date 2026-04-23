/**
 * Shared tool-surface adapter for one-shell renderers.
 * Normalizes direct-query request building plus common loading/error/empty
 * wrapper states so generic and specialized tool paths stay aligned.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function collectWarnings(region, surfacePayload) {
    var warnings = [];
    [
      asList(region && region.warnings),
      asList(surfacePayload && surfacePayload.warnings),
      asList(asObject(surfacePayload && surfacePayload.workspace).warnings),
      asList(asObject(surfacePayload && surfacePayload.source_evidence).warnings),
      asList(asObject(region && region.interface_body).warnings),
    ].forEach(function (items) {
      items.forEach(function (item) {
        var token = asText(item);
        if (token && warnings.indexOf(token) === -1) warnings.push(token);
      });
    });
    return warnings;
  }

  function resolveReadiness(region, surfacePayload) {
    var candidates = [
      asObject(surfacePayload && surfacePayload.readiness),
      asObject(asObject(surfacePayload && surfacePayload.source_evidence).readiness),
      asObject(asObject(surfacePayload && surfacePayload.workspace).readiness),
      asObject(asObject(region && region.interface_body).readiness),
    ];
    for (var index = 0; index < candidates.length; index += 1) {
      var readiness = candidates[index];
      if (asText(readiness.state) || asText(readiness.message)) {
        return readiness;
      }
    }
    return {};
  }

  function resolveToolId(region, surfacePayload) {
    return (
      asText(surfacePayload && surfacePayload.tool_id) ||
      asText(asObject(surfacePayload && surfacePayload.tool_state).tool_id) ||
      asText(asObject(asObject(surfacePayload && surfacePayload.source_evidence).tool_spec).tool_id) ||
      asText(region && region.tool_id)
    );
  }

  function resolveRegionFamilyContract(region) {
    return asObject(region && region.family_contract);
  }

  function resolveRegionFamily(region) {
    return asText(resolveRegionFamilyContract(region).family);
  }

  function resolveSurfacePayloadKind(region, surfacePayload) {
    var familyContract = resolveRegionFamilyContract(region);
    return asText(familyContract.surface_payload_kind) || asText(surfacePayload && surfacePayload.kind);
  }

  function resolveRegionSurfaceId(region, surfacePayload) {
    var familyContract = resolveRegionFamilyContract(region);
    return (
      asText(familyContract.surface_id) ||
      asText(surfacePayload && surfacePayload.surface_id) ||
      asText(region && region.surface_id)
    );
  }

  function resolveDirectivePanelMode(region) {
    var family = resolveRegionFamily(region);
    var kind = asText(region && region.kind);
    var compact = asObject(region && region.state_directive_compact);
    var hasCompactStateDirective = Object.keys(compact).length > 0;

    if (family === "directive_panel") {
      if (hasCompactStateDirective) return "state_directive_compact";
      if (kind === "focus_selection_panel") return "focus_selection_panel";
      return "sections_panel";
    }
    if (hasCompactStateDirective) return "state_directive_compact";
    if (kind === "focus_selection_panel") return "focus_selection_panel";
    return "sections_panel";
  }

  function resolveReflectiveWorkspaceModuleSpec(region, surfacePayload) {
    var family = resolveRegionFamily(region);
    var surfaceId = resolveRegionSurfaceId(region, surfacePayload);
    var payloadKind = resolveSurfacePayloadKind(region, surfacePayload);
    var moduleSpecs = {
      "system.root": {
        moduleId: "system_workspace",
        globalName: "PortalSystemWorkspaceRenderer",
        label: "system workspace",
      },
      "network.root": {
        moduleId: "network_workspace",
        globalName: "PortalNetworkWorkspaceRenderer",
        label: "NETWORK workspace",
      },
      "system.tools.aws_csm": {
        moduleId: "aws_workspace",
        globalName: "PortalAwsCsmWorkspaceRenderer",
        label: "AWS-CSM workspace",
      },
    };

    if (family === "reflective_workspace" && moduleSpecs[surfaceId]) {
      return moduleSpecs[surfaceId];
    }
    if (payloadKind === "system_workspace") return moduleSpecs["system.root"];
    if (payloadKind === "network_system_log_workspace") return moduleSpecs["network.root"];
    if (payloadKind === "aws_csm_workspace") return moduleSpecs["system.tools.aws_csm"];
    return {};
  }

  function resolveReflectiveWorkspaceMode(region, surfacePayload) {
    var family = resolveRegionFamily(region);
    var payloadKind = resolveSurfacePayloadKind(region, surfacePayload);
    var moduleSpec = resolveReflectiveWorkspaceModuleSpec(region, surfacePayload);

    if (family === "reflective_workspace") {
      if (moduleSpec.moduleId) return "registered_workspace";
      if (payloadKind === "workbench_ui_surface") return "workbench_ui_surface";
      if (payloadKind === "tool_secondary_evidence") return "secondary_evidence";
      return "generic_surface";
    }
    if (moduleSpec.moduleId) return "registered_workspace";
    if (payloadKind === "workbench_ui_surface") return "workbench_ui_surface";
    if (payloadKind === "tool_secondary_evidence") return "secondary_evidence";
    return "generic_surface";
  }

  function hasGenericContent(surfacePayload) {
    return (
      asList(surfacePayload && surfacePayload.cards).length > 0 ||
      asList(surfacePayload && surfacePayload.sections).length > 0 ||
      asList(surfacePayload && surfacePayload.notes).length > 0
    );
  }

  function resolveSurfaceState(options) {
    var opts = options || {};
    var region = asObject(opts.region);
    var surfacePayload = asObject(opts.surfacePayload);
    var readiness = resolveReadiness(region, surfacePayload);
    var warnings = collectWarnings(region, surfacePayload);
    var state = "ready";
    if (opts.unsupported) {
      state = "unsupported";
    } else if (surfacePayload.loading === true || region.loading === true || asText(readiness.state) === "loading") {
      state = "loading";
    } else if (
      surfacePayload.error === true ||
      region.error === true ||
      asText(surfacePayload.error_message) ||
      asText(region.error_message) ||
      asText(readiness.state) === "error"
    ) {
      state = "error";
    } else if (opts.hasContent === false) {
      state = "empty";
    }
    return {
      state: state,
      title: asText(opts.title) || asText(region.title) || asText(surfacePayload.title) || "Surface",
      message:
        asText(opts.message) ||
        asText(surfacePayload.error_message) ||
        asText(region.error_message) ||
        asText(readiness.message) ||
        asText(surfacePayload.empty_text) ||
        asText(region.summary),
      warnings: warnings,
      readiness: readiness,
      toolId: resolveToolId(region, surfacePayload),
    };
  }

  function renderReadinessCard(readiness) {
    if (!asText(readiness.state) && !asText(readiness.message)) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Readiness</h3><dl class="v2-surface-dl">' +
      "<dt>state</dt><dd><strong>" +
      escapeHtml(asText(readiness.state) || "pending") +
      "</strong>" +
      (asText(readiness.message) ? "<br />" + escapeHtml(asText(readiness.message)) : "") +
      "</dd></dl></section>"
    );
  }

  function renderWarningsCard(warnings) {
    if (!warnings.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
      warnings
        .map(function (warning) {
          return "<li>" + escapeHtml(warning) + "</li>";
        })
        .join("") +
      "</ul></section>"
    );
  }

  function renderStateHtml(meta) {
    var message = meta.message;
    if (!message) {
      if (meta.state === "loading") message = "Content is still loading.";
      else if (meta.state === "error") message = "This surface reported an error.";
      else if (meta.state === "unsupported") message = "This surface is not supported by the current renderer set.";
      else message = "No content is available for this surface yet.";
    }
    return (
      '<section class="v2-card"><h3>' +
      escapeHtml(meta.title || "Surface") +
      "</h3><p>" +
      escapeHtml(message) +
      "</p>" +
      (meta.toolId
        ? '<p><small>tool: ' + escapeHtml(meta.toolId) + "</small></p>"
        : "") +
      renderReadinessCard(meta.readiness || {}) +
      renderWarningsCard(meta.warnings || []) +
      "</section>"
    );
  }

  function renderWrappedSurface(target, meta, contentHtml) {
    if (!target) return false;
    if (!meta || meta.state !== "ready") {
      target.innerHTML = renderStateHtml(meta || { state: "unsupported", title: "Surface", message: "" });
      return false;
    }
    target.innerHTML = String(contentHtml || "") + renderReadinessCard(meta.readiness || {}) + renderWarningsCard(meta.warnings || []);
    return true;
  }

  function buildDirectSurfaceRequest(ctx, options) {
    var opts = options || {};
    var envelope = (ctx && ctx.getEnvelope && ctx.getEnvelope()) || {};
    var filterMap = asObject(opts.filterMap);
    var activeFilters = asObject(opts.activeFilters);
    var query = {};

    Object.keys(asObject(opts.baseQuery)).forEach(function (key) {
      var token = asText(asObject(opts.baseQuery)[key]);
      if (token) query[key] = token;
    });

    Object.keys(activeFilters).forEach(function (key) {
      var queryKey = asText(filterMap[key]);
      if (!queryKey) return;
      var token = asText(activeFilters[key]);
      if (token) query[queryKey] = token;
    });

    Object.keys(asObject(opts.overrides)).forEach(function (key) {
      var value = asObject(opts.overrides)[key];
      if (value == null || value === "") {
        delete query[key];
      } else {
        query[key] = String(value);
      }
    });

    return {
      schema: "mycite.v2.portal.shell.request.v1",
      requested_surface_id: asText(envelope.surface_id) || asText(opts.defaultSurfaceId) || "system.root",
      portal_scope: envelope.portal_scope || { scope_id: "fnd", capabilities: [] },
      surface_query: query,
    };
  }

  function buildAwsProfileRows(profile) {
    var raw = asObject(profile && profile.raw);
    var identity = asObject(raw.identity);
    var workflow = asObject(raw.workflow);
    var verification = asObject(raw.verification);
    var provider = asObject(raw.provider);
    var smtp = asObject(raw.smtp);
    var inbound = asObject(raw.inbound);
    return [
      { label: "Send-as", value: identity.send_as_email || profile.send_as_email || "—" },
      { label: "User", value: identity.single_user_email || profile.user_email || "—" },
      { label: "Role", value: identity.role || profile.role || "—" },
      { label: "Workflow", value: workflow.lifecycle_state || profile.workflow_state || "—" },
      { label: "Verification", value: verification.portal_state || verification.status || profile.verification_state || "—" },
      { label: "Provider", value: provider.gmail_send_as_status || provider.aws_ses_identity_status || profile.provider_state || "—" },
      { label: "Forward Target", value: smtp.forward_to_email || profile.forward_target || "—" },
      { label: "Inbound", value: inbound.receive_state || profile.inbound_state || "—" },
    ];
  }

  function buildAwsNewsletterRows(newsletter) {
    return [
      { label: "List", value: (newsletter && newsletter.list_address) || "—" },
      { label: "Author", value: (newsletter && newsletter.author_address) || "—" },
      { label: "Delivery", value: (newsletter && newsletter.delivery_mode) || "—" },
      { label: "Contacts", value: String((newsletter && newsletter.contact_count) || 0) },
      { label: "Subscribed", value: String((newsletter && newsletter.subscribed_count) || 0) },
      { label: "Dispatches", value: String((newsletter && newsletter.dispatch_count) || 0) },
      { label: "Last Dispatch", value: (newsletter && newsletter.last_dispatch_id) || "—" },
      { label: "Last Inbound", value: (newsletter && newsletter.last_inbound_status) || "—" },
    ];
  }

  window.PortalToolSurfaceAdapter = {
    buildAwsNewsletterRows: buildAwsNewsletterRows,
    buildAwsProfileRows: buildAwsProfileRows,
    buildDirectSurfaceRequest: buildDirectSurfaceRequest,
    collectWarnings: collectWarnings,
    hasGenericContent: hasGenericContent,
    resolveDirectivePanelMode: resolveDirectivePanelMode,
    resolveReflectiveWorkspaceMode: resolveReflectiveWorkspaceMode,
    resolveReflectiveWorkspaceModuleSpec: resolveReflectiveWorkspaceModuleSpec,
    resolveRegionFamily: resolveRegionFamily,
    resolveRegionFamilyContract: resolveRegionFamilyContract,
    resolveRegionSurfaceId: resolveRegionSurfaceId,
    resolveSurfacePayloadKind: resolveSurfacePayloadKind,
    renderStateHtml: renderStateHtml,
    renderWrappedSurface: renderWrappedSurface,
    resolveReadiness: resolveReadiness,
    resolveToolId: resolveToolId,
    resolveSurfaceState: resolveSurfaceState,
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("tool_surface_adapter");
  }
})();
