/**
 * Detects incomplete canonical-shell hydration and reports a distinct fatal
 * taxonomy for bundle-delivery vs shell POST failure.
 */
(function () {
  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function showFatal(message, fatalClass) {
    if (window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
      return;
    }
    if (typeof window.__MYCITE_V2_SHOW_FATAL === "function") {
      window.__MYCITE_V2_SHOW_FATAL(message, fatalClass);
      return;
    }
    if (typeof window.__MYCITE_V2_PATCH_FATAL_STATE === "function") {
      window.__MYCITE_V2_PATCH_FATAL_STATE(message, fatalClass);
      return;
    }
    var body = document.body || document.documentElement;
    if (body) {
      body.setAttribute("data-shell-boot-state", "fatal");
      body.setAttribute("data-shell-fatal-class", fatalClass || "shell_post_failed");
    }
  }

  function firstRegistrationFailure(moduleIds) {
    if (typeof window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS !== "function") {
      return null;
    }
    for (var index = 0; index < moduleIds.length; index += 1) {
      var diagnostics = window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS(moduleIds[index]) || {};
      var failures = asList(diagnostics.failures)
        .map(function (entry) {
          return asText(entry);
        })
        .filter(Boolean);
      if (!failures.length) {
        continue;
      }
      return {
        module_id: moduleIds[index],
        diagnostics: diagnostics,
        failures: failures,
      };
    }
    return null;
  }

  function registrationFailureMessage(failure) {
    var diagnostics = (failure && failure.diagnostics) || {};
    var loadedScripts = asList(diagnostics.script_load_order)
      .map(function (entry) {
        return asText((entry && entry.module_id) || (entry && entry.file));
      })
      .filter(Boolean);
    var registeredModules = asList(diagnostics.registered_module_ids)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    var invalidMessages = asList(diagnostics.invalid_messages)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    return (
      "The portal shell bundle loaded, but a required module registration is missing or malformed. " +
      "module_id=" +
      asText(failure && failure.module_id) +
      " expected_global=" +
      asText(diagnostics.expected_global) +
      " expected_callable=" +
      asText(diagnostics.expected_callable) +
      " boot_stage=" +
      (asText(diagnostics.boot_stage) || "unknown") +
      " loaded_scripts=" +
      (loadedScripts.join(" -> ") || "none") +
      " registered_modules=" +
      (registeredModules.join(", ") || "none") +
      " invalid_registrations=" +
      (invalidMessages.join("; ") || "none") +
      " contract_failures=" +
      asList(failure && failure.failures).join("; ")
    );
  }

  function startWatchdog() {
    var body = document.body || document.documentElement;
    var timeoutMs = Number((body && body.getAttribute("data-shell-watchdog-timeout-ms")) || 1800);
    if (!isFinite(timeoutMs) || timeoutMs < 250) {
      timeoutMs = 1800;
    }
    window.setTimeout(function () {
      if (window.__MYCITE_V2_SHELL_HYDRATED || window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
        return;
      }
      var registrationFailure = firstRegistrationFailure([
        "region_renderers",
        "tool_surface_adapter",
        "workbench_renderers",
        "inspector_renderers",
        "shell_core",
      ]);
      if (
        registrationFailure &&
        window.__MYCITE_V2_SHELL_ENTRY_LOADED &&
        window.__MYCITE_V2_SHELL_INTERNALS_READY &&
        window.__MYCITE_V2_SHELL_CORE_LOADED
      ) {
        showFatal(registrationFailureMessage(registrationFailure), "module_registration_missing");
        return;
      }
      if (!window.__MYCITE_V2_SHELL_ENTRY_LOADED || !window.__MYCITE_V2_SHELL_INTERNALS_READY || !window.__MYCITE_V2_SHELL_CORE_LOADED) {
        showFatal("The portal shell bundle did not load or did not execute.", "bundle_not_loaded");
      }
    }, timeoutMs);
  }

  window.__MYCITE_V2_SHELL_WATCHDOG = {
    start: startWatchdog,
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("shell_watchdog");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWatchdog, { once: true });
  } else {
    startWatchdog();
  }
})();
