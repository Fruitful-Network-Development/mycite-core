/**
 * Portal tool palette — Phase 3 (portal_tool_surface_contract.md).
 *
 * Lists the tools whose applies_to_archetype / applies_to_source_kind matches
 * the currently-selected datum. Fetches eligibility from
 *   GET /portal/api/tools/eligible?tenant_id=...&document_id=...&datum_address=...
 *
 * Exposed surface (window.PortalToolPalette):
 *   - fetch(opts) -> Promise<{schema, tools: [...]}>
 *   - mount(target, ctx) -> void   (attaches search input + result list to a DOM node)
 *   - refresh(target, ctx) -> void (re-renders the list against the current datum)
 *
 * Phase 3a-3c: the palette is callable via the global so tests and the browser
 * console can drive it end-to-end. Phase 3e wires the visual mount into the
 * shell composition once the interface panel is retired.
 */
(function () {
  "use strict";

  function asText(v) {
    return String(v == null ? "" : v).trim();
  }

  function escapeHtml(v) {
    return asText(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function paletteEndpoint(opts) {
    var params = new URLSearchParams();
    var tenantId = asText(opts && opts.tenantId);
    var documentId = asText(opts && opts.documentId);
    var datumAddress = asText(opts && opts.datumAddress);
    if (tenantId) params.set("tenant_id", tenantId);
    if (documentId) params.set("document_id", documentId);
    if (datumAddress) params.set("datum_address", datumAddress);
    return "/portal/api/tools/eligible?" + params.toString();
  }

  function fetchEligible(opts) {
    var url = paletteEndpoint(opts);
    return fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("palette: " + resp.status);
        }
        return resp.json();
      })
      .then(function (payload) {
        if (!payload || !Array.isArray(payload.tools)) {
          return { schema: "", tools: [] };
        }
        return payload;
      })
      .catch(function () {
        return { schema: "", tools: [], _error: true };
      });
  }

  function forSandboxEndpoint(opts) {
    var params = new URLSearchParams();
    var tenantId = asText(opts && opts.tenantId);
    var sandboxId = asText(opts && opts.sandboxId);
    if (tenantId) params.set("tenant_id", tenantId);
    if (sandboxId) params.set("sandbox_id", sandboxId);
    return "/portal/api/visualizers/for-sandbox?" + params.toString();
  }

  // Search-bar discovery: the visualizers eligible for the contents of the
  // current sandbox (ranked by reach), normalized to the same item shape
  // renderList consumes so the menubar search can list them directly.
  function fetchForSandbox(opts) {
    return fetch(forSandboxEndpoint(opts), {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error("visualizers: " + resp.status);
        return resp.json();
      })
      .then(function (payload) {
        var visualizers = payload && Array.isArray(payload.visualizers) ? payload.visualizers : [];
        return {
          schema: (payload && payload.schema) || "",
          sandbox_id: (payload && payload.sandbox_id) || "",
          sandboxes: (payload && payload.sandboxes) || [],
          documents: (payload && payload.documents) || [],
          // alias as `tools` so refresh()/renderList() are agnostic to source.
          tools: visualizers,
          visualizers: visualizers,
        };
      })
      .catch(function () {
        return { schema: "", tools: [], visualizers: [], sandboxes: [], documents: [], _error: true };
      });
  }

  function filterTools(tools, query) {
    var needle = asText(query).toLowerCase();
    if (!needle) return tools.slice();
    return tools.filter(function (tool) {
      var hay =
        asText(tool.tool_id).toLowerCase() +
        " " +
        asText(tool.label).toLowerCase() +
        " " +
        asText(tool.summary).toLowerCase();
      return hay.indexOf(needle) !== -1;
    });
  }

  function renderList(target, tools, ctx) {
    if (!target) return;
    if (!tools || tools.length === 0) {
      target.innerHTML =
        '<p class="portal-tool-palette__empty">No tools apply to the selected datum.</p>';
      return;
    }
    var items = tools
      .map(function (tool) {
        return (
          '<li class="portal-tool-palette__item" data-tool-id="' +
          escapeHtml(tool.tool_id) +
          '" data-route="' +
          escapeHtml(tool.route) +
          '">' +
          '<button type="button" class="portal-tool-palette__action">' +
          '<strong>' + escapeHtml(tool.label) + '</strong>' +
          '<small>' + escapeHtml(tool.summary) + '</small>' +
          '</button>' +
          '</li>'
        );
      })
      .join("");
    target.innerHTML = '<ul class="portal-tool-palette__list">' + items + '</ul>';
    target.querySelectorAll("[data-tool-id]").forEach(function (li) {
      li.addEventListener("click", function () {
        if (ctx && typeof ctx.onDispatch === "function") {
          ctx.onDispatch({
            tool_id: li.getAttribute("data-tool-id"),
            route: li.getAttribute("data-route"),
            datum_address: ctx.datumAddress || "",
            document_id: ctx.documentId || "",
            scope_depth: ctx.scopeDepth || "self",
          });
        }
      });
    });
  }

  function refresh(target, ctx) {
    if (!target) return Promise.resolve({ schema: "", tools: [] });
    var listEl = target.querySelector("[data-palette-list]") || target;
    var inputEl = target.querySelector("[data-palette-input]");
    // The interface-panel search is a DISCOVERY surface: whenever a sandbox is in
    // context, list every visualizer valid for that sandbox's contents so the user
    // can find + add one regardless of which document the workbench auto-selected.
    // (The workbench always auto-selects a document — often the geometry-less anchor,
    // which matches NO tool — so gating discovery on "no document selected" left the
    // search permanently empty and the sandbox's tools undiscoverable.) The selected
    // document still drives what each ADDED tool renders, not the search list. Only the
    // corpus view (no sandbox) falls back to datum-scoped eligibility.
    var fetcher = ctx && asText(ctx.sandboxId) ? fetchForSandbox : fetchEligible;
    return fetcher(ctx).then(function (payload) {
      var query = inputEl ? inputEl.value : "";
      var items = payload.tools || payload.visualizers || [];
      if (payload._error && !items.length) {
        // Fetch failed — KEEP whatever we already have (e.g. the server-embedded seed delivered
        // with the authenticated page). Only show the retry message if we have nothing at all.
        if (!(target.__paletteTools && target.__paletteTools.length)) {
          target.__paletteTools = [];
          if (listEl) {
            listEl.innerHTML =
              '<p class="portal-tool-palette__empty portal-tool-palette__error">Couldn’t load tools — click here and retry.</p>';
          }
        }
        return payload;
      }
      target.__paletteTools = items;
      renderList(listEl, filterTools(items, query), ctx);
      return payload;
    });
  }

  function mount(target, ctx) {
    if (!target) return;
    target.classList.add("portal-tool-palette");
    target.innerHTML =
      '<div class="portal-tool-palette__search">' +
      '<input type="search" data-palette-input placeholder="Search tools…" autocomplete="off">' +
      "</div>" +
      // Discovery results are an overlay DROPDOWN: hidden until the user engages the
      // search (focus/blur is wired by the interface-panel host; typing toggles below).
      '<div data-palette-list class="portal-tool-palette__results" hidden></div>';
    var inputEl = target.querySelector("[data-palette-input]");
    var listEl = target.querySelector("[data-palette-list]");
    // Seed from the server-embedded tool list (window.__MYCITE_V2_MENUBAR_TOOLS, delivered WITH the
    // authenticated page load) so the dropdown populates with NO dependency on the background XHR —
    // which can fail/race through the auth proxy and otherwise leaves the search permanently empty.
    var seed = (typeof window !== "undefined" && Array.isArray(window.__MYCITE_V2_MENUBAR_TOOLS))
      ? window.__MYCITE_V2_MENUBAR_TOOLS
      : [];
    if (seed.length) {
      target.__paletteTools = seed.slice();
      renderList(listEl, seed, ctx);
    }
    if (inputEl) {
      // Re-fetch on focus when the list is empty. The mount-time fetch runs at page load and can
      // race or fail (auth/session not yet settled, a transient error) — and the palette otherwise
      // never recovers (it fetches once and only filters the stored list). Fetching again when the
      // user actively engages the search, well after load, reliably populates it.
      inputEl.addEventListener("focus", function () {
        var tools = target.__paletteTools || [];
        if (!tools.length) {
          refresh(target, ctx).then(function () { if (listEl) listEl.removeAttribute("hidden"); });
        } else {
          renderList(listEl, filterTools(tools, inputEl.value), ctx);
          if (listEl) listEl.removeAttribute("hidden");
        }
      });
      inputEl.addEventListener("input", function () {
        var tools = target.__paletteTools || [];
        if (!tools.length) {
          // still empty (initial fetch failed/raced) — try again, then render what arrives
          refresh(target, ctx).then(function () {
            renderList(listEl, filterTools(target.__paletteTools || [], inputEl.value), ctx);
            if (listEl) listEl.removeAttribute("hidden");
          });
        }
        renderList(listEl, filterTools(tools, inputEl.value), ctx);
        if (listEl) listEl.removeAttribute("hidden");
      });
    }
    refresh(target, ctx);
  }

  window.PortalToolPalette = {
    fetch: fetchEligible,
    fetchForSandbox: fetchForSandbox,
    filter: filterTools,
    renderList: renderList,
    refresh: refresh,
    mount: mount,
  };

  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("tool_palette");
  }
})();
