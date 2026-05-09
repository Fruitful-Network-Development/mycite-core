/**
 * Dedicated renderer for the PayPal-CSM tool surface.
 * Provides domain profile status, credential readiness, and tenant summary views.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function resolveModuleRegistry() {
    return window.__MYCITE_V2_SHELL_MODULE_REGISTRY || {};
  }

  // -----------------------------------------------------------------------
  // Workspace renderer — reflective_workspace region
  // -----------------------------------------------------------------------

  var PortalPaypalCsmWorkspaceRenderer = {
    render: function render(ctx, target, surfacePayload) {
      if (!target) return;
      var payload = asObject(surfacePayload);
      var domainProfile = asObject(payload.domain_profile);
      var tenantSummary = asObject(payload.tenant_summary);
      var credentialsReady = payload.credentials_ready === true;

      var domain = asText(domainProfile.domain);
      var environment = asText(domainProfile.environment);
      var brandName = asText(domainProfile.brand_name);
      var tenantRef = asText(domainProfile.tenant_ref);
      var profileConfigured = domainProfile.configured === true;

      var html = '<div class="paypal-csm-workspace">';

      // Domain profile status card
      html += '<section class="paypal-csm-workspace__section">';
      html += '<h3 class="paypal-csm-workspace__heading">Domain Profile</h3>';
      if (domain) {
        html += '<table class="paypal-csm-workspace__table">';
        html += '<tr><th>Domain</th><td>' + escapeHtml(domain) + '</td></tr>';
        html += '<tr><th>Environment</th><td>' + escapeHtml(environment) + '</td></tr>';
        html += '<tr><th>Brand name</th><td>' + escapeHtml(brandName) + '</td></tr>';
        html += '<tr><th>Tenant ref</th><td>' + escapeHtml(tenantRef) + '</td></tr>';
        html += '<tr><th>Configured</th><td>' + (profileConfigured ? '<span class="status-ok">yes</span>' : '<span class="status-warn">no</span>') + '</td></tr>';
        html += '</table>';
      } else {
        html += '<p class="paypal-csm-workspace__empty">No domain profile loaded for this surface.</p>';
      }
      html += '</section>';

      // Credential readiness
      html += '<section class="paypal-csm-workspace__section">';
      html += '<h3 class="paypal-csm-workspace__heading">Credentials</h3>';
      html += '<p>Resolved: <strong>' + (credentialsReady ? '<span class="status-ok">yes</span>' : '<span class="status-warn">no</span>') + '</strong></p>';
      html += '<p class="paypal-csm-workspace__note">Credential values are never displayed here. Set <code>PAYPAL_CLIENT_ID</code> and <code>PAYPAL_CLIENT_SECRET</code> env vars on the host.</p>';
      html += '</section>';

      // Tenant config summary
      if (tenantSummary.environment) {
        html += '<section class="paypal-csm-workspace__section">';
        html += '<h3 class="paypal-csm-workspace__heading">Tenant Config</h3>';
        html += '<table class="paypal-csm-workspace__table">';
        html += '<tr><th>Environment</th><td>' + escapeHtml(asText(tenantSummary.environment)) + '</td></tr>';
        if (tenantSummary.brand_name) {
          html += '<tr><th>Brand name</th><td>' + escapeHtml(asText(tenantSummary.brand_name)) + '</td></tr>';
        }
        html += '</table>';
        html += '</section>';
      }

      html += '</div>';
      target.innerHTML = html;
    },
  };

  // -----------------------------------------------------------------------
  // Interface Panel renderer — presentation_surface / interface panel region
  // -----------------------------------------------------------------------

  var PortalPaypalCsmInterfacePanelRenderer = {
    render: function render(ctx, target, surfacePayload) {
      if (!target) return;
      var payload = asObject(surfacePayload);
      var sections = asList(payload.sections);
      var domainProfile = asObject(payload.domain_profile);

      var html = '<div class="paypal-csm-interfacePanel">';
      html += '<h3 class="paypal-csm-interfacePanel__heading">PayPal-CSM</h3>';

      if (sections.length > 0) {
        for (var si = 0; si < sections.length; si++) {
          var section = asObject(sections[si]);
          var rows = asList(section.rows);
          html += '<section class="paypal-csm-interfacePanel__section">';
          if (section.title) {
            html += '<h4 class="paypal-csm-interfacePanel__section-title">' + escapeHtml(asText(section.title)) + '</h4>';
          }
          if (rows.length > 0) {
            html += '<dl class="paypal-csm-interfacePanel__dl">';
            for (var ri = 0; ri < rows.length; ri++) {
              var row = asObject(rows[ri]);
              html += '<dt>' + escapeHtml(asText(row.label)) + '</dt>';
              html += '<dd>' + escapeHtml(asText(row.value));
              if (row.detail) {
                html += '<span class="paypal-csm-interfacePanel__detail"> — ' + escapeHtml(asText(row.detail)) + '</span>';
              }
              html += '</dd>';
            }
            html += '</dl>';
          }
          html += '</section>';
        }
      } else if (domainProfile.domain) {
        // Fallback: render domain profile fields directly if sections not provided
        html += '<section class="paypal-csm-interfacePanel__section">';
        html += '<dl class="paypal-csm-interfacePanel__dl">';
        html += '<dt>Domain</dt><dd>' + escapeHtml(asText(domainProfile.domain)) + '</dd>';
        html += '<dt>Environment</dt><dd>' + escapeHtml(asText(domainProfile.environment)) + '</dd>';
        html += '<dt>Configured</dt><dd>' + (domainProfile.configured ? 'yes' : 'no') + '</dd>';
        html += '</dl>';
        html += '</section>';
      } else {
        html += '<p class="paypal-csm-interfacePanel__empty">No profile data available.</p>';
      }

      html += '</div>';
      target.innerHTML = html;
    },
  };

  // -----------------------------------------------------------------------
  // Module registration
  // -----------------------------------------------------------------------

  window.PortalPaypalCsmWorkspaceRenderer = PortalPaypalCsmWorkspaceRenderer;
  window.PortalPaypalCsmInterfacePanelRenderer = PortalPaypalCsmInterfacePanelRenderer;

  var registry = resolveModuleRegistry();
  if (typeof registry.register === "function") {
    registry.register("paypal_workspace");
  } else if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("paypal_workspace");
  }
})();
