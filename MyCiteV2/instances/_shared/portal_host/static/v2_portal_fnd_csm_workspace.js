/**
 * FND-CSM workspace renderer — grantee service management with four tabs:
 * Email, Analytics, Newsletter, PayPal.
 *
 * Interface panel: tabbed_interface_panel with component_frames (canonical model).
 * Reflective workspace: grantee overview card with grantee/domain selectors.
 */
(function () {
  "use strict";

  function escapeHtml(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asText(v) { return String(v == null ? "" : v).trim(); }
  function asObject(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : {}; }
  function asList(v) { return Array.isArray(v) ? v.slice() : []; }
  function asInt(v) { var n = parseInt(v, 10); return isNaN(n) ? 0 : n; }

  function tabHost() { return window.__MYCITE_V2_INTERFACE_TAB_HOST || {}; }
  function surfaceAdapter() { return window.PortalToolSurfaceAdapter || {}; }

  // ---------------------------------------------------------------------------
  // Request helpers
  // ---------------------------------------------------------------------------

  function buildSurfaceRequest(ctx, overrides) {
    return surfaceAdapter().buildDirectSurfaceRequest(ctx, {
      defaultSurfaceId: "system.tools.fnd_csm",
      baseQuery: {},
      activeFilters: {},
      filterMap: {},
      overrides: overrides || {},
    });
  }

  function dispatchSurface(ctx, surfacePayload, toolStateOverrides) {
    var contract = asObject(surfacePayload && surfacePayload.request_contract);
    var route = asText(contract.route);
    if (!route) return;
    var envelope = (ctx && ctx.getEnvelope && ctx.getEnvelope()) || {};
    var base = asObject(surfacePayload && surfacePayload.tool_state);
    var toolState = Object.assign({}, base, toolStateOverrides || {});
    ctx.loadRuntimeView(route, {
      schema: asText(contract.schema),
      portal_scope: envelope.portal_scope || { scope_id: "fnd", capabilities: [] },
      shell_state: envelope.shell_state || undefined,
      tool_state: toolState,
    }, { replaceHistory: true });
  }

  // ---------------------------------------------------------------------------
  // Interface panel renderer — canonical component frame model
  // ---------------------------------------------------------------------------

  var FndCsmInterfacePanelRenderer = {
    render: function (ctx, target, surfacePayload) {
      var region = asObject(ctx && ctx.region);
      var payload = asObject(surfacePayload);
      var host = tabHost();

      var regionTabs = asList(region.tabs);
      var defaultTabId = asText(region.default_tab_id) || "email";
      var componentFrames = asList(region.component_frames);

      var normalizedTabs = (host.normalizeTabs) ? host.normalizeTabs(regionTabs, regionTabs, defaultTabId) : regionTabs;
      var activeTab = (host.activeTabId) ? host.activeTabId(normalizedTabs, defaultTabId) : defaultTabId;
      var tabBarHtml = (host.renderTabs) ? host.renderTabs(normalizedTabs) : "";

      var renderFrameList = (typeof window.__MYCITE_V2_RENDER_COMPONENT_FRAME_LIST === "function")
        ? window.__MYCITE_V2_RENDER_COMPONENT_FRAME_LIST
        : function () { return ""; };

      // Map component_group frames to their tab id via frame_id convention: fnd_csm.tab.{tabId}
      var frameByTabId = {};
      componentFrames.forEach(function (frame) {
        var fid = asText(asObject(frame).frame_id);
        var m = fid.match(/^fnd_csm\.tab\.(.+)$/);
        if (m) frameByTabId[m[1]] = frame;
      });

      function tabPanel(tabId) {
        var frame = frameByTabId[tabId] || null;
        var contentHtml = frame ? renderFrameList([frame]) : "";
        return (host.renderTabPanel)
          ? host.renderTabPanel(tabId, activeTab, contentHtml, "fnd-csm-tabPanel")
          : '<div class="fnd-csm-tabPanel' + (tabId === activeTab ? ' is-active' : '') + '">' + contentHtml + '</div>';
      }

      target.innerHTML =
        '<nav class="fnd-csm-tabs">' + tabBarHtml + '</nav>' +
        tabPanel("email") +
        tabPanel("analytics") +
        tabPanel("newsletter") +
        tabPanel("paypal");

      if (host.bindTabs) {
        host.bindTabs(target);
      }

      target.querySelectorAll("[data-tab-id]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          dispatchSurface(ctx, payload, { active_tab: asText(btn.getAttribute("data-tab-id")) });
        });
      });

      if (typeof window.__MYCITE_V2_BIND_COMPONENT_FRAME_ENGAGEMENT === "function") {
        window.__MYCITE_V2_BIND_COMPONENT_FRAME_ENGAGEMENT(target, ctx);
      }
    },
  };

  // ---------------------------------------------------------------------------
  // Reflective workspace renderer (grantee overview)
  // ---------------------------------------------------------------------------

  var FndCsmWorkspaceRenderer = {
    render: function (ctx, target, surfacePayload) {
      var payload = asObject(surfacePayload);
      var grantees = asList(payload.grantees);
      var selectedGrantee = asObject(payload.selected_grantee);
      var selectedDomain = asText(payload.selected_domain);
      var toolState = asObject(payload.tool_state);

      // Grantee selector cards
      var granteeCards = grantees.map(function (g) {
        var isActive = asText(g.msn_id) === asText(selectedGrantee.msn_id);
        var domains = asList(g.domains);
        return (
          '<button class="fnd-csm-granteeCard' + (isActive ? ' is-active' : '') + '"' +
          ' data-fnd-csm-select-grantee data-msn="' + escapeHtml(g.msn_id) + '">' +
          '<strong>' + escapeHtml(g.label) + '</strong>' +
          '<small>' + escapeHtml(g.short_name) + '</small>' +
          (domains.length ? '<span>' + escapeHtml(domains.join(", ")) + '</span>' : '') +
          '</button>'
        );
      }).join("");

      // Domain selector (for multi-domain grantees)
      var domainTabs = "";
      var allDomains = asList(selectedGrantee.domains);
      if (allDomains.length > 1) {
        domainTabs =
          '<div class="fnd-csm-domainTabs">' +
          allDomains.map(function (d) {
            var isActive = d === selectedDomain;
            return (
              '<button class="fnd-csm-domainTab' + (isActive ? ' is-active' : '') + '"' +
              ' data-fnd-csm-select-domain data-domain="' + escapeHtml(d) + '">' +
              escapeHtml(d) + '</button>'
            );
          }).join("") +
          '</div>';
      }

      target.innerHTML =
        '<div class="fnd-csm-workspace">' +
        '<section class="fnd-csm-granteeRow">' + granteeCards + '</section>' +
        domainTabs +
        '</div>';

      // Bind grantee selection
      target.querySelectorAll("[data-fnd-csm-select-grantee]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var msn = asText(btn.getAttribute("data-msn"));
          dispatchSurface(ctx, payload, { selected_grantee_msn: msn, selected_domain: "" });
        });
      });

      // Bind domain selection
      target.querySelectorAll("[data-fnd-csm-select-domain]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var domain = asText(btn.getAttribute("data-domain"));
          dispatchSurface(ctx, payload, { selected_domain: domain });
        });
      });
    },
  };

  // ---------------------------------------------------------------------------
  // Registration
  // ---------------------------------------------------------------------------

  window.PortalFndCsmWorkspaceRenderer = FndCsmWorkspaceRenderer;
  window.PortalFndCsmInterfacePanelRenderer = FndCsmInterfacePanelRenderer;
})();
