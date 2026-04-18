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

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function prettifyKey(value) {
    return asText(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, function (match) {
        return match.toUpperCase();
      });
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

  function buildActionRequest(ctx, workspace, surfacePayload, actionKind, actionPayload) {
    var envelope = (ctx && ctx.getEnvelope && ctx.getEnvelope()) || {};
    var contract = asObject(surfacePayload && surfacePayload.action_contract);
    var directRequest = buildSurfaceRequest(ctx, workspace, {});
    return {
      schema: asText(contract.request_schema),
      portal_scope: envelope.portal_scope || directRequest.portal_scope || { scope_id: "fnd", capabilities: [] },
      shell_state: envelope.shell_state || undefined,
      surface_query: directRequest.surface_query || { view: "domains" },
      action_kind: actionKind,
      action_payload: actionPayload || {},
    };
  }

  function submitAction(ctx, workspace, surfacePayload, actionKind, actionPayload) {
    var contract = asObject(surfacePayload && surfacePayload.action_contract);
    var route = asText(contract.route);
    if (!route) return;
    ctx.loadRuntimeView(route, buildActionRequest(ctx, workspace, surfacePayload, actionKind, actionPayload), {
      replaceHistory: true,
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

  function renderKeyValueRows(obj, preferredOrder) {
    var payload = asObject(obj);
    var seen = {};
    var rows = [];
    (preferredOrder || []).forEach(function (key) {
      var value = asText(payload[key]);
      if (!value) return;
      rows.push({ label: prettifyKey(key), value: value });
      seen[key] = true;
    });
    Object.keys(payload).forEach(function (key) {
      if (seen[key]) return;
      var value = asText(payload[key]);
      if (!value) return;
      rows.push({ label: prettifyKey(key), value: value });
    });
    return rows;
  }

  function profileFactRows(profile) {
    return toolSurfaceAdapter().buildAwsProfileRows(profile || {});
  }

  function newsletterRows(newsletter) {
    return toolSurfaceAdapter().buildAwsNewsletterRows(newsletter || {});
  }

  function renderCreateDomainCard(workspace) {
    if (asText(workspace.selected_domain)) return "";
    var defaults = asObject(workspace.create_domain_defaults);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Onboard Domain</h3><p>Create an explicit AWS-CSM domain onboarding record and open its domain view.</p>' +
      '<form data-aws-create-domain-form style="margin-top:12px">' +
      '<label class="v2-formField"><span>Tenant Id</span><input type="text" name="tenant_id" placeholder="cvccboard" value="' +
      escapeHtml(defaults.tenant_id || "") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Domain</span><input type="text" name="domain" placeholder="cvccboard.org" value="' +
      escapeHtml(defaults.domain || "") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Hosted Zone Id</span><input type="text" name="hosted_zone_id" placeholder="Z1234567890" value="' +
      escapeHtml(defaults.hosted_zone_id || "") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Region</span><input type="text" name="region" placeholder="us-east-1" value="' +
      escapeHtml(defaults.region || "us-east-1") +
      '" required /></label>' +
      '<div style="margin-top:12px"><button type="submit" class="ide-sessionAction ide-sessionAction--button">Create Domain Record</button></div>' +
      "</form></section>"
    );
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
                (row.newsletter_configured ? " · newsletter" : "") +
                (row.onboarding_state && row.onboarding_state !== "legacy_inferred"
                  ? " · onboarding " + row.onboarding_state
                  : "")
            ) +
            '</span><span class="aws-csm-profileCard__stats">' +
            "<span>contacts: " +
            escapeHtml(String(row.contact_count || 0)) +
            "</span><span>dispatches: " +
            escapeHtml(String(row.dispatch_count || 0)) +
            "</span><span>state: " +
            escapeHtml(row.onboarding_state || "legacy_inferred") +
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
    if (!rows.length) {
      return '<section class="v2-card" style="margin-top:12px"><h3>User Email Gallery</h3><p>No AWS-CSM user emails are configured for this domain yet.</p></section>';
    }
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

  function renderCreateProfileCard(workspace) {
    var createProfile = asObject(workspace.selected_domain_create_profile);
    var domain = asText(createProfile.domain);
    if (!domain) return "";
    if (!createProfile.enabled) {
      return (
        '<section class="v2-card" style="margin-top:12px"><h3>Add User</h3><p>' +
        escapeHtml(createProfile.disabled_reason || "This domain is not ready for add-user yet.") +
        "</p>" +
        renderInfoRows(
          renderKeyValueRows(createProfile, ["domain", "tenant_id", "region"])
        ) +
        "</section>"
      );
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Add User</h3><p>Create a draft AWS-CSM profile and continue directly into the same onboarding workflow.</p>' +
      renderInfoRows(
        renderKeyValueRows(createProfile, ["domain", "tenant_id", "region", "default_role"])
      ) +
      '<form data-aws-create-profile-form style="margin-top:12px">' +
      '<input type="hidden" name="domain" value="' +
      escapeHtml(domain) +
      '" />' +
      '<input type="hidden" name="role" value="' +
      escapeHtml(createProfile.default_role || "operator") +
      '" />' +
      '<label class="v2-formField"><span>Mailbox Local Part</span><input type="text" name="mailbox_local_part" placeholder="alex" required /></label>' +
      '<label class="v2-formField"><span>Single User Email</span><input type="email" name="single_user_email" placeholder="alex@example.com" required /></label>' +
      '<label class="v2-formField"><span>Forwarded Operator Inbox</span><input type="email" name="operator_inbox_target" placeholder="leave blank to use the single user email" /></label>' +
      '<div style="margin-top:12px"><button type="submit" class="ide-sessionAction ide-sessionAction--button">Create Draft User</button></div>' +
      "</form></section>"
    );
  }

  function renderOnboardingActions(onboarding) {
    var actions = asList(onboarding && onboarding.actions);
    if (!actions.length) return "";
    return (
      '<div class="aws-csm-flowForm__actions">' +
      actions
        .map(function (action) {
          var disabled = action.enabled === false;
          return (
            '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-action-kind="' +
            escapeHtml(action.kind || "") +
            '"' +
            (disabled ? ' disabled="disabled"' : "") +
            (action.disabled_reason ? ' title="' + escapeHtml(action.disabled_reason) + '"' : "") +
            ">" +
            escapeHtml(action.label || action.kind || "Run") +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderDomainActions(onboarding) {
    var actions = asList(onboarding && onboarding.actions);
    if (!actions.length) return "";
    return (
      '<div class="aws-csm-flowForm__actions">' +
      actions
        .map(function (action) {
          var disabled = action.enabled === false;
          return (
            '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-domain-action-kind="' +
            escapeHtml(action.kind || "") +
            '"' +
            (disabled ? ' disabled="disabled"' : "") +
            (action.disabled_reason ? ' title="' + escapeHtml(action.disabled_reason) + '"' : "") +
            ">" +
            escapeHtml(action.label || action.kind || "Run") +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderDomainOnboardingCard(workspace) {
    var onboarding = asObject(workspace.selected_domain_onboarding);
    var domain = asText(workspace.selected_domain);
    if (!domain) return "";
    if (!asText(onboarding.domain)) {
      return (
        '<section class="v2-card" style="margin-top:12px"><h3>Domain Onboarding</h3><p>No explicit domain onboarding record exists for this domain yet.</p></section>'
      );
    }
    var blockers = asList(onboarding.blockers);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Domain Onboarding</h3><p>' +
      escapeHtml(onboarding.readiness_summary || "AWS-backed domain onboarding state.") +
      "</p>" +
      renderInfoRows(
        renderKeyValueRows(onboarding, [
          "tenant_id",
          "domain",
          "region",
          "hosted_zone_id",
          "readiness_state",
          "last_checked_at",
          "registrar_nameservers",
          "hosted_zone_nameservers",
          "nameserver_match",
          "mx_record_present",
          "mx_record_values",
          "ses_identity_exists",
          "ses_identity_status",
          "dkim_status",
          "dkim_token_count",
          "dkim_records_present",
          "receipt_rule_status",
          "receipt_rule_name",
          "receipt_rule_recipient",
          "receipt_rule_bucket",
          "receipt_rule_prefix",
        ])
      ) +
      (blockers.length
        ? '<div style="margin-top:12px"><h4>Blockers</h4><ul>' +
          blockers
            .map(function (blocker) {
              return "<li>" + escapeHtml(blocker) + "</li>";
            })
            .join("") +
          "</ul></div>"
        : "") +
      renderDomainActions(onboarding) +
      "</section>"
    );
  }

  function renderHandoffCard(onboarding) {
    var handoff = asObject(onboarding && onboarding.handoff);
    if (!asText(handoff.send_as_email)) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Handoff</h3><p>Split-secret Gmail handoff keeps the SMTP password out of stored profile state and instruction emails.</p>' +
      renderInfoRows(
        renderKeyValueRows(handoff, [
          "send_as_email",
          "single_user_email",
          "operator_inbox_target",
          "forward_target",
          "smtp_host",
          "smtp_port",
          "smtp_username",
          "secret_name",
          "secret_state",
          "email_received_at",
          "verified_at",
        ])
      ) +
      "</section>"
    );
  }

  function renderActionResult(surfacePayload) {
    var result = asObject(surfacePayload && surfacePayload.action_result);
    if (!asText(result.action_kind) && !asText(result.message)) return "";
    var detailRows = renderKeyValueRows(result.details, [
      "profile_id",
      "tenant_id",
      "tenant_scope_id",
      "domain",
      "hosted_zone_id",
      "readiness_state",
      "send_as_email",
      "single_user_email",
      "operator_inbox_target",
      "sent_to",
      "message_id",
      "secret_name",
      "state",
    ]);
    var handoffDispatchRows = renderKeyValueRows(result.handoff_dispatch, [
      "sent_to",
      "send_as_email",
      "username",
      "smtp_host",
      "smtp_port",
      "message_id",
      "state",
    ]);
    var secretRows = renderKeyValueRows(result.ephemeral_secret, [
      "send_as_email",
      "username",
      "password",
      "smtp_host",
      "smtp_port",
      "secret_name",
      "state",
    ]);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Latest Action</h3><p><strong>' +
      escapeHtml(prettifyKey(result.status || "accepted")) +
      "</strong> · " +
      escapeHtml(prettifyKey(result.action_kind || "action")) +
      "</p><p>" +
      escapeHtml(result.message || "") +
      "</p>" +
      (detailRows.length ? renderInfoRows(detailRows) : "") +
      (handoffDispatchRows.length
        ? '<div style="margin-top:12px"><h4>Handoff Dispatch</h4>' + renderInfoRows(handoffDispatchRows) + "</div>"
        : "") +
      (secretRows.length
        ? '<div style="margin-top:12px"><h4>Ephemeral SMTP Secret</h4><p>This password is shown only in this response and is not persisted to profile JSON.</p>' +
          renderInfoRows(secretRows) +
          "</div>"
        : "") +
      "</section>"
    );
  }

  function renderOnboardingSection(workspace) {
    var selected = workspace.selected_profile || null;
    var rows = workspace.mailbox_rows || [];
    var onboarding = asObject(workspace.selected_profile_onboarding);
    var domainCard = renderDomainOnboardingCard(workspace);
    if (!selected && !rows.length && !domainCard) return "";
    if (selected) {
      return (
        domainCard +
        '<section class="v2-card" style="margin-top:12px"><h3>Mailbox Onboarding</h3><p>' +
        escapeHtml(selected.title || selected.profile_id || "") +
        "</p>" +
        renderInfoRows(profileFactRows(selected)) +
        renderInfoRows(
          renderKeyValueRows(onboarding, [
            "workflow_state",
            "handoff_status",
            "verification_state",
            "email_received_at",
            "verified_at",
            "latest_message_reference",
            "provider_state",
            "inbound_state",
          ])
        ) +
        renderOnboardingActions(onboarding) +
        "</section>" +
        renderHandoffCard(onboarding)
      );
    }
    if (!rows.length) {
      return (
        domainCard +
        '<section class="v2-card" style="margin-top:12px"><h3>Mailbox Onboarding</h3><p>No AWS-CSM user emails are configured for this domain yet.</p></section>'
      );
    }
    return (
      domainCard +
      '<section class="v2-card" style="margin-top:12px"><h3>Mailbox Onboarding</h3><div class="aws-csm-profileGrid aws-csm-profileGrid--compact">' +
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

  function renderSelectedDomain(workspace, surfacePayload) {
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
      renderActionResult(surfacePayload) +
      (showUsers ? renderCreateProfileCard(workspace) + renderMailboxGallery(workspace) : "") +
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

  function bindCreateProfileForm(target, ctx, workspace, surfacePayload) {
    var form = target.querySelector("[data-aws-create-profile-form]");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var payload = {};
      Array.prototype.forEach.call(form.querySelectorAll("input, textarea, select"), function (field) {
        if (!field.name) return;
        var value = field.value;
        if (value == null || value === "") return;
        payload[field.name] = value;
      });
      submitAction(ctx, workspace, surfacePayload, "create_profile", payload);
    });
  }

  function bindCreateDomainForm(target, ctx, workspace, surfacePayload) {
    var form = target.querySelector("[data-aws-create-domain-form]");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var payload = {};
      Array.prototype.forEach.call(form.querySelectorAll("input, textarea, select"), function (field) {
        if (!field.name) return;
        var value = field.value;
        if (value == null || value === "") return;
        payload[field.name] = value;
      });
      submitAction(ctx, workspace, surfacePayload, "create_domain", payload);
    });
  }

  function bindOnboardingActions(target, ctx, workspace, surfacePayload) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-aws-action-kind]"), function (button) {
      if (button.disabled) return;
      button.addEventListener("click", function () {
        var kind = button.getAttribute("data-aws-action-kind") || "";
        var selected = asObject(workspace.selected_profile);
        submitAction(ctx, workspace, surfacePayload, kind, {
          profile_id: selected.profile_id || "",
        });
      });
    });
  }

  function bindDomainActions(target, ctx, workspace, surfacePayload) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-aws-domain-action-kind]"), function (button) {
      if (button.disabled) return;
      button.addEventListener("click", function () {
        var kind = button.getAttribute("data-aws-domain-action-kind") || "";
        submitAction(ctx, workspace, surfacePayload, kind, {
          domain: workspace.selected_domain || "",
        });
      });
    });
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
          renderCreateDomainCard(workspace) +
          renderDomainGallery(workspace) +
          renderSelectedDomain(workspace, surfacePayload) +
          renderNotes(surfacePayload.notes || [])
      );

      bindCreateDomainForm(target, ctx, workspace, surfacePayload);
      bindCreateProfileForm(target, ctx, workspace, surfacePayload);
      bindOnboardingActions(target, ctx, workspace, surfacePayload);
      bindDomainActions(target, ctx, workspace, surfacePayload);

      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-domain]"), function (button) {
        button.addEventListener("click", function () {
          var domain = button.getAttribute("data-aws-domain") || "";
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { domain: domain, profile: null, section: null }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-aws-profile]"), function (button) {
        button.addEventListener("click", function () {
          var profile = button.getAttribute("data-aws-profile") || "";
          ctx.loadShell(buildSurfaceRequest(ctx, workspace, { profile: profile, section: null }));
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
      var domainOnboarding = asObject(workspace.selected_domain_onboarding);
      var profile = workspace.selected_profile || null;
      var newsletter = workspace.selected_newsletter || null;
      var actionResult = asObject(surfacePayload && surfacePayload.action_result);
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
          : asText(domainOnboarding.domain)
            ? '<section class="v2-card" style="margin-top:12px"><h3>Selected Domain</h3>' +
              renderInfoRows(
                renderKeyValueRows(domainOnboarding, [
                  "tenant_id",
                  "domain",
                  "region",
                  "hosted_zone_id",
                  "readiness_state",
                  "ses_identity_status",
                  "dkim_status",
                  "receipt_rule_status",
                ])
              ) +
              "</section>"
          : newsletter
            ? '<section class="v2-card" style="margin-top:12px"><h3>Selected Newsletter</h3>' +
              renderInfoRows(newsletterRows(newsletter)) +
              "</section>"
            : '<section class="v2-card" style="margin-top:12px"><h3>Selection</h3><p>Select a domain or user email to inspect AWS-CSM state without leaving the unified tool surface.</p></section>') +
        (asText(actionResult.message)
          ? '<section class="v2-card" style="margin-top:12px"><h3>Latest Action</h3>' +
            renderInfoRows(
              renderKeyValueRows(
                {
                  action_kind: actionResult.action_kind,
                  status: actionResult.status,
                  message: actionResult.message,
                },
                ["action_kind", "status", "message"]
              )
            ) +
            "</section>"
          : "") +
        ((profile && profile.raw) || (newsletter && newsletter.raw) || asObject(workspace.selected_domain_record).raw
          ? '<section class="v2-card" style="margin-top:12px"><h3>Raw Payload</h3><pre class="v2-networkInspector__json">' +
            escapeHtml(compactJson((profile && profile.raw) || asObject(workspace.selected_domain_record).raw || (newsletter && newsletter.raw) || {})) +
            "</pre></section>"
          : "") +
        "</div>"
      );
    },
  };
})();
