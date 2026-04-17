/**
 * Dedicated renderer for the unified AWS-CSM workbench.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function compactJson(value) {
    if (value == null) return "";
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
  }

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function buildSurfaceRequest(ctx, workspace, overrides) {
    return toolSurfaceAdapter().buildDirectSurfaceRequest(ctx, {
      defaultSurfaceId: "system.tools.aws_csm",
      baseQuery: { view: "domains" },
      activeFilters: (workspace && workspace.active_filters) || {},
      filterMap: {
        domain: "domain",
        profile_id: "profile",
        section: "section",
      },
      overrides: overrides,
    });
  }

  function renderCards(cards) {
    if (!cards || !cards.length) return "";
    return (
      '<div class="v2-card-grid">' +
      cards
        .map(function (card) {
          return (
            '<article class="v2-card"><h3>' +
            escapeHtml(card.label || "") +
            "</h3><p>" +
            escapeHtml(card.value || "—") +
            "</p></article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderInfoRows(rows) {
    if (!rows || !rows.length) return '<p class="ide-controlpanel__empty">No detail is available.</p>';
    return (
      '<dl class="aws-csm-infoGrid">' +
      rows
        .map(function (row) {
          return (
            '<div class="aws-csm-infoRow"><dt>' +
            escapeHtml(row.label || "") +
            '</dt><dd><span>' +
            escapeHtml(row.value || "—") +
            "</span></dd></div>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function profileFactRows(profile) {
    return toolSurfaceAdapter().buildAwsProfileRows(profile || {});
  }

  function newsletterRows(newsletter) {
    return toolSurfaceAdapter().buildAwsNewsletterRows(newsletter || {});
  }

  function renderDomainGallery(workspace) {
    var rows = workspace.domain_rows || [];
    if (!rows.length) {
      return '<section class="v2-card" style="margin-top:12px"><h3>Domain Gallery</h3><p>No AWS-CSM domains are configured in this portal state root.</p></section>';
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Domain Gallery</h3><div class="aws-csm-profileGrid">' +
      rows
        .map(function (row) {
          return (
            '<button type="button" class="aws-csm-profileCard' +
            (row.active ? " is-active" : "") +
            '" data-aws-domain="' +
            escapeHtml(row.domain || "") +
            '">' +
            '<span class="aws-csm-profileCard__title">' +
            escapeHtml(row.label || row.domain || "") +
            '</span><span class="aws-csm-profileCard__meta">' +
            escapeHtml(
              String(row.profile_count || 0) +
                " mailbox" +
                ((row.profile_count || 0) === 1 ? "" : "es") +
                (row.newsletter_configured ? " · newsletter" : "")
            ) +
            '</span><span class="aws-csm-profileCard__stats">' +
            "<span>contacts: " +
            escapeHtml(String(row.contact_count || 0)) +
            "</span><span>dispatches: " +
            escapeHtml(String(row.dispatch_count || 0)) +
            "</span></span></button>"
          );
        })
        .join("") +
      "</div></section>"
    );
  }

  function renderSectionButtons(workspace) {
    var rows = workspace.section_rows || [];
    if (!rows.length) return "";
    return (
      '<div class="aws-csm-flowForm__actions">' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-section-clear>All</button>' +
      rows
        .map(function (row) {
          return (
            '<button type="button" class="ide-sessionAction ide-sessionAction--button' +
            (row.active ? " is-active" : "") +
            '" data-aws-section="' +
            escapeHtml((row.label || "").toLowerCase()) +
            '">' +
            escapeHtml(row.label || "") +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderMailboxGallery(workspace) {
    var rows = workspace.mailbox_rows || [];
    if (!rows.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>User Email Gallery</h3><div class="aws-csm-profileGrid">' +
      rows
        .map(function (row) {
          return (
            '<button type="button" class="aws-csm-profileCard' +
            (row.active ? " is-active" : "") +
            '" data-aws-profile="' +
            escapeHtml(row.profile_id || "") +
            '">' +
            '<span class="aws-csm-profileCard__title">' +
            escapeHtml(row.title || row.profile_id || "") +
            '</span><span class="aws-csm-profileCard__meta">' +
            escapeHtml((row.user_email || "no linked user") + " · " + (row.role || "mailbox")) +
            '</span><span class="aws-csm-profileCard__stats">' +
            "<span>workflow: " +
            escapeHtml(row.workflow_state || "—") +
            "</span><span>verification: " +
            escapeHtml(row.verification_state || "—") +
            "</span><span>provider: " +
            escapeHtml(row.provider_state || "—") +
            "</span><span>inbound: " +
            escapeHtml(row.inbound_state || "—") +
            "</span></span></button>"
          );
        })
        .join("") +
      "</div></section>"
    );
  }

  function renderOnboardingSection(workspace) {
    var selected = workspace.selected_profile || null;
    var rows = workspace.mailbox_rows || [];
    if (!selected && !rows.length) return "";
    if (selected) {
      return (
        '<section class="v2-card" style="margin-top:12px"><h3>Onboarding</h3><p>' +
        escapeHtml(selected.title || selected.profile_id || "") +
        "</p>" +
        renderInfoRows(profileFactRows(selected)) +
        "</section>"
      );
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Onboarding</h3><div class="aws-csm-profileGrid aws-csm-profileGrid--compact">' +
      rows
        .map(function (row) {
          return (
            '<article class="aws-csm-domainSection aws-csm-domainSection--compact"><div class="aws-csm-domainSection__header"><span class="aws-csm-domainSection__title">' +
            escapeHtml(row.title || row.profile_id || "") +
            '</span><span class="aws-csm-domainSection__count">' +
            escapeHtml(row.workflow_state || "unknown") +
            "</span></div>" +
            renderInfoRows([
              { label: "Verification", value: row.verification_state || "—" },
              { label: "Provider", value: row.provider_state || "—" },
              { label: "Inbound", value: row.inbound_state || "—" },
            ]) +
            "</article>"
          );
        })
        .join("") +
      "</div></section>"
    );
  }

  function renderNewsletterSection(workspace) {
    var newsletter = workspace.selected_newsletter || null;
    if (!newsletter) {
      return '<section class="v2-card" style="margin-top:12px"><h3>Newsletter</h3><p>No newsletter profile is configured for this domain.</p></section>';
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Newsletter</h3><article class="aws-csm-newsletterCard">' +
      '<span class="aws-csm-newsletterCard__title">' +
      escapeHtml(newsletter.domain || "") +
      '</span><span class="aws-csm-newsletterCard__meta">' +
      escapeHtml((newsletter.list_address || "—") + " · " + (newsletter.author_address || "no author")) +
      '</span><span class="aws-csm-newsletterCard__stats">' +
      newsletterRows(newsletter)
        .map(function (row) {
          return "<span>" + escapeHtml((row.label || "") + ": " + (row.value || "—")) + "</span>";
        })
        .join("") +
      "</span></article></section>"
    );
  }

  function renderSelectedDomain(workspace) {
    var domain = workspace.selected_domain || "";
    if (!domain) return "";
    var section = (workspace.active_filters && workspace.active_filters.section) || "";
    var showUsers = !section || section === "users";
    var showOnboarding = !section || section === "onboarding";
    var showNewsletter = !section || section === "newsletter";
    return (
      '<section class="v2-card aws-csm-overviewIntro" style="margin-top:12px"><h3>' +
      escapeHtml(domain) +
      "</h3><p>Unified AWS-CSM domain gallery for mailbox state, onboarding posture, and newsletter readiness.</p>" +
      renderSectionButtons(workspace) +
      '<div class="aws-csm-flowForm__actions"><button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-domain-clear>Back to Domain Gallery</button></div>' +
      "</section>" +
      (showUsers ? renderMailboxGallery(workspace) : "") +
      (showOnboarding ? renderOnboardingSection(workspace) : "") +
      (showNewsletter ? renderNewsletterSection(workspace) : "")
    );
  }

  function renderNotes(notes) {
    if (!notes || !notes.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Notes</h3><ul>' +
      notes
        .map(function (note) {
          return "<li>" + escapeHtml(note) + "</li>";
        })
        .join("") +
      "</ul></section>"
    );
  }

  window.PortalAwsCsmWorkspaceRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "AWS-CSM",
          hasContent: true,
        }),
        renderCards(surfacePayload.cards || []) +
          renderDomainGallery(workspace) +
          renderSelectedDomain(workspace) +
          renderNotes(surfacePayload.notes || [])
      );

      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-domain]"), function (button) {
        button.addEventListener("click", function () {
          var domain = button.getAttribute("data-aws-domain") || "";
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { domain: domain, profile: null, section: null }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-profile]"), function (button) {
        button.addEventListener("click", function () {
          var profile = button.getAttribute("data-aws-profile") || "";
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { profile: profile }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-section]"), function (button) {
        button.addEventListener("click", function () {
          var label = (button.getAttribute("data-aws-section") || "").toLowerCase();
          var section = label === "users" || label === "onboarding" || label === "newsletter" ? label : "";
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { section: section }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-section-clear]"), function (button) {
        button.addEventListener("click", function () {
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { section: null }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-domain-clear]"), function (button) {
        button.addEventListener("click", function () {
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { domain: null, profile: null, section: null }));
        });
      });
    },
  };

  window.PortalAwsCsmInspectorRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var tool = (surfacePayload && surfacePayload.tool) || {};
      var profile = workspace.selected_profile || null;
      var newsletter = workspace.selected_newsletter || null;
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "AWS-CSM Interface Panel",
          hasContent: true,
        }),
        '<div class="v2-inspector-stack"><section class="v2-card"><h3>Tool Posture</h3>' +
        renderInfoRows([
          { label: "Configured", value: tool.configured ? "yes" : "no" },
          { label: "Enabled", value: tool.enabled ? "yes" : "no" },
          { label: "Operational", value: tool.operational ? "yes" : "no" },
          { label: "Missing Capability", value: (tool.missing_capabilities || []).join(", ") || "none" },
        ]) +
        "</section>" +
        (profile
          ? '<section class="v2-card" style="margin-top:12px"><h3>Selected User Email</h3>' +
            renderInfoRows(profileFactRows(profile)) +
            "</section>"
          : newsletter
            ? '<section class="v2-card" style="margin-top:12px"><h3>Selected Newsletter</h3>' +
              renderInfoRows(newsletterRows(newsletter)) +
              "</section>"
            : '<section class="v2-card" style="margin-top:12px"><h3>Selection</h3><p>Select a domain or user email to inspect AWS-CSM state without leaving the unified tool surface.</p></section>') +
        ((profile && profile.raw) || (newsletter && newsletter.raw)
          ? '<section class="v2-card" style="margin-top:12px"><h3>Raw Payload</h3><pre class="v2-networkInspector__json">' +
            escapeHtml(compactJson((profile && profile.raw) || (newsletter && newsletter.raw) || {})) +
            "</pre></section>"
          : "") +
        "</div>"
      );
    },
  };
})();
