(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});
  var state = {
    selectedProfile: "fnd",
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
    return token || state.selectedProfile || "fnd";
  }

  function setSelectedProfile(value) {
    var token = String(value || "").trim() || "fnd";
    state.selectedProfile = token;
    var node = qs("#awsp-profile-select");
    if (node && node.value !== token) node.value = token;
  }

  function populateProfiles(profiles) {
    var node = qs("#awsp-profile-select");
    if (!node) return;
    var items = Array.isArray(profiles) ? profiles : [];
    var selected = state.selectedProfile || "fnd";
    node.innerHTML = items.map(function (item) {
      var token = String(item.tenant_id || item.profile_id || "").trim();
      var label = String(item.send_as_email || token || "").trim();
      var picked = token === selected ? ' selected="selected"' : "";
      return '<option value="' + token + '"' + picked + ">" + token + " · " + label + "</option>";
    }).join("");
    if (!node.options.length) {
      node.innerHTML = '<option value="fnd">fnd</option>';
      node.value = "fnd";
      selected = "fnd";
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
      smtp: profile.smtp || {},
      verification: profile.verification || {},
      provider: provider,
      workflow: workflow,
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
