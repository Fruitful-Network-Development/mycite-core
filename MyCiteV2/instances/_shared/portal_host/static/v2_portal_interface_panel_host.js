/**
 * Startup-critical interface panel host for the one-shell portal.
 *
 * Heavy CTS-GIS rendering lives in a deferred module to keep initial boot lean.
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

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function normalizePresentationTabs(tabs, fallbackTabs, defaultTabId) {
    var candidates = Array.isArray(tabs) && tabs.length ? tabs : Array.isArray(fallbackTabs) ? fallbackTabs : [];
    var normalized = candidates
      .map(function (tab, index) {
        var source = asObject(tab);
        var id = asText(source.id) || asText(source.tab_id) || "tab-" + String(index + 1);
        if (!id) return null;
        return {
          id: id,
          label: asText(source.label) || asText(source.title) || id,
          summary: asText(source.summary),
          active: source.active === true,
        };
      })
      .filter(function (tab) {
        return !!tab;
      });
    if (!normalized.length) return [];
    var requestedDefault = asText(defaultTabId);
    var activeId = "";
    normalized.forEach(function (tab) {
      if (!activeId && tab.active) activeId = tab.id;
    });
    if (!activeId) {
      activeId = normalized.some(function (tab) {
        return tab.id === requestedDefault;
      })
        ? requestedDefault
        : normalized[0].id;
    }
    return normalized.map(function (tab) {
      return Object.assign({}, tab, { active: tab.id === activeId });
    });
  }

  function activePresentationTabId(tabs, fallbackId) {
    var normalized = Array.isArray(tabs) ? tabs : [];
    for (var index = 0; index < normalized.length; index += 1) {
      if (normalized[index] && normalized[index].active) return normalized[index].id;
    }
    return normalized.length ? normalized[0].id : asText(fallbackId);
  }

  function renderPresentationTabs(tabs) {
    if (!tabs || !tabs.length) return "";
    return (
      '<div class="v2-surfaceTabs" role="tablist" aria-label="Interface tabs">' +
      tabs
        .map(function (tab) {
          return (
            '<button type="button" class="v2-surfaceTabs__tab' +
            (tab.active ? " is-active" : "") +
            '" data-interface-tab="' +
            escapeHtml(tab.id) +
            '" role="tab" aria-selected="' +
            (tab.active ? "true" : "false") +
            '">' +
            escapeHtml(tab.label || tab.id) +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderPresentationTabPanel(tabId, activeTabId, contentHtml, className) {
    var panelClass = "v2-surfaceTabPanel" + (className ? " " + className : "");
    var active = !asText(tabId) || asText(tabId) === asText(activeTabId);
    return (
      '<div class="' +
      escapeHtml(panelClass + (active ? " is-active" : "")) +
      '" data-interface-tab-panel="' +
      escapeHtml(tabId || "") +
      '" role="tabpanel"' +
      (active ? "" : ' hidden="hidden"') +
      ">" +
      String(contentHtml || "") +
      "</div>"
    );
  }

  function bindPresentationTabs(target) {
    if (!target) return;
    var buttons = Array.prototype.slice.call(target.querySelectorAll("[data-interface-tab]"));
    var panels = Array.prototype.slice.call(target.querySelectorAll("[data-interface-tab-panel]"));
    if (!buttons.length || !panels.length) return;

    function activate(tabId) {
      buttons.forEach(function (button) {
        var active = String(button.getAttribute("data-interface-tab") || "") === tabId;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      });
      panels.forEach(function (panel) {
        var active = String(panel.getAttribute("data-interface-tab-panel") || "") === tabId;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
    }

    var initialTabId = activePresentationTabId(
      buttons.map(function (button) {
        return {
          id: String(button.getAttribute("data-interface-tab") || ""),
          active: button.classList.contains("is-active"),
        };
      }),
      String(buttons[0].getAttribute("data-interface-tab") || "")
    );
    activate(initialTabId);
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        activate(String(button.getAttribute("data-interface-tab") || ""));
      });
    });
  }

  window.__MYCITE_V2_INTERFACE_TAB_HOST = {
    normalizeTabs: normalizePresentationTabs,
    activeTabId: activePresentationTabId,
    renderTabs: renderPresentationTabs,
    renderTabPanel: renderPresentationTabPanel,
    bindTabs: bindPresentationTabs,
  };

  // ---------------------------------------------------------------------------
  // Component Frame Registry
  //
  // Tracks rendered component frames so frozen frames are not re-rendered when
  // a new surface payload arrives with a matching render_key.
  // Registry persists across panel switches within a session; cleared on page reload.
  // ---------------------------------------------------------------------------

  var _componentFrameRegistry = Object.create(null);

  var componentFrameRegistry = {
    register: function (frameId, html, renderKey) {
      _componentFrameRegistry[frameId] = { html: html, key: renderKey };
    },
    isFrozen: function (frameId, incomingKey) {
      var existing = _componentFrameRegistry[frameId];
      return !!(existing && existing.key === incomingKey);
    },
    getCached: function (frameId) {
      var existing = _componentFrameRegistry[frameId];
      return existing ? existing.html : null;
    },
    clear: function (frameId) {
      delete _componentFrameRegistry[frameId];
    },
    clearAll: function () {
      _componentFrameRegistry = Object.create(null);
    },
  };

  function resolveComponentLibrary() {
    return (typeof window !== "undefined" && window.PortalComponentLibrary) || null;
  }

  function renderSingleFrameToHtml(frame) {
    var lib = resolveComponentLibrary();
    if (lib && typeof lib.renderComponentFrame === "function") {
      return lib.renderComponentFrame(frame);
    }
    // Minimal fallback if library not yet loaded.
    return (
      '<div class="v2-component-frame v2-component-frame--pending"' +
      ' data-frame-id="' + asText(frame.frame_id) + '">' +
      "<p>Component renderer loading…</p>" +
      "</div>"
    );
  }

  function renderComponentFrameRecursive(rawFrame) {
      var frame = asObject(rawFrame);
      var frameId = asText(frame.frame_id);
      var renderKey = asText(frame.render_key);
      var frozen = frame.frozen === true;
      if (frozen && frameId && componentFrameRegistry.isFrozen(frameId, renderKey)) {
        var cached = componentFrameRegistry.getCached(frameId);
        if (cached !== null) return cached;
      }
      var html = renderSingleFrameToHtml(frame);
      if (frameId) componentFrameRegistry.register(frameId, html, renderKey);
      return html;
  }

  function renderComponentFramesSection(frames) {
    var list = Array.isArray(frames) ? frames : [];
    if (!list.length) return "";
    return list.map(function (rawFrame) {
      return renderComponentFrameRecursive(rawFrame);
    }).join("");
  }

  function bindComponentFrameEngagement(target, ctx) {
    if (!target) return;
    var btns = Array.prototype.slice.call(target.querySelectorAll("[data-engage-frame]"));
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var frameId = asText(btn.getAttribute("data-engage-frame"));
        if (!frameId) return;
        // Clear the cached entry so the incoming fresh render_key causes a re-render.
        componentFrameRegistry.clear(frameId);
        // Fire the tool action. The backend detects action_kind="engage_component_frame"
        // and returns a fresh render_key for the matching frame via action_result.
        // Sibling frames are unaffected (their render_keys are unchanged).
        if (ctx && typeof ctx.dispatchToolAction === "function") {
          ctx.dispatchToolAction({ action_kind: "engage_component_frame", frame_id: frameId });
        } else if (ctx && typeof ctx.reload === "function") {
          ctx.reload();
        }
      });
    });
  }

  window.__MYCITE_V2_COMPONENT_FRAME_REGISTRY = componentFrameRegistry;
  window.__MYCITE_V2_BIND_COMPONENT_FRAME_ENGAGEMENT = bindComponentFrameEngagement;
  window.__MYCITE_V2_RENDER_COMPONENT_FRAME_RECURSIVE = renderComponentFrameRecursive;
  window.__MYCITE_V2_RENDER_COMPONENT_FRAME_LIST = renderComponentFramesSection;

  function renderRows(rows) {
    if (!rows || !rows.length) {
      return '<p class="ide-controlpanel__empty">No interface panel details.</p>';
    }
    return (
      '<dl class="v2-surface-dl">' +
      rows
        .map(function (row) {
          return (
            "<dt>" +
            escapeHtml(row.label || "") +
            "</dt><dd><strong>" +
            escapeHtml(row.status || row.value || "—") +
            "</strong>" +
            (row.detail ? "<br />" + escapeHtml(row.detail) : "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function resolveRegisteredModuleExport(moduleId, globalName) {
    if (typeof window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT === "function") {
      return window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT(moduleId, globalName);
    }
    return window[globalName] || null;
  }

  function renderDatumFocusWidget(target, region) {
    var stateReflection = asObject(region.state_reflection);
    var aitas = asObject(stateReflection.aitas);
    var nimm = asObject(stateReflection.nimm);
    var currentDatum = asText(stateReflection.current_datum);
    var currentFile = asText(stateReflection.current_file);
    var nimmActions = Array.isArray(nimm.actions) ? nimm.actions : [];
    var rows = [
      { label: "Datum", value: currentDatum || "—" },
      { label: "Document", value: currentFile || "—" },
      { label: "Intention", value: asText(aitas.intention) || "investigate" },
      { label: "Archetype", value: asText(aitas.archetype) || "—" },
    ];
    var actionsHtml = nimmActions.length
      ? '<section class="v2-card" style="margin-top:12px"><h3>Available Directives</h3><dl class="v2-surface-dl">' +
        nimmActions
          .map(function (a) {
            var action = a && typeof a === "object" ? a : {};
            return (
              "<dt>" + escapeHtml(asText(action.action_id) || "action") + "</dt>" +
              "<dd><strong>" + escapeHtml(asText(action.directive) || "—") + "</strong>" +
              (action.script_hint ? "<br /><code>" + escapeHtml(asText(action.script_hint)) + "</code>" : "") +
              "</dd>"
            );
          })
          .join("") +
        "</dl></section>"
      : "";
    target.innerHTML =
      '<div class="v2-interfacePanel-stack">' +
      '<section class="v2-card"><h3>Datum Focus</h3>' +
      '<dl class="v2-surface-dl">' +
      rows
        .map(function (row) {
          return (
            "<dt>" + escapeHtml(row.label) + "</dt>" +
            "<dd><strong>" + escapeHtml(row.value) + "</strong></dd>"
          );
        })
        .join("") +
      "</dl></section>" +
      actionsHtml +
      "</div>";
  }

  function renderGenericInterfacePanelSurface(target, region, surfacePayload) {
    var sections = region.sections || [];
    var interfaceBody = asObject(region.interface_body);
    var componentFrames = Array.isArray(interfaceBody.component_frames) ? interfaceBody.component_frames : [];
    var existingActiveTab = target && target.querySelector("[data-interface-tab].is-active");
    var existingActiveTabId = existingActiveTab ? (existingActiveTab.getAttribute("data-interface-tab") || "") : "";
    var interfaceTabs = normalizePresentationTabs(interfaceBody.tabs, [], existingActiveTabId || interfaceBody.default_tab_id);
    var adapter = toolSurfaceAdapter();
    var rendered = adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: region.title || "Interface Panel",
        hasContent: !!region.subject || !!sections.length || !!componentFrames.length,
        message: region.summary || "Select an item to load interface panel content.",
      }),
      (function () {
        // Component frames path: when interface_body.component_frames is present,
        // render using the ComponentFrameRegistry + PortalComponentLibrary.
        // Falls through to the section/tab path when absent (backwards compat).
        if (componentFrames.length) {
          return (
            '<div class="v2-interfacePanel-stack v2-interfacePanel-stack--frames">' +
            renderComponentFramesSection(componentFrames) +
            "</div>"
          );
        }

        function renderSectionCards(sectionList) {
          return (sectionList || [])
            .map(function (section) {
              return (
                '<section class="v2-card" style="margin-top:12px"><h3>' +
                escapeHtml(section.title || "Section") +
                "</h3>" +
                renderRows(section.rows || []) +
                "</section>"
              );
            })
            .join("");
        }

        function renderTabbedSections(tabs, sectionList) {
          if (!tabs.length) return renderSectionCards(sectionList);
          var activeTabId = activePresentationTabId(tabs, tabs[0].id);
          var sectionsByTab = {};
          tabs.forEach(function (tab) {
            sectionsByTab[tab.id] = [];
          });
          (sectionList || []).forEach(function (section) {
            var tabId = asText(section && section.tab_id);
            if (!tabId || !sectionsByTab[tabId]) tabId = tabs[0].id;
            sectionsByTab[tabId].push(section);
          });
          return (
            renderPresentationTabs(tabs) +
            tabs
              .map(function (tab) {
                var tabSections = sectionsByTab[tab.id] || [];
                var panelHtml =
                  renderSectionCards(tabSections) ||
                  ('<section class="v2-card" style="margin-top:12px"><h3>' +
                    escapeHtml(tab.label || tab.id) +
                    "</h3><p>No interface panel details.</p></section>");
                return renderPresentationTabPanel(tab.id, activeTabId, panelHtml);
              })
              .join("")
          );
        }

        return (
          '<div class="v2-interfacePanel-stack">' +
          (region.subject
            ? '<section class="v2-card"><h3>Subject</h3>' +
              renderRows([
                {
                  label: region.subject.level || "level",
                  value: region.subject.id || "—",
                },
              ]) +
              "</section>"
            : "") +
          (!region.subject && !sections.length
            ? '<section class="v2-card"><h3>Interface Panel</h3><p>' +
              escapeHtml(region.summary || "Select an item to load interface panel content.") +
              "</p></section>"
            : "") +
          renderTabbedSections(interfaceTabs, sections) +
          "</div>"
        );
      })()
    );
    if (rendered && interfaceTabs.length) bindPresentationTabs(target);
    if (rendered && componentFrames.length) bindComponentFrameEngagement(target, null);
  }

  function renderRegisteredPresentationSurface(ctx, target, region, surfacePayload, spec) {
    var moduleSpec = asObject(spec);
    var adapter = toolSurfaceAdapter();
    var renderer = resolveRegisteredModuleExport(moduleSpec.moduleId, moduleSpec.globalName);

    if (renderer && typeof renderer.render === "function") {
      renderer.render(ctx, target, surfacePayload);
      return;
    }
    if (typeof window.__MYCITE_V2_LOAD_SHELL_MODULE === "function" && asText(moduleSpec.moduleId)) {
      adapter.renderWrappedSurface(
        target,
        {
          state: "loading",
          title: asText(moduleSpec.label) || region.title || "Interface Panel",
          message: "Loading deferred interface renderer module…",
          warnings: [],
          readiness: {},
          toolId: asText(moduleSpec.moduleId),
        },
        ""
      );
      window.__MYCITE_V2_LOAD_SHELL_MODULE(moduleSpec.moduleId, {
        reason: "presentation_surface:" + (asText(moduleSpec.label) || asText(moduleSpec.moduleId) || "unknown"),
      })
        .then(function () {
          var resolved = resolveRegisteredModuleExport(moduleSpec.moduleId, moduleSpec.globalName);
          if (resolved && typeof resolved.render === "function") {
            resolved.render(ctx, target, surfacePayload);
            return;
          }
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: asText(moduleSpec.label) || region.title || "Interface Panel",
              unsupported: true,
              message:
                "The " +
                (asText(moduleSpec.label) || "interface panel") +
                " renderer is unavailable.",
            }),
            ""
          );
        })
        .catch(function (error) {
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: asText(moduleSpec.label) || region.title || "Interface Panel",
              unsupported: true,
              message:
                "The " +
                (asText(moduleSpec.label) || "interface panel") +
                " renderer is unavailable. " +
                asText(error && error.message),
            }),
            ""
          );
        });
      return;
    }
    adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: asText(moduleSpec.label) || region.title || "Interface Panel",
        unsupported: true,
        message:
          "The " +
          (asText(moduleSpec.label) || "interface panel") +
          " renderer is unavailable.",
      }),
      ""
    );
  }

  function renderPresentationSurfaceHost(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    var mode =
      (adapter &&
        typeof adapter.resolvePresentationSurfaceMode === "function" &&
        adapter.resolvePresentationSurfaceMode(region, surfacePayload)) ||
      "summary_surface";
    var moduleSpec =
      (adapter &&
        typeof adapter.resolvePresentationSurfaceModuleSpec === "function" &&
        adapter.resolvePresentationSurfaceModuleSpec(region, surfacePayload)) ||
      {};

    if (mode === "registered_surface" && asObject(moduleSpec).moduleId) {
      renderRegisteredPresentationSurface(ctx, target, region, surfacePayload, moduleSpec);
      return;
    }
    if (mode === "unsupported_interface_body") {
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: region,
          surfacePayload: surfacePayload,
          title: region.title || "Tool Interface Panel",
          unsupported: true,
          message: "This tool interface is not supported by the current renderer set.",
        }),
        ""
      );
      return;
    }
    renderGenericInterfacePanelSurface(target, region, surfacePayload);
  }

  window.PortalShellInterfacePanelRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var surfacePayload = region.surface_payload || {};
      var adapter = toolSurfaceAdapter();
      var family =
        (adapter && typeof adapter.resolveRegionFamily === "function" && adapter.resolveRegionFamily(region)) ||
        "";
      var mode =
        (adapter &&
          typeof adapter.resolvePresentationSurfaceMode === "function" &&
          adapter.resolvePresentationSurfaceMode(region, surfacePayload)) ||
        "summary_surface";
      if (!target) return;
      if (region.visible === false) {
        target.innerHTML = "";
        return;
      }
      if (family === "presentation_surface" || mode !== "summary_surface") {
        renderPresentationSurfaceHost(ctx, target, region, surfacePayload);
        return;
      }
      // When a datum is in focus under investigation intention, show the datum focus widget
      var stateReflection = asObject(region.state_reflection);
      var aitas = asObject(stateReflection.aitas);
      if (asText(stateReflection.current_datum) && asText(aitas.intention) === "investigate") {
        renderDatumFocusWidget(target, region);
        return;
      }
      renderGenericInterfacePanelSurface(target, region, surfacePayload);
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("interface_panel_renderers");
  }
})();
