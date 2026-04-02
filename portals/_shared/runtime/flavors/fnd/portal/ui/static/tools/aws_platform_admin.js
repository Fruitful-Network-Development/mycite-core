(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});
  var state = {
    selectedProfile: "aws-csm.fnd.dylan",
    latestVerification: null,
    latestStatus: null,
    latestProfile: null,
  };

  function summary(value) {
    var node = qs("#awsp-summary");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function profileView(value) {
    var node = qs("#awsp-profile");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function verificationView(value) {
    var node = qs("#awsp-verification");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function out(value) {
    var node = qs("#awsp-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function linkView(value) {
    var wrap = qs("#awsp-link-wrap");
    var node = qs("#awsp-link");
    if (!wrap || !node) return;
    var token = String(value || "").trim();
    if (!token) {
      wrap.style.display = "none";
      node.href = "#";
      node.textContent = "Open verification link";
      return;
    }
    wrap.style.display = "block";
    node.href = token;
    node.textContent = token;
  }

  function selectedProfile() {
    var node = qs("#awsp-profile-select");
    var token = node ? String(node.value || "").trim() : "";
    return token || state.selectedProfile || "aws-csm.fnd.dylan";
  }

  function setSelectedProfile(value) {
    var token = String(value || "").trim() || "aws-csm.fnd.dylan";
    state.selectedProfile = token;
    var node = qs("#awsp-profile-select");
    if (node && node.value !== token) node.value = token;
  }

  function populateProfiles(profiles) {
    var node = qs("#awsp-profile-select");
    if (!node) return;
    var items = Array.isArray(profiles) ? profiles : [];
    var selected = state.selectedProfile || "aws-csm.fnd.dylan";
    node.innerHTML = items.map(function (item) {
      var token = String(item.profile_id || item.tenant_id || "").trim();
      var label = [
        String(item.domain || "").trim(),
        String(item.send_as_email || token || "").trim(),
        String(item.role || "").trim(),
        String(item.lifecycle_state || "").trim()
      ].filter(Boolean).join(" | ");
      var picked = token === selected ? ' selected="selected"' : "";
      return '<option value="' + token + '"' + picked + ">" + token + " · " + label + "</option>";
    }).join("");
    if (!node.options.length) {
      node.innerHTML = '<option value="aws-csm.fnd.dylan">aws-csm.fnd.dylan</option>';
      node.value = "aws-csm.fnd.dylan";
      selected = "aws-csm.fnd.dylan";
    }
    setSelectedProfile(node.value || selected);
  }

  function compactProfile(payload) {
    var profile = payload && typeof payload.profile === "object" ? payload.profile : {};
    var provider = profile.provider || {};
    var workflow = profile.workflow || {};
    return {
      profile_id: payload.profile_id || "",
      profile_path: payload.profile_path || "",
      send_as_email: payload.send_as_email || "",
      status_labels: {
        provider_ready: String(provider.aws_ses_identity_status || "") === "verified",
        handoff_ready: !!workflow.is_ready_for_user_handoff,
        gmail_complete: !!workflow.is_send_as_confirmed,
      },
      identity: profile.identity || {},
      smtp: profile.smtp || {},
      verification: profile.verification || {},
      provider: provider,
      workflow: workflow,
      inbound: profile.inbound || {},
    };
  }

  async function loadProfile() {
    var profileId = selectedProfile();
    var payload = await api("GET", "/portal/api/admin/aws/profile/" + encodeURIComponent(profileId));
    state.latestProfile = payload;
    profileView(compactProfile(payload));
    if (!(state.latestVerification && state.latestVerification.verification_message)) {
      linkView("");
      verificationView("No verification message loaded yet.");
    }
    return payload;
  }

  async function runProvision(action) {
    var profileId = selectedProfile();
    var payload = await api("POST", "/portal/api/admin/aws/profile/" + encodeURIComponent(profileId) + "/provision", {
      action: action,
    });
    out(payload);
    appendLog({
      type: "portal.aws_csm.provision",
      status: "ok",
      details: { profile_id: profileId, action: action, request_id: payload.request_id || "" }
    });
    return payload;
  }

  function showSmtpSetup() {
    var profile = state.latestProfile && typeof state.latestProfile.profile === "object" ? state.latestProfile.profile : {};
    var smtp = profile.smtp || {};
    var identity = profile.identity || {};
    out({
      action: "show_smtp_setup",
      profile_id: state.latestProfile && state.latestProfile.profile_id || selectedProfile(),
      domain: identity.domain || "",
      role: identity.role || "",
      send_as_email: smtp.send_as_email || identity.send_as_email || "",
      operator_inbox_target: identity.operator_inbox_target || identity.single_user_email || "",
      host: smtp.host || "",
      port: smtp.port || "",
      username: smtp.username || "",
      credentials_secret_name: smtp.credentials_secret_name || "",
      credentials_secret_state: smtp.credentials_secret_state || "",
    });
  }

  async function loadContext() {
    try {
      var payload = await api("GET", "/portal/api/data/system/config_context/aws_platform_admin");
      out(payload);
      appendLog({ type: "portal.aws_csm.context.checked", status: "ok" });
      return payload;
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.aws_csm.context.failed", status: "failed", details: { error: err.message } });
      throw err;
    }
  }

  async function status() {
    try {
      var payload = await api("GET", "/portal/api/admin/aws/fnd/status");
      state.latestStatus = payload;
      var profiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      populateProfiles(profiles);
      summary({
        canonical_root: payload.canonical_root || "",
        domain_groups: payload.domain_groups || {},
        tenant_profiles_count: payload.tenant_profiles_count || profiles.length,
        ready_for_handoff_count: payload.ready_for_handoff_count || 0,
        send_as_confirmed_count: payload.send_as_confirmed_count || 0,
        selected_profile: selectedProfile(),
        profiles: profiles
      });
      appendLog({ type: "portal.aws_csm.status.checked", status: "ok" });
      return payload;
    } catch (err) {
      summary("Error: " + err.message);
      appendLog({ type: "portal.aws_csm.status.failed", status: "failed", details: { error: err.message } });
      throw err;
    }
  }

  async function refreshStatus() {
    var payload = await runProvision("refresh_provider_status");
    await status();
    await loadProfile();
    return payload;
  }

  async function beginOnboarding() {
    var payload = await runProvision("begin_onboarding");
    if (payload && payload.profile) {
      state.latestProfile = payload;
      profileView(compactProfile(payload));
    } else {
      await loadProfile();
    }
    await status();
    return payload;
  }

  async function refreshInboundStatus() {
    var payload = await runProvision("refresh_inbound_status");
    state.latestVerification = payload;
    if (payload && payload.profile) {
      state.latestProfile = payload;
      profileView(compactProfile(payload));
    } else {
      await loadProfile();
    }
    if (payload && payload.verification_message && payload.verification_message.confirmation_link) {
      linkView(payload.verification_message.confirmation_link);
    }
    verificationView({
      inbound_status: payload.status || "",
      legacy_inbound: payload.legacy_inbound || {},
      verification_message: payload.verification_message || {},
    });
    await status();
    return payload;
  }

  async function captureVerification() {
    var payload = await runProvision("capture_verification");
    state.latestVerification = payload;
    var details = payload && payload.verification_message ? payload.verification_message : null;
    if (details && Object.keys(details).length) {
      verificationView({
        sender: details.sender || "",
        subject: details.subject || "",
        captured_at: details.captured_at || "",
        message_date: details.message_date || "",
        s3_uri: details.s3_uri || "",
        forward_from_email: details.forward_from_email || "",
        forward_to_email: details.forward_to_email || "",
        message_id: details.message_id || "",
      });
      linkView(details.confirmation_link || "");
    } else {
      verificationView("No captured Gmail verification message was found for the selected profile.");
      linkView("");
    }
    if (payload && payload.profile) {
      state.latestProfile = payload;
      profileView(compactProfile(payload));
    } else {
      await loadProfile();
    }
    await status();
    return payload;
  }

  async function replayVerification() {
    var payload = await runProvision("replay_verification_forward");
    state.latestVerification = payload;
    var details = payload && payload.verification_message ? payload.verification_message : null;
    if (details && Object.keys(details).length) {
      verificationView({
        sender: details.sender || "",
        subject: details.subject || "",
        captured_at: details.captured_at || "",
        s3_uri: details.s3_uri || "",
        message_id: details.message_id || "",
        replay_status: payload.status || "",
        lambda_result: payload.lambda_result || {},
      });
      linkView(details.confirmation_link || "");
    } else {
      verificationView("No captured Gmail verification message is available to replay yet.");
      linkView("");
    }
    if (payload && payload.profile) {
      state.latestProfile = payload;
      profileView(compactProfile(payload));
    } else {
      await loadProfile();
    }
    await status();
    return payload;
  }

  async function confirmVerified() {
    var profileId = selectedProfile();
    var ok = window.confirm("Mark " + profileId + " as Gmail verified after the operator has completed the confirmation link?");
    if (!ok) return null;
    var payload = await runProvision("confirm_verified");
    linkView("");
    verificationView("Verification confirmed for " + profileId + " at " + String(payload.verified_at || "") + ".");
    if (payload && payload.profile) {
      state.latestProfile = payload;
      profileView(compactProfile(payload));
    } else {
      await loadProfile();
    }
    await status();
    return payload;
  }

  async function refreshAll() {
    await status();
    await loadProfile();
    await loadContext();
  }

  var btn = qs("#awsp-status");
  if (btn) btn.addEventListener("click", function () { refreshStatus().catch(function () {}); });
  var contextBtn = qs("#awsp-context");
  if (contextBtn) contextBtn.addEventListener("click", loadContext);
  var beginBtn = qs("#awsp-begin");
  if (beginBtn) beginBtn.addEventListener("click", function () { beginOnboarding().catch(function () {}); });
  var smtpBtn = qs("#awsp-smtp");
  if (smtpBtn) smtpBtn.addEventListener("click", function () { showSmtpSetup(); });
  var inboundBtn = qs("#awsp-inbound");
  if (inboundBtn) inboundBtn.addEventListener("click", function () { refreshInboundStatus().catch(function () {}); });
  var profileSelect = qs("#awsp-profile-select");
  if (profileSelect) {
    profileSelect.addEventListener("change", function () {
      setSelectedProfile(profileSelect.value);
      loadProfile().catch(function () {});
    });
  }
  var captureBtn = qs("#awsp-capture");
  if (captureBtn) captureBtn.addEventListener("click", function () { captureVerification().catch(function () {}); });
  var replayBtn = qs("#awsp-replay");
  if (replayBtn) replayBtn.addEventListener("click", function () { replayVerification().catch(function () {}); });
  var confirmBtn = qs("#awsp-confirm");
  if (confirmBtn) confirmBtn.addEventListener("click", function () { confirmVerified().catch(function () {}); });
  refreshAll().catch(function () {});
})();
