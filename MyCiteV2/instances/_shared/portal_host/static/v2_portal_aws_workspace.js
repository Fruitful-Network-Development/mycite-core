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

  function asDisplayText(value) {
    if (Array.isArray(value)) {
      return value
        .map(function (item) {
          return typeof item === "object" ? "" : asText(item);
        })
        .filter(Boolean)
        .join(", ");
    }
    if (value && typeof value === "object") return "";
    return asText(value);
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

  function interfaceTabHost() {
    return window.__MYCITE_V2_INTERFACE_TAB_HOST || {};
  }

  function normalizeInspectorTabs(tabs, fallbackTabs, defaultTabId) {
    var host = interfaceTabHost();
    if (host && typeof host.normalizeTabs === "function") {
      return host.normalizeTabs(tabs, fallbackTabs, defaultTabId);
    }
    return Array.isArray(fallbackTabs) ? fallbackTabs.slice() : [];
  }

  function activeInspectorTabId(tabs, fallbackId) {
    var host = interfaceTabHost();
    if (host && typeof host.activeTabId === "function") {
      return host.activeTabId(tabs, fallbackId);
    }
    return (tabs && tabs[0] && tabs[0].id) || fallbackId || "";
  }

  function renderInspectorTabs(tabs) {
    var host = interfaceTabHost();
    if (host && typeof host.renderTabs === "function") {
      return host.renderTabs(tabs);
    }
    return "";
  }

  function renderInspectorTabPanel(tabId, activeTabId, contentHtml, className) {
    var host = interfaceTabHost();
    if (host && typeof host.renderTabPanel === "function") {
      return host.renderTabPanel(tabId, activeTabId, contentHtml, className);
    }
    return String(contentHtml || "");
  }

  function bindInspectorTabs(target) {
    var host = interfaceTabHost();
    if (host && typeof host.bindTabs === "function") {
      host.bindTabs(target);
    }
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
      var value = asDisplayText(payload[key]);
      if (!value) return;
      rows.push({ label: prettifyKey(key), value: value });
      seen[key] = true;
    });
    Object.keys(payload).forEach(function (key) {
      if (seen[key]) return;
      var value = asDisplayText(payload[key]);
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
            "<span>onboarding: " +
            escapeHtml(row.onboarding_state || "—") +
            "</span><span>workflow: " +
            escapeHtml(row.workflow_state || "—") +
            "</span><span>verification: " +
            escapeHtml(row.verification_state || "—") +
            "</span><span>provider: " +
            escapeHtml(row.provider_state || "—") +
            "</span><span>correction: " +
            escapeHtml(row.handoff_correction_status || "—") +
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
          "mailbox_count",
          "handoff_correction_required_count",
          "handoff_correction_completed_count",
          "current_handoff_template_version",
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
      '<section class="v2-card" style="margin-top:12px"><h3>Handoff</h3><p>Portal handoff sends a minimal SMTP credential set while keeping the password out of stored profile JSON.</p>' +
      renderInfoRows(
        renderKeyValueRows(handoff, [
          "send_as_email",
          "single_user_email",
          "operator_inbox_target",
          "forward_target",
          "handoff_email_sent_to",
          "handoff_email_message_id",
          "handoff_email_sent_at",
          "handoff_template_version",
          "current_handoff_template_version",
          "handoff_correction_required",
          "handoff_correction_status",
          "handoff_correction_sent_to",
          "handoff_correction_message_id",
          "handoff_correction_sent_at",
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

  function renderHandoffProviderOptions(selectedValue) {
    var selected = asText(selectedValue).toLowerCase();
    return ["gmail", "outlook", "yahoo", "proofpoint", "generic_manual"]
      .map(function (value) {
        return (
          '<option value="' +
          escapeHtml(value) +
          '"' +
          (selected === value ? ' selected="selected"' : "") +
          ">" +
          escapeHtml(prettifyKey(value)) +
          "</option>"
        );
      })
      .join("");
  }

  function renderProfileEditorCard(profile) {
    var raw = asObject(profile && profile.raw);
    var identity = asObject(raw.identity);
    var smtp = asObject(raw.smtp);
    var provider = asObject(raw.provider);
    var currentForward = smtp.forward_to_email || identity.operator_inbox_target || identity.single_user_email || "";
    var currentProvider =
      provider.handoff_provider || identity.handoff_provider || smtp.handoff_provider || "generic_manual";
    if (!asText(profile && profile.profile_id)) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>User Configuration</h3><p>Update the mailbox alias, linked personal email, or forwarding target for the selected AWS-CSM user.</p>' +
      '<form data-aws-update-profile-form style="margin-top:12px">' +
      '<label class="v2-formField"><span>Mailbox Local Part</span><input type="text" name="mailbox_local_part" value="' +
      escapeHtml(identity.mailbox_local_part || profile.mailbox_local_part || "") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Single User Email</span><input type="email" name="single_user_email" value="' +
      escapeHtml(identity.single_user_email || profile.user_email || "") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Forwarded Operator Inbox</span><input type="email" name="operator_inbox_target" value="' +
      escapeHtml(currentForward) +
      '" required /></label>' +
      '<label class="v2-formField"><span>Role</span><input type="text" name="role" value="' +
      escapeHtml(identity.role || profile.role || "operator") +
      '" required /></label>' +
      '<label class="v2-formField"><span>Handoff Provider</span><select name="handoff_provider">' +
      renderHandoffProviderOptions(currentProvider) +
      "</select></label>" +
      '<div class="aws-csm-flowForm__actions" style="margin-top:12px">' +
      '<button type="submit" class="ide-sessionAction ide-sessionAction--button">Save User Configuration</button>' +
      '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-delete-profile>Delete User</button>' +
      "</div>" +
      "</form></section>"
    );
  }

  function renderRawPayloadCard(workspace) {
    var profile = workspace.selected_profile || null;
    var newsletter = workspace.selected_newsletter || null;
    var domainRaw = asObject(workspace.selected_domain_record).raw;
    var payload = (profile && profile.raw) || domainRaw || (newsletter && newsletter.raw) || null;
    if (!payload) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Raw Payload</h3><pre class="v2-networkInspector__json">' +
      escapeHtml(compactJson(payload)) +
      "</pre></section>"
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
      "corrected_profiles",
      "correction_count",
      "sent_to",
      "message_id",
      "template_version",
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
      "template_version",
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
            "onboarding_state",
            "onboarding_summary",
            "workflow_state",
            "handoff_status",
            "handoff_template_version",
            "handoff_correction_status",
            "handoff_correction_required",
            "handoff_correction_sent_at",
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
            escapeHtml(row.onboarding_state || "unknown") +
            "</span></div>" +
            renderInfoRows([
              { label: "Onboarding", value: row.onboarding_summary || row.onboarding_state || "—" },
              { label: "Correction", value: row.handoff_correction_status || "—" },
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
    return (
      '<section class="v2-card aws-csm-overviewIntro" style="margin-top:12px"><h3>' +
      escapeHtml(domain) +
      "</h3><p>Unified AWS-CSM domain gallery for mailbox management and onboarding posture.</p>" +
      '<div class="aws-csm-flowForm__actions"><button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-domain-clear>Back to Domain Gallery</button></div>' +
      "</section>" +
      renderActionResult(surfacePayload) +
      renderCreateProfileCard(workspace) +
      renderMailboxGallery(workspace) +
      renderOnboardingSection(workspace)
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

  function renderToolPostureCard(tool) {
    return (
      '<section class="v2-card"><h3>Tool Posture</h3>' +
      renderInfoRows([
        { label: "Configured", value: tool.configured ? "yes" : "no" },
        { label: "Enabled", value: tool.enabled ? "yes" : "no" },
        { label: "Operational", value: tool.operational ? "yes" : "no" },
        { label: "Missing Capability", value: (tool.missing_capabilities || []).join(", ") || "none" },
      ]) +
      "</section>"
    );
  }

  function renderInspectorSelectionCard(workspace) {
    if (asText(workspace.selected_domain)) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Selection</h3><p>Select a domain to organize mailbox management and onboarding from the same interface panel.</p></section>' +
      renderDomainGallery(workspace)
    );
  }

  function renderInspectorDomainTab(workspace, surfacePayload) {
    var profile = workspace.selected_profile || null;
    var domainOnboarding = asObject(workspace.selected_domain_onboarding);
    var selectedDomain = asText(workspace.selected_domain);
    if (!selectedDomain) {
      return renderInspectorSelectionCard(workspace);
    }
    return (
      renderActionResult(surfacePayload) +
      '<section class="v2-card" style="margin-top:12px"><h3>Selected Domain</h3>' +
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
      "</section>" +
      renderMailboxGallery(workspace) +
      (profile
        ? '<section class="v2-card" style="margin-top:12px"><h3>Selected User Email</h3>' +
          renderInfoRows(profileFactRows(profile)) +
          "</section>" +
          renderProfileEditorCard(profile)
        : '<section class="v2-card" style="margin-top:12px"><h3>User Management</h3><p>Select a user email from the gallery to edit or delete that staged mailbox.</p></section>') +
      renderRawPayloadCard(workspace)
    );
  }

  function renderInspectorOnboardingTab(workspace, surfacePayload) {
    var selectedDomain = asText(workspace.selected_domain);
    if (!selectedDomain) {
      return renderInspectorSelectionCard(workspace);
    }
    return (
      renderActionResult(surfacePayload) +
      renderCreateProfileCard(workspace) +
      renderOnboardingSection(workspace)
    );
  }

  function hasWorkspaceContent(workspace, surfacePayload) {
    if (asList(surfacePayload && surfacePayload.cards).length) return true;
    if (asList(workspace && workspace.domain_rows).length) return true;
    if (asText(workspace && workspace.selected_domain)) return true;
    if (asText(asObject(surfacePayload && surfacePayload.action_result).message)) return true;
    return false;
  }

  function collectFormPayload(form) {
    var payload = {};
    Array.prototype.forEach.call(form.querySelectorAll("input, textarea, select"), function (field) {
      if (!field.name) return;
      var value = field.value;
      if (value == null || value === "") return;
      payload[field.name] = value;
    });
    return payload;
  }

  function bindDelegatedWorkspaceEvents(target) {
    if (!target || target.__awsCsmDelegatedBindings) return;
    target.__awsCsmDelegatedBindings = true;
    target.addEventListener("submit", function (event) {
      var form = event.target && event.target.closest
        ? event.target.closest("[data-aws-create-profile-form], [data-aws-create-domain-form], [data-aws-update-profile-form]")
        : null;
      var state = target.__awsCsmRenderState || {};
      if (!form || !target.contains(form) || !state.ctx) return;
      event.preventDefault();
      if (form.hasAttribute("data-aws-create-profile-form")) {
        submitAction(
          state.ctx,
          state.workspace,
          state.surfacePayload,
          "create_profile",
          collectFormPayload(form)
        );
        return;
      }
      if (form.hasAttribute("data-aws-update-profile-form")) {
        submitAction(
          state.ctx,
          state.workspace,
          state.surfacePayload,
          "update_profile",
          collectFormPayload(form)
        );
        return;
      }
      if (form.hasAttribute("data-aws-create-domain-form")) {
        submitAction(
          state.ctx,
          state.workspace,
          state.surfacePayload,
          "create_domain",
          collectFormPayload(form)
        );
      }
    });
    target.addEventListener("click", function (event) {
      var button = event.target && event.target.closest
        ? event.target.closest(
            "[data-aws-action-kind], [data-aws-domain-action-kind], [data-aws-domain], [data-aws-profile], [data-aws-domain-clear], [data-aws-delete-profile]"
          )
        : null;
      var state = target.__awsCsmRenderState || {};
      if (!button || !target.contains(button) || !state.ctx || button.disabled) return;
      if (button.hasAttribute("data-aws-action-kind")) {
        submitAction(state.ctx, state.workspace, state.surfacePayload, button.getAttribute("data-aws-action-kind") || "", {
          profile_id: asObject(state.workspace.selected_profile).profile_id || "",
        });
        return;
      }
      if (button.hasAttribute("data-aws-domain-action-kind")) {
        submitAction(
          state.ctx,
          state.workspace,
          state.surfacePayload,
          button.getAttribute("data-aws-domain-action-kind") || "",
          { domain: state.workspace.selected_domain || "" }
        );
        return;
      }
      if (button.hasAttribute("data-aws-domain")) {
        state.ctx.loadShell(
          buildSurfaceRequest(state.ctx, state.workspace, {
            domain: button.getAttribute("data-aws-domain") || "",
            profile: null,
            section: null,
          })
        );
        return;
      }
      if (button.hasAttribute("data-aws-profile")) {
        state.ctx.loadShell(
          buildSurfaceRequest(state.ctx, state.workspace, {
            profile: button.getAttribute("data-aws-profile") || "",
            section: null,
          })
        );
        return;
      }
      if (button.hasAttribute("data-aws-domain-clear")) {
        state.ctx.loadShell(
          buildSurfaceRequest(state.ctx, state.workspace, { domain: null, profile: null, section: null })
        );
        return;
      }
      if (button.hasAttribute("data-aws-delete-profile")) {
        submitAction(
          state.ctx,
          state.workspace,
          state.surfacePayload,
          "delete_profile",
          { profile_id: asObject(state.workspace.selected_profile).profile_id || "" }
        );
      }
    });
  }

  window.PortalAwsCsmWorkspaceRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      var contentReady = hasWorkspaceContent(workspace, surfacePayload);
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "AWS-CSM",
          hasContent: contentReady,
          message: contentReady
            ? ""
            : "No AWS-CSM domains or actions are available in this workspace state yet.",
        }),
        renderCards(surfacePayload.cards || []) +
          renderCreateDomainCard(workspace) +
          renderDomainGallery(workspace) +
          renderSelectedDomain(workspace, surfacePayload) +
          renderNotes(surfacePayload.notes || [])
      );
      target.__awsCsmRenderState = {
        ctx: ctx,
        workspace: workspace,
        surfacePayload: surfacePayload,
      };
      bindDelegatedWorkspaceEvents(target);
    },
  };

  window.PortalAwsCsmInspectorRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var tool = (surfacePayload && surfacePayload.tool) || {};
      var actionResult = asObject(surfacePayload && surfacePayload.action_result);
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      var inspectorHasContent = !!(
        asList(workspace.domain_rows).length ||
        asText(workspace.selected_domain) ||
        workspace.selected_profile ||
        workspace.selected_newsletter ||
        asText(actionResult.message)
      );
      var tabs = normalizeInspectorTabs(
        [{ id: "onboarding", label: "Onboarding", active: true }, { id: "domain", label: "Domain", active: true }],
        [{ id: "onboarding", label: "Onboarding", active: true }, { id: "domain", label: "Domain", active: true }],
        "onboarding"
      );
      var activeTabId = activeInspectorTabId(tabs, "onboarding");
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "AWS-CSM Interface Panel",
          hasContent: inspectorHasContent,
          message: inspectorHasContent
            ? ""
            : "Select a domain or mailbox profile to inspect AWS-CSM tool posture.",
        }),
        '<div class="v2-inspector-stack aws-csm-interfacePanel">' +
        renderToolPostureCard(tool) +
        renderInspectorTabs(tabs) +
        '<div class="aws-csm-interfacePanel__body">' +
        renderInspectorTabPanel("onboarding", activeTabId, renderInspectorOnboardingTab(workspace, surfacePayload), "aws-csm-interfacePanel__tabPanel") +
        renderInspectorTabPanel("domain", activeTabId, renderInspectorDomainTab(workspace, surfacePayload), "aws-csm-interfacePanel__tabPanel") +
        "</div></div>"
      );
      target.__awsCsmRenderState = {
        ctx: ctx,
        workspace: workspace,
        surfacePayload: surfacePayload,
      };
      bindDelegatedWorkspaceEvents(target);
      bindInspectorTabs(target);
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("aws_workspace");
  }
})();
