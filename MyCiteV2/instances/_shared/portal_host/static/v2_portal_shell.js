/**
 * Canonical V2 portal shell entrypoint.
 * Loads the internal shell modules in order and owns fatal handling for
 * internal bundle-delivery failures.
 */
(function () {
  var body = document.body || document.documentElement;

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function currentRegistry() {
    return window.__MYCITE_V2_SHELL_MODULE_REGISTRY || null;
  }

  function setRegistryBootStage(state) {
    var registry = currentRegistry();
    if (!registry) return;
    registry.boot_stage = asText(state) || "template";
  }

  function setBootState(state) {
    if (!body) return;
    body.setAttribute("data-shell-boot-state", asText(state) || "template");
    setRegistryBootStage(state);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function patchFatalState(message, fatalClass) {
    setRegistryBootStage("fatal");
    if (body) {
      body.setAttribute("data-shell-boot-state", "fatal");
      body.setAttribute("data-shell-fatal-class", fatalClass || "render_dispatch_failed");
    }
    var placeholder = document.getElementById("v2-control-panel-placeholder");
    if (placeholder) {
      placeholder.textContent = message;
    }
    var workbenchBody = document.getElementById("v2-workbench-body");
    if (workbenchBody) {
      workbenchBody.innerHTML =
        '<section class="v2-card" style="max-width:720px"><h3>Shell hydration failed</h3><p>' +
        escapeHtml(message) +
        "</p></section>";
    }
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = true;
  }

  function readAssetManifest() {
    var el = document.getElementById("v2-shell-asset-manifest");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (_) {
      return null;
    }
  }

  function resolveWindowPath(path) {
    var segments = asText(path).split(".").filter(Boolean);
    var cursor = window;
    if (!segments.length) return null;
    for (var index = 0; index < segments.length; index += 1) {
      if (cursor == null) return null;
      cursor = cursor[segments[index]];
    }
    return cursor == null ? null : cursor;
  }

  function resolveCallable(target, callablePath) {
    var segments = asText(callablePath).split(".").filter(Boolean);
    var cursor = target;
    if (!segments.length) return typeof target === "function" ? target : null;
    for (var index = 0; index < segments.length; index += 1) {
      if (cursor == null) return null;
      cursor = cursor[segments[index]];
    }
    return typeof cursor === "function" ? cursor : null;
  }

  function buildModuleRegistry(assetManifest) {
    var expectedModules = asList(asObject(asObject(assetManifest).scripts).shell_modules)
      .map(function (entry, index) {
        var moduleEntry = asObject(entry);
        var moduleId = asText(moduleEntry.module_id);
        var file = asText(moduleEntry.file);
        if (!moduleId || !file) return null;
        return {
          order: index,
          module_id: moduleId,
          file: file,
          url: asText(moduleEntry.url),
          exports: asList(moduleEntry.exports).map(function (exportContract) {
            var contract = asObject(exportContract);
            return {
              global: asText(contract.global),
              required_callables: asList(contract.required_callables)
                .map(function (callableName) {
                  return asText(callableName);
                })
                .filter(Boolean),
            };
          }),
        };
      })
      .filter(Boolean);
    var expectedModuleMap = {};
    expectedModules.forEach(function (entry) {
      expectedModuleMap[entry.module_id] = entry;
    });
    return {
      schema: "mycite.v2.portal.shell.module_registry.v1",
      build_id: asText(assetManifest && assetManifest.build_id),
      boot_stage: "template",
      expected_modules: expectedModules,
      expected_module_ids: expectedModules.map(function (entry) {
        return entry.module_id;
      }),
      expected_module_map: expectedModuleMap,
      script_load_order: [],
      registrations: [],
      invalid_registrations: [],
      modules: {},
    };
  }

  function validateModuleExports(contract) {
    var exportStatuses = asList(contract && contract.exports).map(function (exportContract) {
      var exportValue = resolveWindowPath(exportContract.global);
      var requiredCallables = asList(exportContract.required_callables);
      var callableStatuses = requiredCallables.map(function (callableName) {
        return {
          callable: callableName,
          available: typeof resolveCallable(exportValue, callableName) === "function",
        };
      });
      var failures = [];
      if (exportValue == null) {
        failures.push("missing global " + exportContract.global);
      }
      callableStatuses.forEach(function (callableStatus) {
        if (!callableStatus.available) {
          failures.push("missing callable " + exportContract.global + "." + callableStatus.callable);
        }
      });
      return {
        global: exportContract.global,
        required_callables: requiredCallables,
        callable_statuses: callableStatuses,
        failures: failures,
      };
    });
    return {
      exports: exportStatuses,
      failures: exportStatuses.reduce(function (acc, exportStatus) {
        return acc.concat(exportStatus.failures);
      }, []),
    };
  }

  function buildModuleDiagnostics(moduleId) {
    var registry = currentRegistry();
    var contract = registry && registry.expected_module_map ? registry.expected_module_map[moduleId] : null;
    var exportValidation = validateModuleExports(contract || {});
    var failures = exportValidation.failures.slice();
    var registeredModuleIds = registry
      ? registry.registrations.map(function (entry) {
          return entry.module_id;
        })
      : [];
    if (!registry || !registry.modules || !registry.modules[moduleId]) {
      failures.unshift("module did not self-register");
    }
    return {
      module_id: moduleId,
      file: contract ? contract.file : "",
      boot_stage: registry ? registry.boot_stage : "",
      expected_exports: contract ? contract.exports : [],
      expected_global: contract && contract.exports[0] ? contract.exports[0].global : "",
      expected_callable:
        contract && contract.exports[0] && contract.exports[0].required_callables[0]
          ? contract.exports[0].required_callables[0]
          : "",
      script_load_order: registry ? registry.script_load_order.slice() : [],
      registered_module_ids: registeredModuleIds,
      invalid_messages: registry
        ? registry.invalid_registrations.map(function (entry) {
            return entry.message;
          })
        : [],
      failures: failures,
      export_statuses: exportValidation.exports,
    };
  }

  function registerShellModule(moduleId) {
    var token = asText(moduleId);
    var registry = currentRegistry();
    if (!registry || !token) return false;
    var contract = registry.expected_module_map ? registry.expected_module_map[token] : null;
    if (!contract) {
      registry.invalid_registrations.push({
        module_id: token || "(missing)",
        reason: "unknown_module",
        message: "Unknown shell module registration: " + (token || "(missing)"),
      });
      return false;
    }
    var exportValidation = validateModuleExports(contract);
    if (exportValidation.failures.length) {
      registry.invalid_registrations.push({
        module_id: token,
        reason: "contract_mismatch",
        message: exportValidation.failures.join("; "),
      });
      return false;
    }
    registry.modules[token] = {
      module_id: token,
      file: contract.file,
      registered_after_script_count: registry.script_load_order.length,
      exports: exportValidation.exports.map(function (exportStatus) {
        return {
          global: exportStatus.global,
          required_callables: exportStatus.required_callables.slice(),
        };
      }),
    };
    registry.registrations.push({
      module_id: token,
      file: contract.file,
    });
    return true;
  }

  function resolveShellModuleExport(moduleId, globalName) {
    var diagnostics = buildModuleDiagnostics(moduleId);
    if (diagnostics.failures.length) return null;
    return resolveWindowPath(asText(globalName) || diagnostics.expected_global);
  }

  function loadScript(moduleEntry) {
    var src = asText(moduleEntry && moduleEntry.url);
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.onload = function () {
        var registry = currentRegistry();
        if (registry) {
          registry.script_load_order.push({
            module_id: asText(moduleEntry && moduleEntry.module_id),
            file: asText(moduleEntry && moduleEntry.file),
            url: src,
          });
        }
        resolve(src);
      };
      script.onerror = function () {
        reject(new Error("Failed to load " + src));
      };
      (document.head || document.documentElement).appendChild(script);
    });
  }

  window.__MYCITE_V2_SHELL_CANONICAL_ASSET = true;
  window.__MYCITE_V2_SHELL_ENTRY_LOADED = true;
  window.__MYCITE_V2_PATCH_FATAL_STATE = patchFatalState;
  window.__MYCITE_V2_SET_SHELL_BOOT_STAGE = setRegistryBootStage;
  setBootState("entry_loaded");

  var assetManifest = readAssetManifest();
  window.__MYCITE_V2_SHELL_MODULE_REGISTRY = buildModuleRegistry(assetManifest || {});
  window.__MYCITE_V2_REGISTER_SHELL_MODULE = registerShellModule;
  window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS = buildModuleDiagnostics;
  window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT = resolveShellModuleExport;
  var scripts = assetManifest && assetManifest.scripts ? assetManifest.scripts : {};
  var internalScripts = Array.isArray(scripts.shell_modules)
    ? scripts.shell_modules
        .map(function (entry) {
          var moduleEntry = asObject(entry);
          return moduleEntry.url ? moduleEntry : null;
        })
        .filter(Boolean)
    : [];
  if (!assetManifest || !internalScripts.length) {
    patchFatalState("The portal shell asset manifest was not embedded into the page.", "asset_manifest_missing");
    return;
  }
  window.__MYCITE_V2_SHELL_ASSET_MANIFEST = assetManifest;

  internalScripts
    .reduce(function (chain, moduleEntry) {
      return chain.then(function () {
        setRegistryBootStage("module_loading");
        return loadScript(moduleEntry);
      });
    }, Promise.resolve())
    .then(function () {
      window.__MYCITE_V2_SHELL_INTERNALS_READY = true;
      setRegistryBootStage("bundle_loaded");
      var currentState = body && body.getAttribute("data-shell-boot-state");
      if (
        !window.__MYCITE_V2_SHELL_FATAL_SHOWN &&
        (!currentState || currentState === "template" || currentState === "entry_loaded" || currentState === "core_loaded")
      ) {
        setBootState("bundle_loaded");
      }
    })
    .catch(function () {
      patchFatalState("The portal shell bundle did not load or did not execute.", "bundle_not_loaded");
    });
})();
