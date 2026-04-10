/**
 * V2 portal: renders shell chrome from runtime-issued shell_composition only.
 * Dispatches navigation via POST /portal/api/v2/admin/shell using server-provided shell_request bodies.
 * Tool writes use submit_contract routes from the inspector region only.
 */
(function () {
  const SHELL_URL = "/portal/api/v2/admin/shell";
  const RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1";
  let lastShellRequest = null;

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function readBootstrapRequest() {
    const el = document.getElementById("v2-bootstrap-shell-request");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch {
      return null;
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().then(function (j) {
        return { ok: r.ok, status: r.status, json: j };
      });
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function applyChrome(comp) {
    var el = qs(".ide-shell");
    if (!el || !comp) return;
    el.setAttribute("data-active-service", comp.active_service || "system");
    el.setAttribute("data-shell-composition", comp.composition_mode || "system");
    el.setAttribute("data-foreground-shell-region", comp.foreground_shell_region || "center-workbench");
    el.setAttribute("data-control-panel-collapsed", comp.control_panel_collapsed ? "true" : "false");
    el.setAttribute("data-inspector-collapsed", comp.inspector_collapsed ? "true" : "false");
    if (comp.active_tool_slice_id) {
      el.setAttribute("data-active-mediate-tool", comp.active_tool_slice_id);
    } else {
      el.removeAttribute("data-active-mediate-tool");
    }

    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    if (menubarTitle && comp.page_title) menubarTitle.textContent = comp.page_title;
    if (menubarSub && comp.page_subtitle != null) menubarSub.textContent = comp.page_subtitle;

    var pageheadTitle = qs("#v2-workbench-title");
    var pageheadSub = qs("#v2-workbench-subtitle");
    var wbRegion = comp.regions && comp.regions.workbench;
    if (pageheadTitle && wbRegion && wbRegion.title) pageheadTitle.textContent = wbRegion.title;
    if (pageheadSub && wbRegion && wbRegion.subtitle != null) pageheadSub.textContent = wbRegion.subtitle;

    var wb = qs(".ide-workbench");
    if (wb) {
      var tool = comp.composition_mode === "tool";
      wb.setAttribute("data-foreground-visible", tool ? "false" : "true");
      wb.setAttribute("aria-hidden", tool ? "true" : "false");
    }

    var insp = document.getElementById("portalInspector");
    if (insp) {
      var collapsed = !!comp.inspector_collapsed;
      insp.classList.toggle("is-collapsed", collapsed);
      insp.setAttribute("aria-hidden", collapsed ? "true" : "false");
      insp.setAttribute("data-primary-surface", comp.composition_mode === "tool" ? "true" : "false");
      insp.setAttribute("data-surface-layout", comp.composition_mode === "tool" ? "primary-fill" : "sidebar");
    }
  }

  function renderActivityItems(items) {
    var nav = document.getElementById("v2-activity-nav");
    if (!nav) return;
    if (!items || !items.length) {
      nav.innerHTML =
        '<p class="ide-sessionLine ide-sessionLine--dim" style="padding:8px;text-align:center;font-size:10px">No activity items from shell composition.</p>';
      return;
    }
    nav.innerHTML = "";
    items.forEach(function (item) {
      var a = document.createElement("a");
      a.className = "ide-activitylink" + (item.active ? " is-active" : "");
      a.href = "#";
      a.setAttribute("aria-label", item.label || "");
      var label = (item.label || "").toUpperCase();
      a.innerHTML = "<span>" + escapeHtml(label.length > 22 ? label.slice(0, 20) + "…" : label) + "</span>";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        if (!item.shell_request) return;
        loadShell(item.shell_request);
      });
      nav.appendChild(a);
    });
  }

  function renderControlPanel(region) {
    var root = document.getElementById("portalControlPanel");
    if (!root || !region || !region.sections) return;
    root.innerHTML = "";
    region.sections.forEach(function (sec) {
      var section = document.createElement("section");
      section.className = "ide-controlpanel__section";
      var h = document.createElement("header");
      h.className = "ide-controlpanel__title";
      h.textContent = sec.title || "";
      section.appendChild(h);
      var entries = sec.entries || [];
      if (!entries.length) {
        var empty = document.createElement("div");
        empty.className = "ide-controlpanel__empty";
        empty.textContent = "No entries";
        section.appendChild(empty);
      } else {
        var ul = document.createElement("ul");
        ul.className = "ide-controlpanel__list";
        entries.forEach(function (ent) {
          var li = document.createElement("li");
          var link = document.createElement("a");
          link.className = "ide-controlpanel__link" + (ent.active ? " is-active" : "");
          link.href = "#";
          var span = document.createElement("span");
          span.textContent = ent.label || "";
          link.appendChild(span);
          if (ent.meta) {
            var sm = document.createElement("small");
            sm.textContent = ent.meta;
            link.appendChild(sm);
          }
          link.addEventListener("click", function (e) {
            e.preventDefault();
            if (ent.shell_request) loadShell(ent.shell_request);
          });
          li.appendChild(link);
          ul.appendChild(li);
        });
        section.appendChild(ul);
      }
      root.appendChild(section);
    });
  }

  function renderWorkbench(wb) {
    var body = document.getElementById("v2-workbench-body");
    if (!body || !wb) {
      return;
    }
    var kind = wb.kind || "empty";
    if (kind === "hidden" || wb.visible === false) {
      body.innerHTML = '<p class="ide-controlpanel__empty">Workbench hidden for this shell mode.</p>';
      return;
    }
    if (kind === "error") {
      body.innerHTML =
        '<div class="v2-card"><h3>' +
        escapeHtml(wb.title || "Error") +
        "</h3><p>" +
        escapeHtml(wb.message || "") +
        "</p></div>";
      return;
    }
    if (kind === "home_summary") {
      var blocks = wb.blocks || [];
      var cards =
        '<div class="v2-card-grid">' +
        blocks
          .map(function (b) {
            return (
              '<article class="v2-card"><h3>' +
              escapeHtml(b.label || "") +
              "</h3><p>" +
              escapeHtml(String(b.value != null ? b.value : "—")) +
              "</p></article>"
            );
          })
          .join("") +
        "</div>";
      body.innerHTML = cards;
      return;
    }
    if (kind === "tool_registry") {
      var rows = wb.tool_rows || [];
      var banner = wb.banner;
      var bannerHtml = "";
      if (banner && banner.message) {
        bannerHtml =
          '<div class="v2-card" style="border-color:#c5221f;margin-bottom:12px"><p><strong>' +
          escapeHtml(banner.code || "notice") +
          ":</strong> " +
          escapeHtml(banner.message) +
          "</p></div>";
      }
      var table =
        "<table class=\"v2-table\"><thead><tr><th>Tool</th><th>Slice</th><th>Entrypoint</th></tr></thead><tbody>" +
        rows
          .map(function (row) {
            return (
              "<tr><td>" +
              escapeHtml(row.label || row.tool_id || "") +
              "</td><td><code>" +
              escapeHtml(row.slice_id || "") +
              "</code></td><td><code>" +
              escapeHtml(row.entrypoint_id || "") +
              "</code></td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = bannerHtml + table;
      return;
    }
    if (kind === "datum_workbench") {
      body.innerHTML =
        '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(wb.document || {}, null, 2)) + "</pre>";
      return;
    }
    if (kind === "tool_placeholder") {
      body.innerHTML = '<p class="ide-controlpanel__empty">' + escapeHtml(wb.subtitle || "") + "</p>";
      return;
    }
    body.innerHTML = '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(wb, null, 2)) + "</pre>";
  }

  function renderInspector(region) {
    var titleEl = document.getElementById("portalInspectorTitle");
    var content = document.getElementById("v2-inspector-dynamic");
    if (!region) {
      if (titleEl) titleEl.textContent = "Overview";
      if (content) content.innerHTML = "";
      return;
    }
    if (titleEl) titleEl.textContent = region.title || "Interface panel";
    if (!content) return;
    var kind = region.kind || "empty";
    if (kind === "empty") {
      content.innerHTML = "<p class=\"ide-inspector__empty\">" + escapeHtml(region.body_text || "") + "</p>";
      return;
    }
    if (kind === "json_document") {
      content.innerHTML =
        '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(region.document || {}, null, 2)) + "</pre>";
      return;
    }
    if (kind === "narrow_write_form") {
      var contract = region.submit_contract || {};
      var initial = contract.initial_values || {};
      var fixed = contract.fixed_request_fields || {};
      var html =
        '<form id="v2-narrow-write-form" class="v2-card" style="max-width:520px">' +
        "<h3>Bounded write</h3>" +
        '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
        escapeHtml(contract.request_schema || "") +
        "</code></p>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
        '<input name="profile_id" value="' +
        escapeHtml(initial.profile_id || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">selected_verified_sender</label>' +
        '<input name="selected_verified_sender" value="' +
        escapeHtml(initial.selected_verified_sender || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
        '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply narrow write</button>' +
        "</form>" +
        '<pre id="v2-narrow-write-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
      content.innerHTML = html;
      var form = document.getElementById("v2-narrow-write-form");
      var out = document.getElementById("v2-narrow-write-result");
      if (form && out) {
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var fd = new FormData(form);
          var body = {
            schema: contract.request_schema,
            profile_id: (fd.get("profile_id") || "").toString().trim(),
            selected_verified_sender: (fd.get("selected_verified_sender") || "").toString().trim(),
          };
          if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
          if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
          out.hidden = false;
          out.textContent = "…";
          postJson(contract.route || "/portal/api/v2/admin/aws/narrow-write", body).then(function (res) {
            out.textContent = JSON.stringify(res.json, null, 2);
            if (lastShellRequest) loadShell(lastShellRequest);
          });
        });
      }
      return;
    }
    content.innerHTML = '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(region, null, 2)) + "</pre>";
  }

  function showFatal(message) {
    var nav = document.getElementById("v2-activity-nav");
    if (nav) {
      nav.innerHTML =
        '<p class="ide-sessionLine" style="padding:8px;color:#c5221f;font-size:10px;text-align:center">' +
        escapeHtml(message) +
        "</p>";
    }
    var body = document.getElementById("v2-workbench-body");
    if (body) {
      body.innerHTML = "<p>" + escapeHtml(message) + "</p>";
    }
  }

  function loadShell(requestBody) {
    lastShellRequest = requestBody;
    return postJson(SHELL_URL, requestBody).then(function (r) {
      var env = r.json;
      if (!env || env.schema !== RUNTIME_ENVELOPE_SCHEMA) {
        showFatal("Invalid or missing runtime envelope from shell route.");
        return;
      }
      var comp = env.shell_composition;
      if (!comp || !comp.regions) {
        showFatal("Runtime envelope is missing shell_composition.regions.");
        return;
      }
      applyChrome(comp);
      var act = comp.regions.activity_bar || {};
      renderActivityItems(act.items);
      renderControlPanel(comp.regions.control_panel);
      renderWorkbench(comp.regions.workbench);
      renderInspector(comp.regions.inspector);
      return env;
    });
  }

  function boot() {
    var bootstrap = readBootstrapRequest();
    if (!bootstrap) {
      showFatal("Missing server bootstrap shell request.");
      return;
    }
    loadShell(bootstrap).catch(function () {
      showFatal("Shell request failed.");
    });

    var closeBtn = qs("[data-inspector-close]");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        var shell = qs(".ide-shell");
        var inspector = document.getElementById("portalInspector");
        if (inspector) {
          inspector.classList.add("is-collapsed");
          inspector.setAttribute("aria-hidden", "true");
        }
        if (shell) {
          shell.setAttribute("data-inspector-collapsed", "true");
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
