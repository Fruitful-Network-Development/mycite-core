/**
 * FND-CSM workspace renderer — grantee service management with four tabs:
 * Email, Analytics, Newsletter, PayPal.
 *
 * Interface panel: tabbed_panel with sections tagged by tab_id.
 * Reflective workspace: grantee overview card.
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

  function dispatchAction(ctx, surfacePayload, actionKind, actionPayload) {
    var contract = asObject(surfacePayload && surfacePayload.request_contract);
    var route = asText(contract.action_route || contract.route);
    if (!route) return;
    var envelope = (ctx && ctx.getEnvelope && ctx.getEnvelope()) || {};
    var toolState = asObject(surfacePayload && surfacePayload.tool_state);
    ctx.loadRuntimeView(route, {
      schema: asText(contract.action_schema),
      portal_scope: envelope.portal_scope || { scope_id: "fnd", capabilities: [] },
      shell_state: envelope.shell_state || undefined,
      action_kind: actionKind,
      action_payload: actionPayload || {},
      tool_state: toolState,
    }, { replaceHistory: true });
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
  // Shared rendering helpers
  // ---------------------------------------------------------------------------

  function renderInfoRows(rows) {
    if (!rows || !rows.length) return "<p>—</p>";
    return (
      '<dl class="fnd-csm-infoGrid">' +
      rows.map(function (r) {
        return (
          '<div class="fnd-csm-infoRow"><dt>' + escapeHtml(r.label || "") +
          '</dt><dd>' + escapeHtml(r.value || "—") +
          (r.detail ? '<small>' + escapeHtml(r.detail) + '</small>' : '') +
          '</dd></div>'
        );
      }).join("") +
      "</dl>"
    );
  }

  function renderSection(title, bodyHtml) {
    return (
      '<section class="fnd-csm-section"><h4 class="fnd-csm-section__title">' +
      escapeHtml(title) + '</h4>' + bodyHtml + '</section>'
    );
  }

  // ---------------------------------------------------------------------------
  // Email tab
  // ---------------------------------------------------------------------------

  function renderEmailTab(surfacePayload) {
    var email = asObject(surfacePayload.email);
    var profiles = asList(email.profiles);
    if (!profiles.length) {
      return renderSection("Email", "<p>No mailbox profiles found for the selected domain.</p>");
    }
    return profiles.map(function (p) {
      return renderSection(
        "Mailbox: " + asText(p.send_as || p.mailbox),
        renderInfoRows([
          { label: "send-as", value: p.send_as },
          { label: "role", value: p.role },
          { label: "lifecycle", value: p.lifecycle || "—" },
          { label: "inbound", value: p.inbound || "—" },
        ])
      );
    }).join("");
  }

  // ---------------------------------------------------------------------------
  // Analytics tab
  // ---------------------------------------------------------------------------

  function renderAnalyticsTab(surfacePayload) {
    var analytics = asObject(surfacePayload.analytics);
    var summary = asObject(analytics.summary);
    var recent = asList(analytics.recent_events);
    var summaryRows = [
      { label: "page views", value: String(asInt(summary.page_view)) },
      { label: "form submits", value: String(asInt(summary.form_submit)) },
      { label: "ops probes", value: String(asInt(summary.ops_probe)) },
      { label: "other events", value: String(asInt(summary.other)) },
    ];
    var html = renderSection("Event Summary (last 90 days)", renderInfoRows(summaryRows));
    if (recent.length) {
      html += renderSection(
        "Recent Events",
        '<table class="fnd-csm-table"><thead><tr><th>Type</th><th>Path</th><th>Time</th></tr></thead><tbody>' +
        recent.slice(0, 10).map(function (e) {
          return (
            '<tr><td>' + escapeHtml(e.event_type || "—") +
            '</td><td>' + escapeHtml(e.path || "—") +
            '</td><td>' + escapeHtml(e.timestamp || "—") + '</td></tr>'
          );
        }).join("") +
        '</tbody></table>'
      );
    }
    return html;
  }

  // ---------------------------------------------------------------------------
  // Newsletter tab
  // ---------------------------------------------------------------------------

  function renderNewsletterTab(surfacePayload, ctx) {
    var nl = asObject(surfacePayload.newsletter);
    var senderOptions = asList(nl.sender_options);
    var currentSender = asText(nl.current_sender);
    var domain = asText(nl.domain || surfacePayload.selected_domain);
    var contactRows = asList(nl.contact_rows);

    // Sender assignment
    var senderHtml =
      '<form class="fnd-csm-senderForm" data-fnd-csm-sender-form>' +
      '<label class="fnd-csm-label">Newsletter sender<br>' +
      '<select name="sender_address" class="fnd-csm-select">' +
      senderOptions.map(function (u) {
        var sel = u === currentSender ? ' selected' : '';
        return '<option value="' + escapeHtml(u) + '"' + sel + '>' + escapeHtml(u) + '</option>';
      }).join("") +
      '</select></label>' +
      '<button type="submit" class="fnd-csm-btn">Assign Sender</button>' +
      '</form>';
    var senderSection = renderSection("Sender Assignment", senderHtml);

    // Contact list table
    var tableHtml;
    if (!contactRows.length) {
      tableHtml = "<p>No contacts found.</p>";
    } else {
      tableHtml =
        '<table class="fnd-csm-table"><thead><tr><th>Email</th><th>Status</th><th>Source</th><th>Last sent</th><th></th></tr></thead><tbody>' +
        contactRows.map(function (c) {
          var subscribed = c.subscribed !== false;
          var statusLabel = subscribed ? "subscribed" : "unsubscribed";
          var toggleLabel = subscribed ? "Unsubscribe" : "Subscribe";
          return (
            '<tr><td>' + escapeHtml(c.email) +
            '</td><td>' + statusLabel +
            '</td><td>' + escapeHtml(c.source || "—") +
            '</td><td>' + escapeHtml(c.last_sent || "—") +
            '</td><td><button class="fnd-csm-btn fnd-csm-btn--small"' +
            ' data-fnd-csm-toggle-contact data-email="' + escapeHtml(c.email) +
            '" data-subscribed="' + (subscribed ? "1" : "0") +
            '" data-domain="' + escapeHtml(domain) +
            '">' + toggleLabel + '</button></td></tr>'
          );
        }).join("") +
        '</tbody></table>';
    }
    var contactSection = renderSection(
      "Contact List (" + asInt(nl.subscribed_count) + " subscribed, " + asInt(nl.unsubscribed_count) + " unsubscribed)",
      tableHtml
    );

    return senderSection + contactSection;
  }

  function bindNewsletterTab(target, surfacePayload, ctx) {
    var domain = asText(surfacePayload.selected_domain);
    // Sender form
    var form = target.querySelector("[data-fnd-csm-sender-form]");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var sel = form.querySelector("select[name=sender_address]");
        var sender = sel ? asText(sel.value) : "";
        if (!sender) return;
        dispatchAction(ctx, surfacePayload, "assign_newsletter_sender", {
          domain: domain, sender_address: sender,
        });
      });
    }
    // Contact toggle buttons
    var toggleBtns = target.querySelectorAll("[data-fnd-csm-toggle-contact]");
    toggleBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var email = asText(btn.getAttribute("data-email"));
        var currentlySubscribed = btn.getAttribute("data-subscribed") === "1";
        dispatchAction(ctx, surfacePayload, "update_contact_subscription", {
          domain: asText(btn.getAttribute("data-domain")),
          email: email,
          subscribed: !currentlySubscribed,
        });
      });
    });
  }

  // ---------------------------------------------------------------------------
  // PayPal tab
  // ---------------------------------------------------------------------------

  function renderPaypalTab(surfacePayload, ctx) {
    var paypal = asObject(surfacePayload.paypal);
    var orders = asList(paypal.orders);
    var webhookUrl = asText(paypal.webhook_url);
    var granteemsn = asText(paypal.grantee_msn || (asObject(surfacePayload.selected_grantee).msn_id));

    var webhookHtml =
      '<form class="fnd-csm-webhookForm" data-fnd-csm-webhook-form>' +
      '<label class="fnd-csm-label">PayPal Webhook URL<br>' +
      '<input type="url" name="webhook_url" class="fnd-csm-input" placeholder="https://..." value="' +
      escapeHtml(webhookUrl) + '" /></label>' +
      '<input type="hidden" name="msn_id" value="' + escapeHtml(granteemsn) + '">' +
      '<button type="submit" class="fnd-csm-btn">Save Webhook</button>' +
      '</form>';
    var webhookSection = renderSection("Webhook Configuration", webhookHtml);

    var ordersHtml;
    if (!orders.length) {
      ordersHtml = "<p>No recent orders found.</p>";
    } else {
      ordersHtml =
        '<table class="fnd-csm-table"><thead><tr><th>Event</th><th>Amount</th><th>Status</th><th>Domain</th></tr></thead><tbody>' +
        orders.slice(0, 10).map(function (o) {
          return (
            '<tr><td>' + escapeHtml(o.event || "—") +
            '</td><td>' + escapeHtml((o.amount || "—") + " " + (o.currency || "")) +
            '</td><td>' + escapeHtml(o.status || "—") +
            '</td><td>' + escapeHtml(o.domain || "—") + '</td></tr>'
          );
        }).join("") +
        '</tbody></table>';
    }
    var ordersSection = renderSection("Recent Orders (" + orders.length + ")", ordersHtml);

    return webhookSection + ordersSection;
  }

  function bindPaypalTab(target, surfacePayload, ctx) {
    var form = target.querySelector("[data-fnd-csm-webhook-form]");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var urlInput = form.querySelector("input[name=webhook_url]");
        var msnInput = form.querySelector("input[name=msn_id]");
        dispatchAction(ctx, surfacePayload, "save_paypal_webhook", {
          msn_id: msnInput ? asText(msnInput.value) : "",
          webhook_url: urlInput ? asText(urlInput.value) : "",
        });
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Interface panel renderer
  // ---------------------------------------------------------------------------

  var FndCsmInterfacePanelRenderer = {
    render: function (ctx, target, surfacePayload) {
      var payload = asObject(surfacePayload);
      var grantee = asObject(payload.selected_grantee);
      var domain = asText(payload.selected_domain);

      // Build tabs
      var TABS = [
        { id: "email", label: "Email" },
        { id: "analytics", label: "Analytics" },
        { id: "newsletter", label: "Newsletter" },
        { id: "paypal", label: "PayPal" },
      ];
      var host = tabHost();
      var tabs = (host.normalizeTabs) ? host.normalizeTabs(TABS, TABS, asText((payload.tool_state || {}).active_tab) || "email") : TABS;
      var activeTab = (host.activeTabId) ? host.activeTabId(tabs, "email") : "email";

      var tabBarHtml = (host.renderTabs) ? host.renderTabs(tabs) : "";

      function tabPanel(tabId, contentHtml) {
        return (host.renderTabPanel)
          ? host.renderTabPanel(tabId, activeTab, contentHtml, "fnd-csm-tabPanel")
          : '<div class="fnd-csm-tabPanel' + (tabId === activeTab ? ' is-active' : '') + '">' + contentHtml + '</div>';
      }

      var emailHtml = renderEmailTab(payload);
      var analyticsHtml = renderAnalyticsTab(payload);
      var newsletterHtml = renderNewsletterTab(payload, ctx);
      var paypalHtml = renderPaypalTab(payload, ctx);

      var headerHtml =
        '<header class="fnd-csm-header">' +
        '<span class="fnd-csm-grantee">' + escapeHtml(grantee.label || "—") + '</span>' +
        (domain ? '<span class="fnd-csm-domain"> · ' + escapeHtml(domain) + '</span>' : '') +
        '</header>';

      target.innerHTML =
        headerHtml +
        '<nav class="fnd-csm-tabs">' + tabBarHtml + '</nav>' +
        tabPanel("email", emailHtml) +
        tabPanel("analytics", analyticsHtml) +
        tabPanel("newsletter", newsletterHtml) +
        tabPanel("paypal", paypalHtml);

      // Bind tab switching
      if (host.bindTabs) {
        host.bindTabs(target);
      }

      // Bind tab selection → tool_state persistence
      target.querySelectorAll("[data-tab-id]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var tabId = asText(btn.getAttribute("data-tab-id"));
          dispatchSurface(ctx, payload, { active_tab: tabId });
        });
      });

      // Bind newsletter and PayPal tab interactions
      bindNewsletterTab(target, payload, ctx);
      bindPaypalTab(target, payload, ctx);
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
