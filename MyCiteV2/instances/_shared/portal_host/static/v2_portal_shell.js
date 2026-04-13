/**
 * V2 portal: renders shell chrome from runtime-issued shell_composition only.
 * Dispatches navigation via the page-selected shell endpoint using server-provided shell_request bodies.
 * Tool writes use submit_contract routes from the inspector region only.
 */
(function () {
  const BODY_DATA = document.body || document.documentElement;
  const SHELL_URL = (BODY_DATA && BODY_DATA.getAttribute("data-shell-endpoint")) || "/portal/api/v2/admin/shell";
  const RUNTIME_ENVELOPE_SCHEMA =
    (BODY_DATA && BODY_DATA.getAttribute("data-runtime-envelope-schema")) ||
    "mycite.v2.admin.runtime.envelope.v1";
  let lastShellRequest = null;
  let lastComposition = null;
  let lastDirectView = null;
  let lastEnvelope = null;

  function cloneRequestWithoutChrome(req) {
    var next = JSON.parse(JSON.stringify(req || {}));
    delete next.shell_chrome;
    return next;
  }

  function postShellChrome(chromePartial) {
    if (lastDirectView && lastDirectView.url && lastDirectView.requestBody) {
      var nextDirect = JSON.parse(JSON.stringify(lastDirectView.requestBody || {}));
      nextDirect.shell_chrome = Object.assign({}, nextDirect.shell_chrome || {}, chromePartial);
      return loadRuntimeView(lastDirectView.url, nextDirect);
    }
    if (!lastShellRequest) return Promise.resolve();
    var next = JSON.parse(JSON.stringify(lastShellRequest));
    next.shell_chrome = Object.assign({}, next.shell_chrome || {}, chromePartial);
    return loadShell(next);
  }

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
      return r.text().then(function (text) {
        var j = null;
        try {
          j = text ? JSON.parse(text) : null;
        } catch (_) {
          j = null;
        }
        return {
          ok: r.ok,
          status: r.status,
          json: j,
          bodySnippet: text ? text.slice(0, 280) : "",
        };
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

  function compactJson(value) {
    if (value == null) return "—";
    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  }

  function activityIconMarkup(item) {
    var iconId = (item && item.icon_id) || "generic";
    if (iconId === "fnd-logo") {
      return (
        '<span class="ide-activityicon ide-activityicon--logo" aria-hidden="true">' +
        '<img src="/portal/static/icons/logos/fnd.svg" alt="" width="22" height="22" />' +
        "</span>"
      );
    }
    var svg = "";
    if (iconId === "network") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="6" cy="12" r="2.2"></circle><circle cx="18" cy="6" r="2.2"></circle><circle cx="18" cy="18" r="2.2"></circle>' +
        '<path d="M8 11l7.8-4"></path><path d="M8 13l7.8 4"></path>' +
        "</svg>";
    } else if (iconId === "system") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7.5h16v9H4z"></path><path d="M8 16.5h8"></path><path d="M10 4.5h4"></path>' +
        "</svg>";
    } else if (iconId === "utilities") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7h16v10H4z"></path><path d="M9 7V5.5h6V7"></path><path d="M12 11v5"></path><path d="M9.5 13.5h5"></path>' +
        "</svg>";
    } else if (iconId === "aws") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M7.5 17.5h8a4 4 0 0 0 .7-7.94A5.2 5.2 0 0 0 6.7 8.5 3.6 3.6 0 0 0 7.5 17.5z"></path>' +
        '<path d="M8 20c2 .9 5 .9 8 0"></path>' +
        "</svg>";
    } else if (iconId === "cts_gis") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 20s5-4.3 5-9a5 5 0 1 0-10 0c0 4.7 5 9 5 9z"></path><circle cx="12" cy="11" r="1.8"></circle>' +
        "</svg>";
    } else if (iconId === "fnd_ebi") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4.5 6.5h15"></path><path d="M4.5 12h15"></path><path d="M4.5 17.5h9"></path>' +
        '<path d="M17 16l2.5 2.5"></path><circle cx="14.5" cy="13.5" r="3.5"></circle>' +
        "</svg>";
    } else if (iconId === "datum") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 4l7 4-7 4-7-4 7-4z"></path><path d="M5 12l7 4 7-4"></path><path d="M5 16l7 4 7-4"></path>' +
        "</svg>";
    } else {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="12" cy="12" r="8"></circle>' +
        "</svg>";
    }
    return '<span class="ide-activityicon" aria-hidden="true">' + svg + "</span>";
  }

  function renderCtsGisSvg(mapProjection) {
    var featureCollection = (mapProjection && mapProjection.feature_collection) || {};
    var features = featureCollection.features || [];
    if (!features.length) {
      return (
        '<div class="v2-card" style="margin-top:12px"><h3>Geographic pane</h3><p>No projectable features are available for this document.</p></div>'
      );
    }
    var bounds = featureCollection.bounds || [-180, -90, 180, 90];
    var minLon = Number(bounds[0]);
    var minLat = Number(bounds[1]);
    var maxLon = Number(bounds[2]);
    var maxLat = Number(bounds[3]);
    if (!isFinite(minLon) || !isFinite(minLat) || !isFinite(maxLon) || !isFinite(maxLat)) {
      minLon = -180;
      minLat = -90;
      maxLon = 180;
      maxLat = 90;
    }
    if (minLon === maxLon) {
      minLon -= 1;
      maxLon += 1;
    }
    if (minLat === maxLat) {
      minLat -= 1;
      maxLat += 1;
    }
    var width = 680;
    var height = 360;
    var pad = 18;
    function project(coord) {
      var lon = Number((coord || [0, 0])[0]);
      var lat = Number((coord || [0, 0])[1]);
      var x = pad + ((lon - minLon) / (maxLon - minLon)) * (width - pad * 2);
      var y = height - pad - ((lat - minLat) / (maxLat - minLat)) * (height - pad * 2);
      return [x.toFixed(2), y.toFixed(2)];
    }
    var shapes = features
      .map(function (feature) {
        var geometry = feature.geometry || {};
        var props = feature.properties || {};
        var featureId = feature.id || "";
        var selected = !!feature.selected;
        var attentionMember = !!props.attention_member;
        var stroke = selected ? "#0b57d0" : attentionMember ? "#9a5b00" : "#285943";
        var fill = selected
          ? "rgba(11,87,208,0.28)"
          : attentionMember
          ? "rgba(154,91,0,0.22)"
          : "rgba(40,89,67,0.18)";
        var title = escapeHtml(props.profile_label || props.label_text || featureId || "feature");
        if (geometry.type === "Point") {
          var point = project(geometry.coordinates || [0, 0]);
          return (
            '<g class="v2-map-feature" data-cts-gis-feature-id="' +
            escapeHtml(featureId) +
            '">' +
            '<title>' +
            title +
            "</title>" +
            '<circle cx="' +
            point[0] +
            '" cy="' +
            point[1] +
            '" r="' +
            (selected ? "7" : "5") +
            '" fill="' +
            fill +
            '" stroke="' +
            stroke +
            '" stroke-width="2"></circle></g>'
          );
        }
        if (geometry.type === "Polygon") {
          var ring = ((geometry.coordinates || [])[0] || []).map(project);
          var points = ring
            .map(function (point) {
              return point[0] + "," + point[1];
            })
            .join(" ");
          return (
            '<g class="v2-map-feature" data-cts-gis-feature-id="' +
            escapeHtml(featureId) +
            '">' +
            '<title>' +
            title +
            "</title>" +
            '<polygon points="' +
            points +
            '" fill="' +
            fill +
            '" stroke="' +
            stroke +
            '" stroke-width="' +
            (selected ? "2.8" : "1.6") +
            '"></polygon></g>'
          );
        }
        return "";
      })
      .join("");
    return (
      '<div class="v2-card" style="margin-top:12px"><h3>Geographic pane</h3><svg viewBox="0 0 ' +
      width +
      " " +
      height +
      '" style="width:100%;height:auto;border:1px solid #d3d9df;background:linear-gradient(180deg,#f7fbf9,#eef4f1)">' +
      '<rect x="0" y="0" width="' +
      width +
      '" height="' +
      height +
      '" fill="transparent"></rect>' +
      shapes +
      "</svg></div>"
    );
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
      wb.setAttribute("data-active-service", comp.active_service || "system");
      wb.setAttribute("data-foreground-visible", "true");
      wb.setAttribute("aria-hidden", "false");
    }

    var insp = document.getElementById("portalInspector");
    if (insp) {
      var collapsed = !!comp.inspector_collapsed;
      insp.classList.toggle("is-collapsed", collapsed);
      insp.setAttribute("aria-hidden", collapsed ? "true" : "false");
      insp.setAttribute("data-primary-surface", "false");
      insp.setAttribute("data-surface-layout", "sidebar");
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
      a.className =
        "ide-activitylink ide-activitylink--" +
        escapeHtml((item.nav_kind || "tool").replace(/[^a-z_-]/gi, "").toLowerCase()) +
        (item.active ? " is-active" : "");
      a.href = item.href || "#";
      a.setAttribute("aria-label", item.aria_label || item.label || "");
      a.setAttribute("title", item.aria_label || item.label || "");
      a.innerHTML =
        activityIconMarkup(item) +
        '<span class="ide-activitylabel">' +
        escapeHtml(item.label || "") +
        "</span>";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        if (!item.shell_request) return;
        loadShell(item.shell_request);
      });
      nav.appendChild(a);
    });
  }

  function renderControlPanelTabs(region) {
    var tabs = (region && region.tabs) || [];
    if (!tabs.length) return "";
    return (
      '<div class="ide-controlpanel__tabs">' +
      tabs
        .map(function (tab) {
          return (
            '<a class="ide-controlpanel__tab' +
            (tab.active ? " is-active" : "") +
            '" href="' +
            escapeHtml(tab.href || "#") +
            '" data-controlpanel-tab-id="' +
            escapeHtml(tab.tab_id || "") +
            '">' +
            escapeHtml(tab.label || tab.tab_id || "tab") +
            "</a>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderControlPanelSection(sec, secIndex) {
    var entries = sec.entries || [];
    var inner = "";
    if (!entries.length) {
      inner = '<div class="ide-controlpanel__empty">No entries</div>';
    } else {
      inner =
        '<ul class="ide-controlpanel__list">' +
        entries
          .map(function (ent, entryIndex) {
            return (
              "<li>" +
              '<a class="ide-controlpanel__link' +
              (ent.active ? " is-active" : "") +
              (ent.gated ? " is-gated" : "") +
              '" href="' +
              escapeHtml(ent.href || "#") +
              '" data-controlpanel-section-index="' +
              escapeHtml(String(secIndex)) +
              '" data-controlpanel-entry-index="' +
              escapeHtml(String(entryIndex)) +
              '"' +
              (ent.gated ? ' aria-disabled="true"' : "") +
              ">" +
              "<span>" +
              escapeHtml(ent.label || "") +
              "</span>" +
              (ent.meta ? "<small>" + escapeHtml(ent.meta) + "</small>" : "") +
              "</a></li>"
            );
          })
          .join("") +
        "</ul>";
    }
    return (
      '<section class="ide-controlpanel__section">' +
      '<header class="ide-controlpanel__title">' +
      escapeHtml(sec.title || "") +
      "</header>" +
      inner +
      "</section>"
    );
  }

  function renderSystemControlPanel(region) {
    return (
      '<div class="ide-controlpanel__module">' +
      '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">SYSTEM</div><div class="ide-controlpanel__moduleSub">Core sandbox and datum-facing workbench.</div></div>' +
      renderControlPanelTabs(region) +
      (region.sections || []).map(renderControlPanelSection).join("") +
      "</div>"
    );
  }

  function renderNetworkControlPanel(region) {
    return (
      '<div class="ide-controlpanel__module">' +
      '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">NETWORK</div><div class="ide-controlpanel__moduleSub">Scaffolded hosted and relationship root.</div></div>' +
      renderControlPanelTabs(region) +
      (region.sections || []).map(renderControlPanelSection).join("") +
      "</div>"
    );
  }

  function renderUtilitiesControlPanel(region) {
    return (
      '<div class="ide-controlpanel__module">' +
      '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">UTILITIES</div><div class="ide-controlpanel__moduleSub">Tool management, config, and follow-on utility tabs.</div></div>' +
      renderControlPanelTabs(region) +
      (region.sections || []).map(renderControlPanelSection).join("") +
      "</div>"
    );
  }

  function renderAwsCsmControlPanel(region) {
    return (
      '<div class="ide-controlpanel__module">' +
      '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">AWS-CSM</div><div class="ide-controlpanel__moduleSub">Family-local domain and mailbox context.</div></div>' +
      (region.sections || []).map(renderControlPanelSection).join("") +
      "</div>"
    );
  }

  function renderControlPanel(region) {
    var root = document.getElementById("portalControlPanel");
    if (!root || !region) return;
    var kind = region.kind || "";
    if (kind === "system_control_panel") {
      root.innerHTML = renderSystemControlPanel(region);
    } else if (kind === "network_control_panel") {
      root.innerHTML = renderNetworkControlPanel(region);
    } else if (kind === "utilities_control_panel") {
      root.innerHTML = renderUtilitiesControlPanel(region);
    } else if (kind === "aws_csm_control_panel") {
      root.innerHTML = renderAwsCsmControlPanel(region);
    } else if (region.sections) {
      root.innerHTML = (region.sections || []).map(renderControlPanelSection).join("");
    } else {
      root.innerHTML =
        '<section class="ide-controlpanel__section"><header class="ide-controlpanel__title">Context</header><div class="ide-controlpanel__empty">No page-specific control panel is available.</div></section>';
    }

    Array.prototype.forEach.call(root.querySelectorAll("[data-controlpanel-tab-id], .ide-controlpanel__link"), function (node) {
      node.addEventListener("click", function (e) {
        e.preventDefault();
        var shellRequest = null;
        if (node.hasAttribute("data-controlpanel-tab-id")) {
          var tabId = node.getAttribute("data-controlpanel-tab-id") || "";
          var tabs = region.tabs || [];
          var match = tabs.filter(function (tab) {
            return String(tab.tab_id || "") === tabId;
          })[0];
          shellRequest = match && match.shell_request;
        } else {
          var secIndex = Number(node.getAttribute("data-controlpanel-section-index") || "-1");
          var entryIndex = Number(node.getAttribute("data-controlpanel-entry-index") || "-1");
          var section = ((region.sections || [])[secIndex] || {});
          var entry = ((section.entries || [])[entryIndex] || {});
          shellRequest = entry && entry.shell_request;
        }
        if (shellRequest) loadShell(shellRequest);
      });
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
    if (kind === "system_root") {
      var systemTabs = wb.root_tabs || [];
      var systemTabRow =
        systemTabs.length > 0
          ? '<div class="page-tabs">' +
            systemTabs
              .map(function (tab) {
                return (
                  '<a class="page-tab' +
                  (tab.active ? " is-active" : "") +
                  '" href="' +
                  escapeHtml(tab.href || "#") +
                  '" data-workbench-root-tab="' +
                  escapeHtml(tab.tab_id || "") +
                  '">' +
                  escapeHtml(tab.label || tab.tab_id || "tab") +
                  "</a>"
                );
              })
              .join("") +
            "</div>"
          : "";
      var systemBlocks = wb.blocks || [];
      var systemCards =
        '<div class="v2-card-grid">' +
        systemBlocks
          .map(function (block) {
            return (
              '<article class="v2-card"><h3>' +
              escapeHtml(block.label || "Metric") +
              "</h3><p>" +
              escapeHtml(String(block.value != null ? block.value : "—")) +
              "</p></article>"
            );
          })
          .join("") +
        "</div>";
      var systemNotes = wb.notes || [];
      var systemNoteBlock =
        systemNotes.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Shell posture</h3><dl class="v2-surface-dl">' +
            systemNotes
              .map(function (note) {
                return "<dt>" + escapeHtml(note.label || "") + "</dt><dd>" + escapeHtml(String(note.value || "—")) + "</dd>";
              })
              .join("") +
            "</dl></section>"
          : "";
      var sourcesSummary = wb.sources_summary || {};
      var sandboxSummary = wb.sandbox_summary || {};
      var docs = (wb.root_tab || "home") === "sandbox" ? sandboxSummary.documents || [] : sourcesSummary.documents || [];
      var docTable =
        docs.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>' +
            escapeHtml((wb.root_tab || "home") === "sandbox" ? "Sandbox documents" : "Authoritative documents") +
            '</h3><table class="v2-table"><thead><tr><th>Document</th><th>Source</th><th>Rows</th><th>Issues</th></tr></thead><tbody>' +
            docs
              .slice(0, 80)
              .map(function (doc) {
                return (
                  "<tr><td><code>" +
                  escapeHtml(doc.document_name || "document") +
                  "</code></td><td>" +
                  escapeHtml(doc.source_kind || "—") +
                  "</td><td>" +
                  escapeHtml(String(doc.row_count != null ? doc.row_count : "—")) +
                  "</td><td>" +
                  escapeHtml(String(doc.diagnostic_row_count != null ? doc.diagnostic_row_count : "0")) +
                  "</td></tr>"
                );
              })
              .join("") +
            "</tbody></table></section>"
          : "";
      body.innerHTML = systemTabRow + systemCards + systemNoteBlock + docTable;
      Array.prototype.forEach.call(body.querySelectorAll("[data-workbench-root-tab]"), function (node) {
        node.addEventListener("click", function (e) {
          e.preventDefault();
          var tabId = node.getAttribute("data-workbench-root-tab") || "";
          var match = systemTabs.filter(function (tab) {
            return String(tab.tab_id || "") === tabId;
          })[0];
          if (match && match.shell_request) loadShell(match.shell_request);
        });
      });
      return;
    }
    if (kind === "utilities_root") {
      var utilityTabs = wb.root_tabs || [];
      var utilityTabRow =
        utilityTabs.length > 0
          ? '<div class="page-tabs">' +
            utilityTabs
              .map(function (tab) {
                return (
                  '<a class="page-tab' +
                  (tab.active ? " is-active" : "") +
                  '" href="' +
                  escapeHtml(tab.href || "#") +
                  '" data-workbench-utility-tab="' +
                  escapeHtml(tab.tab_id || "") +
                  '">' +
                  escapeHtml(tab.label || tab.tab_id || "tab") +
                  "</a>"
                );
              })
              .join("") +
            "</div>"
          : "";
      var utilityContent = "";
      if ((wb.root_tab || "tools") === "config") {
        utilityContent =
          '<section class="v2-card"><h3>Config</h3><dl class="v2-surface-dl">' +
          (wb.config_sections || [])
            .map(function (section) {
              return "<dt>" + escapeHtml(section.label || "") + "</dt><dd>" + escapeHtml(section.value || "—") + "</dd>";
            })
            .join("") +
          "</dl></section>";
      } else if ((wb.root_tab || "tools") === "vault") {
        var vaultNotes = ((wb.vault_summary || {}).notes) || [];
        utilityContent =
          '<section class="v2-card"><h3>Vault</h3><ul>' +
          (vaultNotes.length
            ? vaultNotes
                .map(function (note) {
                  return "<li>" + escapeHtml(String(note)) + "</li>";
                })
                .join("")
            : "<li>Vault placeholder.</li>") +
          "</ul></section>";
      } else {
        var toolRows = wb.tool_rows || [];
        utilityContent =
          '<section class="v2-card"><h3>Tools</h3><table class="v2-table"><thead><tr><th>Tool</th><th>Entrypoint</th><th>Visibility</th></tr></thead><tbody>' +
          toolRows
            .map(function (row) {
              return (
                "<tr><td><a href=\"" +
                escapeHtml(row.href || "#") +
                '" data-utility-tool-slice="' +
                escapeHtml(row.slice_id || "") +
                "\">" +
                escapeHtml(row.label || row.tool_id || "tool") +
                "</a></td><td><code>" +
                escapeHtml(row.entrypoint_id || "") +
                "</code></td><td>" +
                escapeHtml(row.visibility_status || "—") +
                "</td></tr>"
              );
            })
            .join("") +
          "</tbody></table></section>";
      }
      body.innerHTML = utilityTabRow + utilityContent;
      Array.prototype.forEach.call(body.querySelectorAll("[data-workbench-utility-tab]"), function (node) {
        node.addEventListener("click", function (e) {
          e.preventDefault();
          var tabId = node.getAttribute("data-workbench-utility-tab") || "";
          var match = utilityTabs.filter(function (tab) {
            return String(tab.tab_id || "") === tabId;
          })[0];
          if (match && match.shell_request) loadShell(match.shell_request);
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-utility-tool-slice]"), function (node) {
        node.addEventListener("click", function (e) {
          e.preventDefault();
          var sliceId = node.getAttribute("data-utility-tool-slice") || "";
          var rows = wb.tool_rows || [];
          var match = rows.filter(function (row) {
            return String(row.slice_id || "") === sliceId;
          })[0];
          if (match && match.shell_request) {
            loadShell(match.shell_request);
          }
        });
      });
      return;
    }
    if (kind === "aws_csm_family_workbench") {
      var familyHealth = wb.family_health || {};
      var domainStates = wb.domain_states || [];
      var selectedDomain = wb.selected_domain_state || {};
      var selectedAuthor = wb.selected_author || {};
      var subnav = wb.subsurface_navigation || {};
      var familyCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
        escapeHtml(familyHealth.mailbox_readiness || familyHealth.status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Verified sender</h3><p>' +
        escapeHtml(familyHealth.selected_verified_sender || selectedAuthor.address || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Queue</h3><p>' +
        escapeHtml(familyHealth.dispatch_queue_state || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Inbound rules</h3><p>' +
        escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
        " ready</p></article>" +
        "</div>";
      var familyHealthBlock =
        '<section class="v2-card" style="margin-top:12px"><h3>Family health</h3><dl class="v2-surface-dl">' +
        "<dt>STS identity</dt><dd><code>" +
        escapeHtml(familyHealth.sts_identity_arn || "—") +
        "</code></dd><dt>Ready domains</dt><dd>" +
        escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
        "/" +
        escapeHtml(String(familyHealth.domain_count != null ? familyHealth.domain_count : "0")) +
        "</dd><dt>Dispatch queue</dt><dd>" +
        escapeHtml(familyHealth.dispatch_queue_state || "—") +
        "</dd><dt>Dispatcher Lambda</dt><dd>" +
        escapeHtml(familyHealth.dispatcher_lambda_state || "—") +
        "</dd><dt>Inbound Lambda</dt><dd>" +
        escapeHtml(familyHealth.inbound_lambda_state || "—") +
        "</dd></dl></section>";
      var navButtons =
        '<section class="v2-card" style="margin-top:12px"><h3>Family navigation</h3><div style="display:flex;gap:8px;flex-wrap:wrap">' +
        [
          { key: "read_only_shell_request", label: "Open read-only overview" },
          { key: "narrow_write_shell_request", label: "Open sender selection" },
          { key: "onboarding_shell_request", label: "Open onboarding" }
        ]
          .map(function (item) {
            var req = subnav[item.key];
            if (!req) return '<span class="ide-controlpanel__empty">' + escapeHtml(item.label) + "</span>";
            return (
              '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-shell-request-key="' +
              escapeHtml(item.key) +
              '">' +
              escapeHtml(item.label) +
              "</button>"
            );
          })
          .join("") +
        "</div></section>";
      var domainCards =
        domainStates.length > 0
          ? domainStates
              .map(function (state) {
                return (
                  '<section class="v2-card" style="margin-top:12px"><h3>' +
                  escapeHtml(state.domain || "domain") +
                  "</h3><dl class=\"v2-surface-dl\"><dt>Selected author</dt><dd>" +
                  escapeHtml(((state.selected_author || {}).address) || "—") +
                  "</dd><dt>Contacts</dt><dd>" +
                  escapeHtml(String(state.contact_count != null ? state.contact_count : "0")) +
                  " total · " +
                  escapeHtml(String(state.subscribed_contact_count != null ? state.subscribed_contact_count : "0")) +
                  " subscribed</dd><dt>Inbound</dt><dd>" +
                  escapeHtml(state.inbound_state || "—") +
                  "</dd><dt>Dispatch</dt><dd>" +
                  escapeHtml(state.dispatch_state || "—") +
                  "</dd></dl></section>"
                );
              })
              .join("")
          : '<section class="v2-card" style="margin-top:12px"><h3>Domain groups</h3><p>No AWS-CSM domain groups are currently configured for this instance.</p></section>';
      body.innerHTML = familyCards + familyHealthBlock + navButtons + domainCards;
      Array.prototype.forEach.call(body.querySelectorAll("[data-aws-shell-request-key]"), function (node) {
        node.addEventListener("click", function () {
          var key = node.getAttribute("data-aws-shell-request-key") || "";
          if (subnav[key]) loadShell(subnav[key]);
        });
      });
      return;
    }
    if (kind === "aws_csm_subsurface_workbench") {
      var profileSummary = wb.profile_summary || {};
      var awsWarnings = wb.compatibility_warnings || [];
      var openPanelButton =
        wb.submit_route
          ? '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-open-aws-interface-panel">Open interface panel</button>'
          : "";
      body.innerHTML =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Profile</h3><p>' +
        escapeHtml(profileSummary.profile_id || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Domain</h3><p>' +
        escapeHtml(profileSummary.domain || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Selected sender</h3><p>' +
        escapeHtml(wb.selected_verified_sender || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
        escapeHtml(wb.mailbox_readiness || "—") +
        "</p></article>" +
        "</div>" +
        '<section class="v2-card" style="margin-top:12px"><h3>' +
        escapeHtml(wb.title || "AWS-CSM") +
        '</h3><p>' +
        escapeHtml(wb.help_text || "") +
        "</p>" +
        openPanelButton +
        "</section>" +
        (awsWarnings.length
          ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
            awsWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></section>"
          : "");
      var openPanel = document.getElementById("v2-open-aws-interface-panel");
      if (openPanel) {
        openPanel.addEventListener("click", function () {
          postShellChrome({ inspector_collapsed: false });
        });
      }
      return;
    }
    if (kind === "home_summary") {
      var blocks = wb.blocks || [];
      var notes = wb.notes || [];
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
      var noteBlock =
        notes.length > 0
          ? '<div class="v2-card" style="margin-top:12px"><h3>Tool exposure</h3><dl class="v2-surface-dl">' +
            notes
              .map(function (note) {
                return (
                  "<dt>" +
                  escapeHtml(note.label || "") +
                  "</dt><dd>" +
                  escapeHtml(String(note.value != null ? note.value : "—")) +
                  "</dd>"
                );
              })
              .join("") +
            "</dl></div>"
          : "";
      body.innerHTML = cards + noteBlock;
      return;
    }
    if (kind === "tenant_home_status") {
      var tenantProfile = wb.tenant_profile || {};
      var availableSlices = wb.available_slices || [];
      var warnings = wb.warnings || [];
      var warningBlock =
        warnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            warnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var cards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>You are here</h3><p>' +
        escapeHtml(wb.where_you_are || "Portal home") +
        "</p></article>" +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Read/write posture</h3><p>' +
        escapeHtml(wb.read_write_posture || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Profile in view</h3><p>' +
        escapeHtml(tenantProfile.profile_title || "—") +
        "</p></article>" +
        "</div>";
      var details =
        '<dl class="v2-surface-dl">' +
        "<dt>Tenant</dt><dd>" +
        escapeHtml(tenantProfile.tenant_id || "—") +
        "</dd>" +
        "<dt>Domain</dt><dd>" +
        escapeHtml(tenantProfile.tenant_domain || "—") +
        "</dd>" +
        "<dt>Entity type</dt><dd>" +
        escapeHtml(tenantProfile.entity_type || "—") +
        "</dd>" +
        "<dt>Profile summary</dt><dd>" +
        escapeHtml(tenantProfile.profile_summary || "—") +
        "</dd>" +
        "<dt>Contact email</dt><dd>" +
        escapeHtml(tenantProfile.contact_email || "—") +
        "</dd>" +
        "<dt>Public website</dt><dd>" +
        escapeHtml(tenantProfile.public_website_url || "—") +
        "</dd>" +
        "<dt>Publication mode</dt><dd>" +
        escapeHtml(tenantProfile.publication_mode || "—") +
        "</dd>" +
        "<dt>Profile resolution</dt><dd>" +
        escapeHtml(tenantProfile.profile_resolution || "—") +
        "</dd>" +
        "<dt>Available documents</dt><dd>" +
        escapeHtml((tenantProfile.available_documents || []).join(", ") || "—") +
        "</dd></dl>";
      var slicesHtml =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        availableSlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = warningBlock + cards + details + '<div class="v2-card" style="margin-top:12px"><h3>Available slices</h3>' + slicesHtml + "</div>";
      return;
    }
    if (kind === "operational_status") {
      var auditPersistence = wb.audit_persistence || {};
      var statusWarnings = wb.warnings || [];
      var statusSlices = wb.available_slices || [];
      var statusWarningBlock =
        statusWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            statusWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var statusCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.current_rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Read/write posture</h3><p>' +
        escapeHtml(wb.read_write_posture || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Audit health</h3><p>' +
        escapeHtml(String(auditPersistence.health_state || "—").replace(/_/g, " ")) +
        "</p></article>" +
        "</div>";
      var statusDetails =
        '<dl class="v2-surface-dl">' +
        "<dt>Storage state</dt><dd>" +
        escapeHtml(String(auditPersistence.storage_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Recent window limit</dt><dd>" +
        escapeHtml(String(auditPersistence.recent_window_limit != null ? auditPersistence.recent_window_limit : "—")) +
        "</dd>" +
        "<dt>Recent record count</dt><dd>" +
        escapeHtml(String(auditPersistence.recent_record_count != null ? auditPersistence.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest persisted at</dt><dd>" +
        escapeHtml(
          String(
            auditPersistence.latest_recorded_at_unix_ms != null
              ? auditPersistence.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>";
      var statusTable =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        statusSlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML =
        statusWarningBlock +
        statusCards +
        statusDetails +
        '<div class="v2-card" style="margin-top:12px"><h3>Visible slices</h3>' +
        statusTable +
        "</div>";
      return;
    }
    if (kind === "audit_activity") {
      var recentActivity = wb.recent_activity || {};
      var activityWarnings = wb.warnings || [];
      var activitySlices = wb.available_slices || [];
      var activityRecords = recentActivity.records || [];
      var activityWarningBlock =
        activityWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            activityWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var activityCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.current_rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Read/write posture</h3><p>' +
        escapeHtml(wb.read_write_posture || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Activity state</h3><p>' +
        escapeHtml(String(recentActivity.activity_state || "—").replace(/_/g, " ")) +
        "</p></article>" +
        "</div>";
      var activityDetails =
        '<dl class="v2-surface-dl">' +
        "<dt>Recent window limit</dt><dd>" +
        escapeHtml(String(recentActivity.recent_window_limit != null ? recentActivity.recent_window_limit : "—")) +
        "</dd>" +
        "<dt>Recent record count</dt><dd>" +
        escapeHtml(String(recentActivity.recent_record_count != null ? recentActivity.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest recorded at</dt><dd>" +
        escapeHtml(
          String(
            recentActivity.latest_recorded_at_unix_ms != null
              ? recentActivity.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>";
      var activityRows =
        activityRecords.length > 0
          ? "<table class=\"v2-table\"><thead><tr><th>Recorded At</th><th>Event</th><th>Verb</th><th>Subject</th><th>Details</th></tr></thead><tbody>" +
            activityRecords
              .map(function (record) {
                return (
                  "<tr><td>" +
                  escapeHtml(String(record.recorded_at_unix_ms != null ? record.recorded_at_unix_ms : "—")) +
                  "</td><td>" +
                  escapeHtml(record.event_type || "—") +
                  "</td><td>" +
                  escapeHtml(record.shell_verb || "—") +
                  "</td><td><code>" +
                  escapeHtml(record.focus_subject || "") +
                  "</code></td><td><code>" +
                  escapeHtml(compactJson(record.details || {})) +
                  "</code></td></tr>"
                );
              })
              .join("") +
            "</tbody></table>"
          : '<p class="ide-controlpanel__empty">No recent tenant-facing audit activity is visible in this fixed window.</p>';
      var activitySliceTable =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        activitySlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML =
        activityWarningBlock +
        activityCards +
        activityDetails +
        '<div class="v2-card" style="margin-top:12px"><h3>Recent records</h3>' +
        activityRows +
        "</div>" +
        '<div class="v2-card" style="margin-top:12px"><h3>Visible slices</h3>' +
        activitySliceTable +
        "</div>";
      return;
    }
    if (kind === "profile_basics_write") {
      var profileBasics = wb.confirmed_profile_basics || {};
      var basicsWarnings = wb.warnings || [];
      var basicsSlices = wb.available_slices || [];
      var basicsWarningBlock =
        basicsWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            basicsWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var basicsCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.current_rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Read/write posture</h3><p>' +
        escapeHtml(wb.read_write_posture || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Write status</h3><p>' +
        escapeHtml(wb.write_status || "—") +
        "</p></article>" +
        "</div>";
      var basicsDetails =
        '<dl class="v2-surface-dl">' +
        "<dt>Profile title</dt><dd>" +
        escapeHtml(profileBasics.profile_title || "—") +
        "</dd>" +
        "<dt>Profile summary</dt><dd>" +
        escapeHtml(profileBasics.profile_summary || "—") +
        "</dd>" +
        "<dt>Contact email</dt><dd>" +
        escapeHtml(profileBasics.contact_email || "—") +
        "</dd>" +
        "<dt>Public website</dt><dd>" +
        escapeHtml(profileBasics.public_website_url || "—") +
        "</dd>" +
        "<dt>Entity type</dt><dd>" +
        escapeHtml(profileBasics.entity_type || "—") +
        "</dd>" +
        "<dt>Profile resolution</dt><dd>" +
        escapeHtml(profileBasics.profile_resolution || "—") +
        "</dd>" +
        "<dt>Publication mode</dt><dd>" +
        escapeHtml(profileBasics.publication_mode || "—") +
        "</dd></dl>";
      var requestedChangeHtml = wb.requested_change
        ? '<section class="v2-card" style="margin-top:12px"><h3>Requested change</h3><pre class="v2-json-panel">' +
          escapeHtml(JSON.stringify(wb.requested_change, null, 2)) +
          "</pre></section>"
        : "";
      var auditHtml = wb.audit
        ? '<section class="v2-card" style="margin-top:12px"><h3>Audit receipt</h3><dl class="v2-surface-dl">' +
          "<dt>Record id</dt><dd><code>" +
          escapeHtml(wb.audit.record_id || "") +
          "</code></dd><dt>Recorded at</dt><dd>" +
          escapeHtml(String(wb.audit.recorded_at_unix_ms != null ? wb.audit.recorded_at_unix_ms : "—")) +
          "</dd><dt>Recovery</dt><dd>" +
          escapeHtml(wb.rollback_reference || "—") +
          "</dd></dl></section>"
        : "";
      var basicsSliceTable =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        basicsSlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML =
        basicsWarningBlock +
        basicsCards +
        basicsDetails +
        requestedChangeHtml +
        auditHtml +
        '<div class="v2-card" style="margin-top:12px"><h3>Visible slices</h3>' +
        basicsSliceTable +
        "</div>";
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
        "<table class=\"v2-table\"><thead><tr><th>Tool</th><th>Slice</th><th>Entrypoint</th><th>Config</th><th>Visibility</th></tr></thead><tbody>" +
        rows
          .map(function (row) {
            return (
              "<tr><td>" +
              escapeHtml(row.label || row.tool_id || "") +
              "</td><td><code>" +
              escapeHtml(row.slice_id || "") +
              "</code></td><td><code>" +
              escapeHtml(row.entrypoint_id || "") +
              "</code></td><td>" +
              escapeHtml(row.config_enabled ? "enabled" : "disabled") +
              "</td><td>" +
              escapeHtml(row.visibility_status || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = bannerHtml + table;
      return;
    }
    if (kind === "datum_workbench") {
      var summ = wb.summary || {};
      var warns = wb.warnings || [];
      var selected = summ.selected_document || {};
      var docs = wb.documents || [];
      var diagnostics = summ.diagnostic_totals || {};
      var diagnosticItems = Object.keys(diagnostics)
        .filter(function (key) {
          return Number(diagnostics[key] || 0) > 0;
        })
        .map(function (key) {
          return "<li><code>" + escapeHtml(String(key)) + "</code>: " + escapeHtml(String(diagnostics[key])) + "</li>";
        })
        .join("");
      var warnBlock =
        warns.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            warns.map(function (w) {
              return "<li>" + escapeHtml(String(w)) + "</li>";
            }).join("") +
            "</ul></div>"
          : "";
      var meta =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rows</h3><p>' +
        escapeHtml(String(summ.row_count != null ? summ.row_count : "—")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Documents</h3><p>' +
        escapeHtml(String(summ.document_count != null ? summ.document_count : "—")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Selected</h3><p>' +
        escapeHtml(String(selected.document_name || "—")) +
        "</p></article></div>";
      var documentsTable =
        "<table class=\"v2-table\"><thead><tr><th>Document</th><th>Source</th><th>Rows</th><th>Issues</th><th>Anchor</th></tr></thead><tbody>" +
        docs
          .map(function (doc) {
            return (
              "<tr><td><code>" +
              escapeHtml(String((doc && doc.document_name) || "")) +
              "</code></td><td>" +
              escapeHtml(String((doc && doc.source_kind) || "")) +
              "</td><td>" +
              escapeHtml(String((doc && doc.row_count) || "0")) +
              "</td><td>" +
              escapeHtml(String((doc && doc.diagnostic_row_count) || "0")) +
              "</td><td>" +
              escapeHtml(String((doc && doc.anchor_document_name) || "—")) +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      var preview = wb.rows_preview || [];
      var table =
        "<table class=\"v2-table\"><thead><tr><th>Address</th><th>Family</th><th>Diagnostics</th><th>Value</th><th>References</th></tr></thead><tbody>" +
        preview
          .map(function (row) {
            var bindings = (row && row.reference_bindings) || [];
            var refText = bindings
              .map(function (binding) {
                var refToken = binding.normalized_reference_form || binding.reference_form || "";
                var valueToken = binding.value_token ? "=" + binding.value_token : "";
                return refToken + valueToken;
              })
              .join(" | ");
            return (
              "<tr><td><code>" +
              escapeHtml(String((row && row.datum_address) || "")) +
              "</code></td><td>" +
              escapeHtml(String((row && row.recognized_family) || "—")) +
              "</td><td>" +
              escapeHtml(String(((row && row.diagnostic_states) || []).join(", ") || "ok")) +
              "</td><td><code>" +
              escapeHtml(String((row && row.primary_value_token) || "—")) +
              "</code></td><td>" +
              escapeHtml(String(refText || "—")) +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML =
        warnBlock +
        meta +
        '<section class="v2-card" style="margin-top:12px"><h3>Documents</h3>' +
        documentsTable +
        "</section>" +
        (diagnosticItems
          ? '<section class="v2-card" style="margin-top:12px"><h3>Diagnostics</h3><ul>' +
            diagnosticItems +
            "</ul></section>"
          : "") +
        '<section class="v2-card" style="margin-top:12px"><h3>Preview</h3>' +
        table +
        "</section>";
      return;
    }
    if (kind === "network_root") {
      var networkTabs = wb.root_tabs || [];
      var networkBlocks = wb.blocks || [];
      var networkNotes = wb.notes || [];
      var activeNetworkTab = wb.root_tab || "messages";
      var networkPanels = wb.tab_panels || {};
      var activeNetworkPanel = networkPanels[activeNetworkTab] || {};
      function renderNetworkSection(section) {
        if (!section) {
          return "";
        }
        var title = escapeHtml(section.title || "Section");
        var emptyText = escapeHtml(section.empty_text || "No entries.");
        var html = '<section class="v2-card" style="margin-top:12px"><h3>' + title + "</h3>";
        if ((section.facts || []).length) {
          html +=
            '<dl class="v2-surface-dl">' +
            (section.facts || [])
              .map(function (fact) {
                return "<dt>" + escapeHtml(fact.label || "") + "</dt><dd>" + escapeHtml(String(fact.value || "—")) + "</dd>";
              })
              .join("") +
            "</dl>";
        }
        if ((section.columns || []).length) {
          var rows = section.rows || [];
          html +=
            '<table class="v2-table"><thead><tr>' +
            (section.columns || [])
              .map(function (column) {
                return "<th>" + escapeHtml(column.label || column.key || "") + "</th>";
              })
              .join("") +
            "</tr></thead><tbody>";
          if (rows.length) {
            html += rows
              .map(function (row) {
                return (
                  "<tr>" +
                  (section.columns || [])
                    .map(function (column) {
                      var key = column.key || "";
                      return "<td>" + escapeHtml(String((row && row[key]) || "—")) + "</td>";
                    })
                    .join("") +
                  "</tr>"
                );
              })
              .join("");
          } else {
            html += '<tr><td colspan="' + escapeHtml(String((section.columns || []).length || 1)) + '">' + emptyText + "</td></tr>";
          }
          html += "</tbody></table>";
        }
        if ((section.entries || []).length) {
          html +=
            "<ul>" +
            (section.entries || [])
              .map(function (entry) {
                var meta = entry.meta ? " <small>" + escapeHtml(String(entry.meta)) + "</small>" : "";
                return "<li><strong>" + escapeHtml(entry.label || "—") + "</strong>" + meta + "</li>";
              })
              .join("") +
            "</ul>";
        } else if (!(section.facts || []).length && !(section.columns || []).length) {
          html += "<p>" + emptyText + "</p>";
        }
        html += "</section>";
        return html;
      }
      var networkTabRow =
        networkTabs.length > 0
          ? '<div class="page-tabs">' +
            networkTabs
              .map(function (tab) {
                return (
                  '<a class="page-tab' +
                  (tab.active ? " is-active" : "") +
                  '" href="' +
                  escapeHtml(tab.href || "#") +
                  '" data-workbench-network-tab="' +
                  escapeHtml(tab.tab_id || "") +
                  '">' +
                  escapeHtml(tab.label || tab.tab_id || "tab") +
                  "</a>"
                );
              })
              .join("") +
            "</div>"
          : "";
      var networkCards =
        '<div class="v2-card-grid">' +
        networkBlocks
          .map(function (block) {
            return (
              '<article class="v2-card"><h3>' +
              escapeHtml(block.label || "Metric") +
              "</h3><p>" +
              escapeHtml(block.value || "—") +
              "</p></article>"
            );
          })
              .join("") +
        "</div>";
      var panelMetrics = activeNetworkPanel.metrics || [];
      var networkPanelMetrics =
        panelMetrics.length > 0
          ? '<div class="v2-card-grid" style="margin-top:12px">' +
            panelMetrics
              .map(function (metric) {
                return (
                  '<article class="v2-card"><h3>' +
                  escapeHtml(metric.label || "Metric") +
                  "</h3><p>" +
                  escapeHtml(String(metric.value || "—")) +
                  "</p></article>"
                );
              })
              .join("") +
            "</div>"
          : "";
      var networkList =
        networkNotes.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Notes</h3><ul>' +
            networkNotes
              .map(function (note) {
                return "<li>" + escapeHtml(String(note)) + "</li>";
              })
              .join("") +
            "</ul></section>"
          : "";
      var networkPanel =
        '<section class="v2-card" style="margin-top:12px"><h3>' +
        escapeHtml(activeNetworkPanel.title || "Network") +
        "</h3><p>" +
        escapeHtml(activeNetworkPanel.summary || "Contract-first network root.") +
        "</p></section>";
      var networkSections = (activeNetworkPanel.sections || []).map(renderNetworkSection).join("");
      body.innerHTML = networkTabRow + networkCards + networkPanel + networkPanelMetrics + networkSections + networkList;
      Array.prototype.forEach.call(body.querySelectorAll("[data-workbench-network-tab]"), function (node) {
        node.addEventListener("click", function (e) {
          e.preventDefault();
          var tabId = node.getAttribute("data-workbench-network-tab") || "";
          var match = networkTabs.filter(function (tab) {
            return String(tab.tab_id || "") === tabId;
          })[0];
          if (match && match.shell_request) loadShell(match.shell_request);
        });
      });
      return;
    }
    if (kind === "cts_gis_workbench") {
      var ctsGisSurface = (lastEnvelope && lastEnvelope.surface_payload) || {};
      var ctsGisWarnings = ctsGisSurface.warnings || wb.warnings || [];
      var ctsGisDocumentCatalog = ctsGisSurface.document_catalog || [];
      var ctsGisSelectedDocument = ctsGisSurface.selected_document || {};
      var ctsGisAttentionProfile = ctsGisSurface.attention_profile || {};
      var ctsGisLineage = ctsGisSurface.lineage || [];
      var ctsGisChildren = ctsGisSurface.children || [];
      var ctsGisRelatedProfiles = ctsGisSurface.related_profiles || [];
      var ctsGisRenderSetSummary = ctsGisSurface.render_set_summary || {};
      var ctsGisSelectedRow = ctsGisSurface.selected_row || {};
      var ctsGisProjection = ctsGisSurface.map_projection || {};
      var ctsGisSelectedFeature = ctsGisProjection.selected_feature || {};
      var ctsGisMediation = ctsGisSurface.mediation_state || wb.mediation_state || {};
      var ctsGisAvailableIntentions = ctsGisMediation.available_intentions || [];
      var ctsGisSelectionSummary = ctsGisMediation.selection_summary || {};
      var ctsGisLens = ctsGisSurface.lens_state || wb.lens_state || {};
      var ctsGisDiagnosticSummary = ctsGisSurface.diagnostic_summary || wb.diagnostic_summary || {};
      var ctsGisRows = ctsGisSurface.rows || [];
      var ctsGisRequestContract = wb.request_contract || {};

      function ctsGisRequestBody(patch) {
        var fixed = ctsGisRequestContract.fixed_request_fields || {};
        var baseMediationState = {
          attention_document_id: ctsGisMediation.attention_document_id || ctsGisSelectedDocument.document_id || "",
          attention_node_id: ctsGisMediation.attention_node_id || "",
          intention_token: ctsGisMediation.intention_token || "0",
        };
        var bodyOut = {
          schema: ctsGisRequestContract.request_schema || "mycite.v2.admin.cts_gis.read_only.request.v1",
          selected_document_id: ctsGisSelectedDocument.document_id || "",
          selected_row_address: ctsGisSelectionSummary.selected_row_address || ctsGisSelectedRow.datum_address || "",
          selected_feature_id: ctsGisSelectionSummary.selected_feature_id || ctsGisSelectedFeature.feature_id || "",
          overlay_mode: ctsGisLens.overlay_mode || "auto",
          raw_underlay_visible: !!ctsGisLens.raw_underlay_visible,
          mediation_state: baseMediationState,
        };
        Object.keys(fixed || {}).forEach(function (key) {
          bodyOut[key] = fixed[key];
        });
        Object.keys(patch || {}).forEach(function (key) {
          if (key === "mediation_state") {
            return;
          }
          if (key === "clear_selection") {
            return;
          }
          bodyOut[key] = patch[key];
        });
        if (patch && patch.mediation_state) {
          Object.keys(patch.mediation_state || {}).forEach(function (key) {
            bodyOut.mediation_state[key] = patch.mediation_state[key];
          });
        }
        if (patch && patch.clear_selection) {
          bodyOut.selected_row_address = "";
          bodyOut.selected_feature_id = "";
        }
        return bodyOut;
      }

      function overlayCellHtml(row) {
        var overlays = row.overlay_preview || [];
        if (!overlays.length) {
          return "<code>" + escapeHtml(row.primary_value_token || "—") + "</code>";
        }
        return overlays
          .map(function (overlay) {
            var display = overlay.display_value || overlay.raw_value || "—";
            var raw = overlay.raw_value || "";
            var title = overlay.anchor_label || overlay.overlay_family || "value";
            var rawHtml =
              ctsGisLens.raw_underlay_visible && raw
                ? '<div><small>raw: <code>' + escapeHtml(raw) + "</code></small></div>"
                : "";
            return (
              '<div style="margin-bottom:6px"><strong>' +
              escapeHtml(String(title).replace(/_/g, " ")) +
              ":</strong> " +
              escapeHtml(display) +
              rawHtml +
              "</div>"
            );
          })
          .join("");
      }

      function profileButtonHtml(profile, attrName, isActive) {
        var label = profile.profile_label || profile.node_id || "profile";
        var meta = profile.feature_count != null ? " (" + String(profile.feature_count) + ")" : "";
        return (
          '<button type="button" class="ide-sessionAction ide-sessionAction--button" ' +
          attrName +
          '="' +
          escapeHtml(profile.node_id || "") +
          '" style="border-radius:6px' +
          (isActive ? ';font-weight:700' : "") +
          '">' +
          escapeHtml(label) +
          meta +
          "</button>"
        );
      }

      var ctsGisWarningBlock =
        ctsGisWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            ctsGisWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var ctsGisCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Attention</h3><p>' +
        escapeHtml(ctsGisAttentionProfile.profile_label || ctsGisAttentionProfile.node_id || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Intention</h3><p>' +
        escapeHtml(String(ctsGisRenderSetSummary.render_mode || ctsGisMediation.intention_token || "—").replace(/_/g, " ")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Features</h3><p>' +
        escapeHtml(String(ctsGisProjection.feature_count != null ? ctsGisProjection.feature_count : "0")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Rows</h3><p>' +
        escapeHtml(String(ctsGisDiagnosticSummary.render_row_count != null ? ctsGisDiagnosticSummary.render_row_count : "0")) +
        "</p></article>" +
        "</div>";
      var lensHtml =
        '<div class="v2-card" style="margin-top:12px"><h3>Lens</h3>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-overlay-mode="auto" style="border-radius:6px' +
        ((ctsGisLens.overlay_mode || "auto") === "auto" ? ';font-weight:700' : "") +
        '">Auto overlay</button>' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-overlay-mode="raw_only" style="border-radius:6px' +
        ((ctsGisLens.overlay_mode || "auto") === "raw_only" ? ';font-weight:700' : "") +
        '">Raw only</button>' +
        '<label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="v2-cts-gis-raw-underlay-toggle"' +
        (ctsGisLens.raw_underlay_visible ? " checked" : "") +
        "> show raw values</label></div></div>";
      var documentButtonStrip =
        ctsGisDocumentCatalog.length > 0
          ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
            ctsGisDocumentCatalog
              .map(function (doc) {
                return (
                  '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-document-id="' +
                  escapeHtml(doc.document_id || "") +
                  '" style="border-radius:6px' +
                  (doc.selected ? ';font-weight:700' : "") +
                  '">' +
                  escapeHtml(doc.document_name || doc.document_id || "document") +
                  " (" +
                  escapeHtml(String(doc.profile_count != null ? doc.profile_count : doc.projectable_feature_count != null ? doc.projectable_feature_count : 0)) +
                  ")</button>"
                );
              })
              .join("") +
            "</div>"
          : "<p>No authoritative CTS-GIS documents are cataloged for this tenant.</p>";
      var lineageHtml =
        ctsGisLineage.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Attention shell</h3><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
            ctsGisLineage
              .map(function (profile) {
                return profileButtonHtml(
                  profile,
                  "data-cts-gis-node-id",
                  !!profile.selected || String(profile.node_id || "") === String(ctsGisMediation.attention_node_id || "")
                );
              })
              .join('<span aria-hidden="true">/</span>') +
            "</div></section>"
          : "";
      var intentionHtml =
        '<section class="v2-card" style="margin-top:12px"><h3>Intention controls</h3>' +
        (ctsGisAvailableIntentions.length > 0
          ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
            ctsGisAvailableIntentions
              .map(function (option) {
                return (
                  '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-cts-gis-intention-token="' +
                  escapeHtml(option.token || "") +
                  '" style="border-radius:6px' +
                  (option.active ? ';font-weight:700' : "") +
                  '">' +
                  escapeHtml(option.label || option.token || "intention") +
                  " (" +
                  escapeHtml(String(option.feature_count != null ? option.feature_count : 0)) +
                  ")</button>"
                );
              })
              .join("") +
            "</div>"
          : "<p>No intention controls are available for the current attention state.</p>") +
        "</section>";
      var documentsSectionHtml =
        '<section class="v2-card" style="margin-top:12px"><h3>Documents</h3>' +
        documentButtonStrip +
        "</section>";
      var attentionProfileHtml =
        ctsGisAttentionProfile && (ctsGisAttentionProfile.node_id || ctsGisAttentionProfile.profile_label)
          ? '<section class="v2-card" style="margin-top:12px"><h3>Attention profile</h3><dl class="v2-surface-dl">' +
            "<dt>Profile</dt><dd>" +
            escapeHtml(ctsGisAttentionProfile.profile_label || "—") +
            "</dd><dt>Node</dt><dd><code>" +
            escapeHtml(ctsGisAttentionProfile.node_id || "—") +
            "</code></dd><dt>Row</dt><dd><code>" +
            escapeHtml(ctsGisAttentionProfile.row_address || "—") +
            "</code></dd><dt>Children</dt><dd>" +
            escapeHtml(String(ctsGisAttentionProfile.child_count != null ? ctsGisAttentionProfile.child_count : "0")) +
            "</dd><dt>Features</dt><dd>" +
            escapeHtml(String(ctsGisAttentionProfile.feature_count != null ? ctsGisAttentionProfile.feature_count : "0")) +
            "</dd></dl></section>'
          : "";
      var childrenHtml =
        '<section class="v2-card" style="margin-top:12px"><h3>Children</h3>' +
        (ctsGisChildren.length > 0
          ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
            ctsGisChildren
              .map(function (profile) {
                return profileButtonHtml(profile, "data-cts-gis-node-id", false);
              })
              .join("") +
            "</div>"
          : "<p>No direct child profiles are available for the current attention node.</p>") +
        "</section>";
      var relatedHtml =
        ctsGisRelatedProfiles.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Related profiles</h3><ul>' +
            ctsGisRelatedProfiles
              .map(function (profile) {
                return (
                  "<li><strong>" +
                  escapeHtml(profile.profile_label || profile.node_id || "profile") +
                  "</strong> <small>" +
                  escapeHtml(profile.relation || "related") +
                  "</small></li>"
                );
              })
              .join("") +
            "</ul></section>"
          : "";
      var selectedFeatureHtml =
        ctsGisSelectedFeature && ctsGisSelectedFeature.feature_id
          ? '<section class="v2-card" style="margin-top:12px"><h3>Selected feature</h3><dl class="v2-surface-dl">' +
            "<dt>Feature</dt><dd><code>" +
            escapeHtml(ctsGisSelectedFeature.feature_id || "") +
            "</code></dd><dt>Geometry</dt><dd>" +
            escapeHtml(ctsGisSelectedFeature.geometry_type || "—") +
            "</dd><dt>Row</dt><dd><code>" +
            escapeHtml(ctsGisSelectedFeature.row_address || "—") +
            "</code></dd><dt>Label</dt><dd>" +
            escapeHtml(ctsGisSelectedFeature.profile_label || ctsGisSelectedFeature.label_text || "—") +
            "</dd><dt>Node</dt><dd><code>" +
            escapeHtml(ctsGisSelectedFeature.samras_node_id || "—") +
            "</dd></dl></section>"
          : "";
      var featureRows = (((ctsGisProjection.feature_collection || {}).features) || []).slice(0, 24);
      var featureTable =
        featureRows.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Features</h3><table class="v2-table"><thead><tr><th>Feature</th><th>Profile</th><th>Geometry</th><th>Row</th></tr></thead><tbody>' +
            featureRows
              .map(function (feature) {
                var props = feature.properties || {};
                return (
                  "<tr><td><a href=\"#\" data-cts-gis-feature-id=\"" +
                  escapeHtml(feature.id || "") +
                  '" data-cts-gis-feature-node-id="' +
                  escapeHtml(props.samras_node_id || "") +
                  "\"><code>" +
                  escapeHtml(feature.id || "") +
                  "</code></a></td><td>" +
                  escapeHtml(props.profile_label || props.label_text || "—") +
                  "</td><td><code>" +
                  escapeHtml((feature.geometry || {}).type || "—") +
                  "</code></td><td><code>" +
                  escapeHtml(props.row_address || "—") +
                  "</td></tr>"
                );
              })
              .join("") +
            "</tbody></table></section>"
          : "";
      var rowTableRows = ctsGisRows.slice(0, 180);
      var rowTable =
        '<details class="v2-card" style="margin-top:12px"><summary>Raw datum underlay</summary><div style="margin-top:12px"><table class="v2-table"><thead><tr><th>Address</th><th>Profile</th><th>Diagnostics</th><th>Overlay values</th></tr></thead><tbody>' +
        rowTableRows
          .map(function (row) {
            return (
              "<tr><td><a href=\"#\" data-cts-gis-row-address=\"" +
              escapeHtml(row.datum_address || "") +
              '" data-cts-gis-row-node-id="' +
              escapeHtml(row.samras_node_id || "") +
              "\"><code>" +
              escapeHtml(row.datum_address || "") +
              "</code></a></td><td>" +
              escapeHtml(row.profile_label || row.label_text || "—") +
              "</td><td>" +
              escapeHtml(((row.diagnostic_states || []).join(", ")) || "ok") +
              "</td><td>" +
              overlayCellHtml(row) +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>" +
        (ctsGisRows.length > rowTableRows.length
          ? '<p class="ide-controlpanel__empty" style="margin-top:8px">Showing first ' +
            escapeHtml(String(rowTableRows.length)) +
            " of " +
            escapeHtml(String(ctsGisRows.length)) +
            " rows.</p>"
          : "") +
        "</div></details>";
      body.innerHTML =
        ctsGisWarningBlock +
        ctsGisCards +
        documentsSectionHtml +
        lineageHtml +
        intentionHtml +
        lensHtml +
        attentionProfileHtml +
        childrenHtml +
        relatedHtml +
        renderCtsGisSvg(ctsGisProjection) +
        selectedFeatureHtml +
        featureTable +
        rowTable;

      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-document-id]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              selected_document_id: el.getAttribute("data-cts-gis-document-id") || "",
              clear_selection: true,
              mediation_state: {
                attention_document_id: el.getAttribute("data-cts-gis-document-id") || "",
                attention_node_id: "",
                intention_token: "",
              },
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-node-id]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              clear_selection: true,
              mediation_state: {
                attention_document_id: ctsGisSelectedDocument.document_id || ctsGisMediation.attention_document_id || "",
                attention_node_id: el.getAttribute("data-cts-gis-node-id") || "",
                intention_token: "0",
              },
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-intention-token]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              clear_selection: true,
              mediation_state: {
                attention_document_id: ctsGisSelectedDocument.document_id || ctsGisMediation.attention_document_id || "",
                attention_node_id: ctsGisMediation.attention_node_id || "",
                intention_token: el.getAttribute("data-cts-gis-intention-token") || "0",
              },
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-row-address]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          var rowNodeId = el.getAttribute("data-cts-gis-row-node-id") || "";
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              selected_row_address: el.getAttribute("data-cts-gis-row-address") || "",
              selected_feature_id: "",
              mediation_state: rowNodeId
                ? {
                    attention_document_id: ctsGisSelectedDocument.document_id || ctsGisMediation.attention_document_id || "",
                    attention_node_id: rowNodeId,
                    intention_token: "0",
                  }
                : undefined,
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-feature-id]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          var featureNodeId = el.getAttribute("data-cts-gis-feature-node-id") || "";
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              selected_feature_id: el.getAttribute("data-cts-gis-feature-id") || "",
              mediation_state: featureNodeId
                ? {
                    attention_document_id: ctsGisSelectedDocument.document_id || ctsGisMediation.attention_document_id || "",
                    attention_node_id: featureNodeId,
                    intention_token: "0",
                  }
                : undefined,
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-cts-gis-overlay-mode]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              overlay_mode: el.getAttribute("data-cts-gis-overlay-mode") || "auto",
            })
          );
        });
      });
      var rawToggle = document.getElementById("v2-cts-gis-raw-underlay-toggle");
      if (rawToggle) {
        rawToggle.addEventListener("change", function () {
          loadRuntimeView(
            ctsGisRequestContract.route || "/portal/api/v2/admin/cts-gis/read-only",
            ctsGisRequestBody({
              raw_underlay_visible: !!rawToggle.checked,
            })
          );
        });
      }
      return;
    }
    if (kind === "fnd_ebi_workbench") {
      var fndSurface = (lastEnvelope && lastEnvelope.surface_payload) || {};
      var fndProfileCards = wb.profile_cards || fndSurface.profile_cards || [];
      var fndOverview = wb.overview || fndSurface.overview || {};
      var fndTraffic = wb.traffic || fndSurface.traffic || {};
      var fndEventsSummary = wb.events_summary || fndSurface.events_summary || {};
      var fndErrorsNoise = wb.errors_noise || fndSurface.errors_noise || {};
      var fndFiles = wb.files || fndSurface.files || {};
      var fndSelectedProfile = wb.selected_profile || fndSurface.selected_profile || {};
      var fndWarnings = wb.warnings || fndSurface.warnings || [];
      var fndRequestContract = wb.request_contract || {};
      var fndYearMonth = fndOverview.year_month || "";

      function fndRequestBody(patch) {
        var fixed = fndRequestContract.fixed_request_fields || {};
        var bodyOut = {
          schema: fndRequestContract.request_schema || "mycite.v2.admin.fnd_ebi.read_only.request.v1",
          selected_domain: fndSurface.selected_domain || fndOverview.domain || "",
          year_month: fndYearMonth,
        };
        Object.keys(fixed || {}).forEach(function (key) {
          bodyOut[key] = fixed[key];
        });
        Object.keys(patch || {}).forEach(function (key) {
          bodyOut[key] = patch[key];
        });
        return bodyOut;
      }

      function fndMetricCard(title, value, detail) {
        return (
          '<article class="v2-card"><h3>' +
          escapeHtml(title) +
          "</h3><p>" +
          escapeHtml(String(value)) +
          "</p>" +
          (detail ? '<p class="ide-controlpanel__empty">' + escapeHtml(detail) + "</p>" : "") +
          "</article>"
        );
      }

      function fndTopListHtml(title, rows, emptyLabel) {
        if (!rows || !rows.length) {
          return (
            '<section class="v2-card fnd-ebi-detail"><h3>' +
            escapeHtml(title) +
            "</h3><p>" +
            escapeHtml(emptyLabel) +
            "</p></section>"
          );
        }
        return (
          '<section class="v2-card fnd-ebi-detail"><h3>' +
          escapeHtml(title) +
          '</h3><ol class="fnd-ebi-list">' +
          rows
            .map(function (row) {
              return (
                "<li><span><code>" +
                escapeHtml(row.key || "—") +
                "</code></span><strong>" +
                escapeHtml(String(row.count != null ? row.count : 0)) +
                "</strong></li>"
              );
            })
            .join("") +
          "</ol></section>"
        );
      }

      function fndTrend(series) {
        if (!series || !series.length) return "—";
        return series
          .map(function (value) {
            var n = Number(value || 0);
            if (n <= 0) return "·";
            if (n < 3) return "▁";
            if (n < 8) return "▃";
            if (n < 16) return "▅";
            return "▇";
          })
          .join("");
      }

      var fndWarningBlock =
        fndWarnings.length > 0
          ? '<section class="v2-card fnd-ebi-detail"><h3>Warnings</h3><ul class="fnd-ebi-warnings">' +
            fndWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></section>"
          : "";
      var fndProfileGallery =
        fndProfileCards.length > 0
          ? '<div class="fnd-ebi-gallery">' +
            fndProfileCards
              .map(function (card) {
                return (
                  '<article class="v2-card fnd-ebi-card" data-fnd-ebi-select-domain="' +
                  escapeHtml(card.domain || "") +
                  '" style="' +
                  (card.selected ? "border-color:#285943;box-shadow:0 0 0 1px rgba(40,89,67,0.22)" : "") +
                  '">' +
                  "<h3>" +
                  escapeHtml(card.domain || "profile") +
                  "</h3>" +
                  '<div class="tool-valueGrid">' +
                  '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">health</dt><dd class="tool-valueGrid__value">' +
                  escapeHtml(card.health_label || "—") +
                  '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">requests</dt><dd class="tool-valueGrid__value">' +
                  escapeHtml(String(card.requests_30d != null ? card.requests_30d : 0)) +
                  '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">events</dt><dd class="tool-valueGrid__value">' +
                  escapeHtml(String(card.events_30d != null ? card.events_30d : 0)) +
                  '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">visitors</dt><dd class="tool-valueGrid__value">' +
                  escapeHtml(String(card.unique_visitors_approx_30d != null ? card.unique_visitors_approx_30d : 0)) +
                  '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">warnings</dt><dd class="tool-valueGrid__value">' +
                  escapeHtml(String(card.warning_count != null ? card.warning_count : 0)) +
                  "</dd></div></div></article>"
                );
              })
              .join("") +
            "</div>"
          : "<p>No FND-EBI profiles are available for this instance.</p>";
      var fndFileRows = [
        { label: "Profile", key: "profile_file" },
        { label: "Access log", key: "access_log" },
        { label: "Error log", key: "error_log" },
        { label: "Events file", key: "events_file" },
      ];
      var fndMetricCards =
        '<div class="v2-card-grid">' +
        fndMetricCard("Requests (30d)", fndTraffic.requests_30d != null ? fndTraffic.requests_30d : 0, "page requests " + String(fndTraffic.real_page_requests_30d != null ? fndTraffic.real_page_requests_30d : 0)) +
        fndMetricCard("Visitors (30d)", fndTraffic.unique_visitors_approx_30d != null ? fndTraffic.unique_visitors_approx_30d : 0, "approximate unique IPs") +
        fndMetricCard("Events (30d)", fndEventsSummary.events_30d != null ? fndEventsSummary.events_30d : 0, "sessions " + String(fndEventsSummary.session_count_approx != null ? fndEventsSummary.session_count_approx : 0)) +
        fndMetricCard("Bot share", Math.round(Number(fndTraffic.bot_share || 0) * 1000) / 10 + "%", "probe count " + String(fndTraffic.suspicious_probe_count != null ? fndTraffic.suspicious_probe_count : 0)) +
        "</div>";

      body.innerHTML =
        fndWarningBlock +
        '<section class="v2-card"><h3>Window</h3><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
        '<label style="display:flex;gap:8px;align-items:center">Month <input id="v2-fnd-ebi-year-month" type="month" value="' +
        escapeHtml(fndYearMonth) +
        '"></label>' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-fnd-ebi-apply-month">Apply</button>' +
        "</div></section>" +
        '<section class="v2-card fnd-ebi-detail"><h3>Profiles</h3>' +
        fndProfileGallery +
        "</section>" +
        fndMetricCards +
        '<section class="v2-card fnd-ebi-detail"><h3>Overview</h3><div class="tool-valueGrid">' +
        '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">domain</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(fndOverview.domain || "—") +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">health</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(fndOverview.health_label || "—") +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">profile file</dt><dd class="tool-valueGrid__value"><code>' +
        escapeHtml(fndOverview.profile_file || "—") +
        '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">site root</dt><dd class="tool-valueGrid__value"><code>' +
        escapeHtml(fndOverview.site_root || "—") +
        '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">analytics root</dt><dd class="tool-valueGrid__value"><code>' +
        escapeHtml(fndOverview.analytics_root || "—") +
        '</code></dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">access seen</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(fndOverview.access_last_seen_utc || "—") +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">events seen</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(fndOverview.events_last_seen_utc || "—") +
        "</dd></div></div></section>" +
        '<section class="v2-card fnd-ebi-detail"><h3>Files</h3><table class="fnd-ebi-table"><thead><tr><th>Source</th><th>State</th><th>Records</th><th>Path</th></tr></thead><tbody>' +
        fndFileRows
          .map(function (row) {
            var fileState = fndFiles[row.key] || {};
            return (
              "<tr><td>" +
              escapeHtml(row.label) +
              "</td><td>" +
              escapeHtml(fileState.state || "—") +
              "</td><td>" +
              escapeHtml(String(fileState.record_count != null ? fileState.record_count : "—")) +
              "</td><td><code>" +
              escapeHtml(fileState.path || "—") +
              "</code></td></tr>"
            );
          })
          .join("") +
        "</tbody></table></section>" +
        '<section class="v2-card fnd-ebi-detail"><h3>Traffic</h3><div class="tool-valueGrid">' +
        '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">24h</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String(fndTraffic.requests_24h != null ? fndTraffic.requests_24h : 0)) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">7d</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String(fndTraffic.requests_7d != null ? fndTraffic.requests_7d : 0)) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">30d trend</dt><dd class="tool-valueGrid__value fnd-ebi-sparkline">' +
        escapeHtml(fndTrend(fndTraffic.trend_30d || [])) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">2xx / 4xx / 5xx</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(
          String(((fndTraffic.response_breakdown || {})["2xx"]) || 0) +
            " / " +
            String(((fndTraffic.response_breakdown || {})["4xx"]) || 0) +
            " / " +
            String(((fndTraffic.response_breakdown || {})["5xx"]) || 0)
        ) +
        "</dd></div></div></section>" +
        fndTopListHtml("Top pages", fndTraffic.top_pages || [], "No recent non-bot page requests.") +
        fndTopListHtml("Top requested paths", fndTraffic.top_requested_paths || [], "No recent path data.") +
        fndTopListHtml("Top referrers", fndTraffic.top_referrers || [], "No recent referrer data.") +
        '<section class="v2-card fnd-ebi-detail"><h3>Events</h3><div class="tool-valueGrid">' +
        '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">24h</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String(fndEventsSummary.events_24h != null ? fndEventsSummary.events_24h : 0)) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">7d</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String(fndEventsSummary.events_7d != null ? fndEventsSummary.events_7d : 0)) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">30d trend</dt><dd class="tool-valueGrid__value fnd-ebi-sparkline">' +
        escapeHtml(fndTrend(fndEventsSummary.trend_30d || [])) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">invalid lines</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String(fndEventsSummary.invalid_line_count != null ? fndEventsSummary.invalid_line_count : 0)) +
        "</dd></div></div></section>" +
        fndTopListHtml(
          "Event types",
          Object.keys(fndEventsSummary.event_type_counts || {}).map(function (key) {
            return { key: key, count: (fndEventsSummary.event_type_counts || {})[key] };
          }),
          "No event types were counted."
        ) +
        '<section class="v2-card fnd-ebi-detail"><h3>Errors and noise</h3><div class="tool-valueGrid">' +
        '<div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">probe routes</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(String((fndErrorsNoise.top_probe_routes || []).length)) +
        '</dd></div><div class="tool-valueGrid__row"><dt class="tool-valueGrid__term">error severities</dt><dd class="tool-valueGrid__value">' +
        escapeHtml(compactJson(fndErrorsNoise.error_severity_counts || {})) +
        "</dd></div></div></section>" +
        fndTopListHtml("Top error routes", fndErrorsNoise.top_error_routes || [], "No recent error routes.") +
        fndTopListHtml("Top probe routes", fndErrorsNoise.top_probe_routes || [], "No suspicious probe routes were counted.");

      Array.prototype.forEach.call(body.querySelectorAll("[data-fnd-ebi-select-domain]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            fndRequestContract.route || "/portal/api/v2/admin/fnd-ebi/read-only",
            fndRequestBody({
              selected_domain: el.getAttribute("data-fnd-ebi-select-domain") || "",
            })
          );
        });
      });
      var fndMonthInput = document.getElementById("v2-fnd-ebi-year-month");
      var fndMonthApply = document.getElementById("v2-fnd-ebi-apply-month");
      function submitFndMonth() {
        loadRuntimeView(
          fndRequestContract.route || "/portal/api/v2/admin/fnd-ebi/read-only",
          fndRequestBody({
            year_month: (fndMonthInput && fndMonthInput.value) || fndYearMonth,
          })
        );
      }
      if (fndMonthApply) {
        fndMonthApply.addEventListener("click", function (ev) {
          ev.preventDefault();
          submitFndMonth();
        });
      }
      if (fndMonthInput) {
        fndMonthInput.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter") {
            ev.preventDefault();
            submitFndMonth();
          }
        });
      }
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
    if (kind === "datum_summary") {
      var selectedDocument = region.selected_document || {};
      var datumWarnings = (region.warnings || [])
        .map(function (warning) {
          return "<li>" + escapeHtml(String(warning)) + "</li>";
        })
        .join("");
      var totals = selectedDocument.diagnostic_totals || {};
      var totalItems = Object.keys(totals)
        .filter(function (key) {
          return Number(totals[key] || 0) > 0;
        })
        .map(function (key) {
          return "<li><code>" + escapeHtml(String(key)) + "</code>: " + escapeHtml(String(totals[key])) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Document</dt><dd><code>" +
        escapeHtml(selectedDocument.document_name || "—") +
        "</code></dd>" +
        "<dt>Relative path</dt><dd><code>" +
        escapeHtml(selectedDocument.relative_path || "—") +
        "</code></dd>" +
        "<dt>Source kind</dt><dd>" +
        escapeHtml(selectedDocument.source_kind || "—") +
        "</dd>" +
        "<dt>Anchor file</dt><dd><code>" +
        escapeHtml(selectedDocument.anchor_document_name || "—") +
        "</code></dd>" +
        "<dt>Anchor resolution</dt><dd>" +
        escapeHtml(selectedDocument.anchor_resolution || "—") +
        "</dd>" +
        "<dt>Rows</dt><dd>" +
        escapeHtml(String(selectedDocument.row_count != null ? selectedDocument.row_count : "—")) +
        "</dd></dl>" +
        (totalItems
          ? '<section class="v2-card" style="margin-top:12px"><h3>Diagnostic totals</h3><ul>' +
            totalItems +
            "</ul></section>"
          : "") +
        (datumWarnings
          ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
            datumWarnings +
            "</ul></section>"
          : "");
      return;
    }
    if (kind === "cts_gis_summary") {
      var mapSurface = (lastEnvelope && lastEnvelope.surface_payload) || {};
      var mapAttentionProfile = mapSurface.attention_profile || {};
      var mapMediationState = mapSurface.mediation_state || {};
      var mapRenderSetSummary = mapSurface.render_set_summary || {};
      var mapSelectedDocument = mapSurface.selected_document || {};
      var mapSelectedFeature = (mapSurface.map_projection || {}).selected_feature || {};
      var mapSelectedRow = mapSurface.selected_row || {};
      var mapDiagnosticSummary = mapSurface.diagnostic_summary || {};
      var mapLensState = mapSurface.lens_state || {};
      var mapWarnings = ((mapSurface.warnings || region.warnings) || [])
        .map(function (warning) {
          return "<li>" + escapeHtml(String(warning)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Document</dt><dd><code>" +
        escapeHtml(mapSelectedDocument.document_name || "—") +
        "</code></dd>" +
        "<dt>Relative path</dt><dd><code>" +
        escapeHtml(mapSelectedDocument.relative_path || "—") +
        "</code></dd>" +
        "<dt>Attention</dt><dd>" +
        escapeHtml(mapAttentionProfile.profile_label || mapAttentionProfile.node_id || "—") +
        "</dd>" +
        "<dt>Intention</dt><dd>" +
        escapeHtml(String(mapRenderSetSummary.render_mode || mapMediationState.intention_token || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Feature count</dt><dd>" +
        escapeHtml(String(mapDiagnosticSummary.render_feature_count != null ? mapDiagnosticSummary.render_feature_count : mapDiagnosticSummary.feature_count != null ? mapDiagnosticSummary.feature_count : "0")) +
        "</dd>" +
        "<dt>Selected feature</dt><dd><code>" +
        escapeHtml(mapSelectedFeature.feature_id || "—") +
        "</code></dd>" +
        "<dt>Selected row</dt><dd><code>" +
        escapeHtml(mapSelectedRow.datum_address || "—") +
        "</code></dd>" +
        "<dt>Overlay mode</dt><dd>" +
        escapeHtml(mapLensState.overlay_mode || "—") +
        "</dd></dl>" +
        '<section class="v2-card" style="margin-top:12px"><h3>Selected row</h3><pre class="v2-json-panel">' +
        escapeHtml(JSON.stringify(mapSelectedRow.raw || mapSelectedRow || {}, null, 2)) +
        "</pre></section>" +
        (mapWarnings
          ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
            mapWarnings +
            "</ul></section>"
          : "");
      return;
    }
    if (kind === "fnd_ebi_summary") {
      var fndSummary = region.summary || {};
      var fndSelectedProfile = region.selected_profile || {};
      var fndInspectorWarnings = (region.warnings || [])
        .map(function (warning) {
          return "<li>" + escapeHtml(String(warning)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Domain</dt><dd><code>" +
        escapeHtml(fndSummary.domain || "—") +
        "</code></dd>" +
        "<dt>Health</dt><dd>" +
        escapeHtml(fndSummary.health_label || "—") +
        "</dd>" +
        "<dt>Month</dt><dd>" +
        escapeHtml(fndSummary.year_month || "—") +
        "</dd>" +
        "<dt>Access state</dt><dd>" +
        escapeHtml(fndSummary.access_state || "—") +
        "</dd>" +
        "<dt>Events state</dt><dd>" +
        escapeHtml(fndSummary.events_state || "—") +
        "</dd>" +
        "<dt>Profile file</dt><dd><code>" +
        escapeHtml(fndSelectedProfile.profile_file || "—") +
        "</code></dd>" +
        "<dt>Site root</dt><dd><code>" +
        escapeHtml(fndSelectedProfile.site_root || "—") +
        "</code></dd>" +
        "<dt>Analytics root</dt><dd><code>" +
        escapeHtml(fndSelectedProfile.analytics_root || "—") +
        "</code></dd></dl>" +
        (fndInspectorWarnings
          ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' +
            fndInspectorWarnings +
            "</ul></section>"
          : "");
      return;
    }
    if (kind === "network_summary") {
      var networkSummary = region.summary || {};
      var networkInstance = region.portal_instance || {};
      var networkNotes = (region.notes || [])
        .map(function (note) {
          return "<li>" + escapeHtml(String(note)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>State</dt><dd>" +
        escapeHtml(region.network_state || "—") +
        "</dd><dt>Active tab</dt><dd>" +
        escapeHtml(region.active_tab || "—") +
        "</dd><dt>Hosted root</dt><dd>" +
        escapeHtml(networkSummary.hosted_root || "—") +
        "</dd><dt>Portal instance</dt><dd><code>" +
        escapeHtml(networkInstance.portal_instance_id || networkSummary.portal_instance_id || "—") +
        "</code></dd><dt>Domain</dt><dd><code>" +
        escapeHtml(networkInstance.domain || networkSummary.domain || "—") +
        "</code></dd><dt>Host aliases</dt><dd>" +
        escapeHtml(String(networkSummary.host_alias_count != null ? networkSummary.host_alias_count : "0")) +
        "</dd><dt>Progeny links</dt><dd>" +
        escapeHtml(String(networkSummary.progeny_link_count != null ? networkSummary.progeny_link_count : "0")) +
        "</dd><dt>P2P contracts</dt><dd>" +
        escapeHtml(String(networkSummary.contract_count != null ? networkSummary.contract_count : "0")) +
        "</dd><dt>Request-log events</dt><dd>" +
        escapeHtml(String(networkSummary.request_log_event_count != null ? networkSummary.request_log_event_count : "0")) +
        "</dd><dt>Local audit</dt><dd>" +
        escapeHtml(networkSummary.local_audit_state || "—") +
        "</dd><dt>Visible utilities</dt><dd>" +
        escapeHtml(String(networkSummary.visible_utility_count != null ? networkSummary.visible_utility_count : "0")) +
        "</dd></dl>" +
        (networkNotes
          ? '<section class="v2-card" style="margin-top:12px"><h3>Notes</h3><ul>' + networkNotes + "</ul></section>"
          : "");
      return;
    }
    if (kind === "aws_csm_family_home") {
      var familyHealth = region.family_health || {};
      var primaryReadOnly = region.primary_read_only || {};
      var domainStates = region.domain_states || [];
      var newsletterContract = region.newsletter_request_contract || {};
      var newsletterFixed = newsletterContract.fixed_request_fields || {};
      var navigation = region.subsurface_navigation || {};
      var gatedSubsurfaces = region.gated_subsurfaces || {};
      var callerIdentity = familyHealth.caller_identity || {};
      var queueHealth = familyHealth.dispatch_queue || {};
      var dispatcherHealth = familyHealth.dispatcher_lambda || {};
      var inboundHealth = familyHealth.inbound_processor_lambda || {};

      function familyNewsletterBody(patch) {
        var bodyOut = {
          schema: newsletterContract.request_schema || "mycite.v2.admin.aws_csm.newsletter.request.v1",
        };
        Object.keys(newsletterFixed || {}).forEach(function (key) {
          bodyOut[key] = newsletterFixed[key];
        });
        Object.keys(patch || {}).forEach(function (key) {
          bodyOut[key] = patch[key];
        });
        return bodyOut;
      }

      var domainSections = domainStates.length
        ? domainStates
            .map(function (state, index) {
              var profile = state.profile || {};
              var readiness = state.readiness || {};
              var latestDispatch = state.latest_dispatch || {};
              var verifiedAuthors = state.verified_author_profiles || [];
              var options = verifiedAuthors
                .map(function (author) {
                  var profileId = author.profile_id || "";
                  return (
                    '<option value="' +
                    escapeHtml(profileId) +
                    '"' +
                    (profileId === (profile.selected_author_profile_id || "") ? " selected" : "") +
                    ">" +
                    escapeHtml((author.send_as_email || profileId || "author") + (author.role ? " · " + author.role : "")) +
                    "</option>"
                  );
                })
                .join("");
              var warnings = (state.warnings || [])
                .map(function (warning) {
                  return "<li>" + escapeHtml(String(warning)) + "</li>";
                })
                .join("");
              return (
                '<section class="v2-card" style="margin-top:12px" data-aws-csm-domain="' +
                escapeHtml(state.domain || "") +
                '">' +
                "<h3>" +
                escapeHtml(state.domain || "domain") +
                "</h3>" +
                '<dl class="v2-surface-dl">' +
                "<dt>Selected author</dt><dd><code>" +
                escapeHtml(profile.selected_author_address || "—") +
                "</code></dd>" +
                "<dt>Contacts</dt><dd>" +
                escapeHtml(String(state.contact_count != null ? state.contact_count : "0")) +
                " total · " +
                escapeHtml(String(state.subscribed_count != null ? state.subscribed_count : "0")) +
                " subscribed</dd>" +
                "<dt>Inbound</dt><dd>" +
                escapeHtml(readiness.inbound_capture_status || "—") +
                "</dd>" +
                "<dt>Dispatch</dt><dd>" +
                escapeHtml(readiness.dispatch_configured ? "configured" : "not configured") +
                "</dd>" +
                "<dt>Latest dispatch</dt><dd><code>" +
                escapeHtml(latestDispatch.dispatch_id || "—") +
                "</code></dd>" +
                "</dl>" +
                (options
                  ? '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
                    '<select data-aws-csm-author-select="' +
                    escapeHtml(state.domain || "") +
                    '" style="min-width:280px;padding:6px 8px">' +
                    options +
                    "</select>" +
                    '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-csm-select-author="' +
                    escapeHtml(state.domain || "") +
                    '" style="border-radius:6px">Select author</button>' +
                    "</div>"
                  : '<p class="ide-controlpanel__empty">No verified authors are available for this domain yet.</p>') +
                '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">' +
                '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-aws-csm-reprocess="' +
                escapeHtml(state.domain || "") +
                '" style="border-radius:6px">Reprocess latest inbound</button>' +
                "</div>" +
                (warnings
                  ? '<section class="v2-card" style="margin-top:12px"><h3>Warnings</h3><ul>' + warnings + "</ul></section>"
                  : "") +
                (index === 0
                  ? '<pre id="v2-aws-csm-newsletter-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>'
                  : "") +
                "</section>"
              );
            })
            .join("")
        : '<section class="v2-card" style="margin-top:12px"><h3>Newsletter operations</h3><p>No newsletter domains are currently visible for this AWS-CSM family surface.</p></section>';

      content.innerHTML =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Mailbox readiness</h3><p>' +
        escapeHtml(primaryReadOnly.mailbox_readiness || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Verified sender</h3><p><code>' +
        escapeHtml(primaryReadOnly.selected_verified_sender || "") +
        "</code></p></article>" +
        '<article class="v2-card"><h3>Queue</h3><p>' +
        escapeHtml(queueHealth.status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Inbound rules</h3><p>' +
        escapeHtml(String((familyHealth.receipt_rules || []).filter(function (row) { return row.status === "ok"; }).length)) +
        " ready</p></article>" +
        "</div>" +
        '<section class="v2-card" style="margin-top:12px"><h3>Family health</h3><dl class="v2-surface-dl">' +
        "<dt>STS identity</dt><dd><code>" +
        escapeHtml(callerIdentity.arn || callerIdentity.status || "—") +
        "</code></dd>" +
        "<dt>Ready domains</dt><dd>" +
        escapeHtml(String(familyHealth.ready_domain_count != null ? familyHealth.ready_domain_count : "0")) +
        " / " +
        escapeHtml(String(familyHealth.domain_count != null ? familyHealth.domain_count : "0")) +
        "</dd>" +
        "<dt>Dispatch queue</dt><dd>" +
        escapeHtml(queueHealth.status || "—") +
        "</dd>" +
        "<dt>Dispatcher Lambda</dt><dd>" +
        escapeHtml(dispatcherHealth.status || "—") +
        "</dd>" +
        "<dt>Inbound Lambda</dt><dd>" +
        escapeHtml(inboundHealth.status || "—") +
        "</dd>" +
        "</dl></section>" +
        '<section class="v2-card" style="margin-top:12px"><h3>Family navigation</h3><div style="display:flex;gap:8px;flex-wrap:wrap">' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-read-only" style="border-radius:6px">Open read-only overview</button>' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-write" style="border-radius:6px">Open sender selection</button>' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-onboarding" style="border-radius:6px">Open onboarding</button>' +
        (gatedSubsurfaces.sandbox
          ? '<span class="ide-controlpanel__empty" style="align-self:center">Sandbox is intentionally gated for this instance.</span>'
          : '<button type="button" class="ide-sessionAction ide-sessionAction--button" id="v2-aws-csm-open-sandbox" style="border-radius:6px">Open sandbox</button>') +
        "</div></section>" +
        domainSections;

      var resultPanel = document.getElementById("v2-aws-csm-newsletter-result");

      function submitNewsletterAction(bodyPatch) {
        if (!newsletterContract.route) return Promise.resolve();
        if (resultPanel) {
          resultPanel.hidden = false;
          resultPanel.textContent = "…";
        }
        return postJson(newsletterContract.route, familyNewsletterBody(bodyPatch)).then(function (res) {
          if (resultPanel) resultPanel.textContent = JSON.stringify(res.json, null, 2);
          if (res.ok && lastShellRequest) {
            return loadShell(cloneRequestWithoutChrome(lastShellRequest));
          }
          return Promise.resolve();
        });
      }

      var readOnlyButton = document.getElementById("v2-aws-csm-open-read-only");
      if (readOnlyButton) {
        readOnlyButton.addEventListener("click", function (ev) {
          ev.preventDefault();
          postJson("/portal/api/v2/admin/aws/read-only", {
            schema: "mycite.v2.admin.aws.read_only.request.v1",
            tenant_scope: newsletterFixed.tenant_scope || {},
          }).then(function (res) {
            if (resultPanel) {
              resultPanel.hidden = false;
              resultPanel.textContent = JSON.stringify(res.json, null, 2);
            }
          });
        });
      }
      var writeButton = document.getElementById("v2-aws-csm-open-write");
      if (writeButton) {
        writeButton.addEventListener("click", function (ev) {
          ev.preventDefault();
          if (navigation.narrow_write_shell_request) loadShell(navigation.narrow_write_shell_request);
        });
      }
      var onboardingButton = document.getElementById("v2-aws-csm-open-onboarding");
      if (onboardingButton) {
        onboardingButton.addEventListener("click", function (ev) {
          ev.preventDefault();
          if (navigation.onboarding_shell_request) loadShell(navigation.onboarding_shell_request);
        });
      }
      var sandboxButton = document.getElementById("v2-aws-csm-open-sandbox");
      if (sandboxButton) {
        sandboxButton.addEventListener("click", function (ev) {
          ev.preventDefault();
          if (navigation.sandbox_shell_request) loadShell(navigation.sandbox_shell_request);
        });
      }
      Array.prototype.forEach.call(content.querySelectorAll("[data-aws-csm-select-author]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          var domain = el.getAttribute("data-aws-csm-select-author") || "";
          var select = content.querySelector('[data-aws-csm-author-select="' + domain.replace(/"/g, '\\"') + '"]');
          var profileId = select ? select.value : "";
          submitNewsletterAction({
            domain: domain,
            action: "select_author",
            selected_author_profile_id: profileId,
          });
        });
      });
      Array.prototype.forEach.call(content.querySelectorAll("[data-aws-csm-reprocess]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          submitNewsletterAction({
            domain: el.getAttribute("data-aws-csm-reprocess") || "",
            action: "reprocess_latest_inbound",
          });
        });
      });
      return;
    }
    if (kind === "aws_read_only_surface") {
      var ps = region.profile_summary || {};
      var doms = (region.allowed_send_domains || []).join(", ");
      var cw = (region.compatibility_warnings || [])
        .map(function (w) {
          return "<li>" + escapeHtml(String(w)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Tenant scope</dt><dd>" +
        escapeHtml(region.tenant_scope_id || "—") +
        "</dd>" +
        "<dt>Mailbox readiness</dt><dd>" +
        escapeHtml(region.mailbox_readiness || "—") +
        "</dd>" +
        "<dt>SMTP</dt><dd>" +
        escapeHtml(region.smtp_state || "—") +
        "</dd>" +
        "<dt>Gmail</dt><dd>" +
        escapeHtml(region.gmail_state || "—") +
        "</dd>" +
        "<dt>Verified sender</dt><dd><code>" +
        escapeHtml(region.selected_verified_sender || "") +
        "</code></dd>" +
        "<dt>Allowed send domains</dt><dd>" +
        escapeHtml(doms || "—") +
        "</dd>" +
        "<dt>Profile</dt><dd>" +
        escapeHtml(ps.profile_id || "—") +
        " · " +
        escapeHtml(ps.domain || "—") +
        "</dd>" +
        "<dt>Write capability</dt><dd>" +
        escapeHtml(region.write_capability || "—") +
        "</dd></dl>" +
        (cw ? "<section class=\"v2-card\" style=\"margin-top:12px\"><h3>Compatibility</h3><ul>" + cw + "</ul></section>" : "");
      return;
    }
    if (kind === "aws_tool_error") {
      var wn = (region.warnings || [])
        .map(function (w) {
          return "<li>" + escapeHtml(String(w)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<div class="v2-card" style="border-color:#c5221f"><h3>' +
        escapeHtml(region.error_code || "error") +
        "</h3><p>" +
        escapeHtml(region.error_message || "") +
        "</p>" +
        (wn ? "<ul>" + wn + "</ul>" : "") +
        "</div>";
      return;
    }
    if (kind === "tenant_profile_summary") {
      var summary = region.summary || {};
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Profile title</dt><dd>" +
        escapeHtml(summary.profile_title || "—") +
        "</dd>" +
        "<dt>Tenant</dt><dd>" +
        escapeHtml(summary.tenant_id || "—") +
        "</dd>" +
        "<dt>Domain</dt><dd>" +
        escapeHtml(summary.tenant_domain || "—") +
        "</dd>" +
        "<dt>Entity type</dt><dd>" +
        escapeHtml(summary.entity_type || "—") +
        "</dd>" +
        "<dt>Profile summary</dt><dd>" +
        escapeHtml(summary.profile_summary || "—") +
        "</dd>" +
        "<dt>Contact email</dt><dd>" +
        escapeHtml(summary.contact_email || "—") +
        "</dd>" +
        "<dt>Public website</dt><dd>" +
        escapeHtml(summary.public_website_url || "—") +
        "</dd>" +
        "<dt>Available documents</dt><dd>" +
        escapeHtml((summary.available_documents || []).join(", ") || "—") +
        "</dd></dl>";
      return;
    }
    if (kind === "operational_status_summary") {
      var operational = region.audit_persistence || {};
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Rollout band</dt><dd>" +
        escapeHtml(region.current_rollout_band || "—") +
        "</dd>" +
        "<dt>Exposure</dt><dd>" +
        escapeHtml(region.exposure_status || "—") +
        "</dd>" +
        "<dt>Read/write posture</dt><dd>" +
        escapeHtml(region.read_write_posture || "—") +
        "</dd>" +
        "<dt>Audit health</dt><dd>" +
        escapeHtml(String(operational.health_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Storage state</dt><dd>" +
        escapeHtml(String(operational.storage_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Recent records</dt><dd>" +
        escapeHtml(String(operational.recent_record_count != null ? operational.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest persisted at</dt><dd>" +
        escapeHtml(
          String(
            operational.latest_recorded_at_unix_ms != null
              ? operational.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>";
      return;
    }
    if (kind === "audit_activity_summary") {
      var activity = region.recent_activity || {};
      var previewRecords = activity.records || [];
      var previewHtml =
        previewRecords.length > 0
          ? "<section class=\"v2-card\" style=\"margin-top:12px\"><h3>Latest records</h3><ul>" +
            previewRecords
              .slice(0, 5)
              .map(function (record) {
                return (
                  "<li><strong>" +
                  escapeHtml(record.event_type || "event") +
                  "</strong> · " +
                  escapeHtml(String(record.recorded_at_unix_ms != null ? record.recorded_at_unix_ms : "—")) +
                  " · <code>" +
                  escapeHtml(record.focus_subject || "") +
                  "</code></li>"
                );
              })
              .join("") +
            "</ul></section>"
          : "";
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Rollout band</dt><dd>" +
        escapeHtml(region.current_rollout_band || "—") +
        "</dd>" +
        "<dt>Exposure</dt><dd>" +
        escapeHtml(region.exposure_status || "—") +
        "</dd>" +
        "<dt>Read/write posture</dt><dd>" +
        escapeHtml(region.read_write_posture || "—") +
        "</dd>" +
        "<dt>Activity state</dt><dd>" +
        escapeHtml(String(activity.activity_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Recent records</dt><dd>" +
        escapeHtml(String(activity.recent_record_count != null ? activity.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest recorded at</dt><dd>" +
        escapeHtml(
          String(
            activity.latest_recorded_at_unix_ms != null
              ? activity.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>" +
        previewHtml;
      return;
    }
    if (kind === "profile_basics_write_form") {
      var contract = region.submit_contract || {};
      var initial = contract.initial_values || {};
      var fixed = contract.fixed_request_fields || {};
      var html =
        '<form id="v2-profile-basics-form" class="v2-card" style="max-width:620px">' +
        "<h3>Profile basics</h3>" +
        '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
        escapeHtml(contract.request_schema || "") +
        "</code></p>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_title</label>' +
        '<input name="profile_title" value="' +
        escapeHtml(initial.profile_title || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_summary</label>' +
        '<textarea name="profile_summary" style="width:100%;min-height:96px;box-sizing:border-box;margin-bottom:10px;padding:6px 8px">' +
        escapeHtml(initial.profile_summary || "") +
        "</textarea>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">contact_email</label>' +
        '<input name="contact_email" value="' +
        escapeHtml(initial.contact_email || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">public_website_url</label>' +
        '<input name="public_website_url" value="' +
        escapeHtml(initial.public_website_url || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
        '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply profile update</button>' +
        "</form>" +
        '<pre id="v2-profile-basics-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
      content.innerHTML = html;
      var form = document.getElementById("v2-profile-basics-form");
      var out = document.getElementById("v2-profile-basics-result");
      if (form && out) {
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var fd = new FormData(form);
          var body = {
            schema: contract.request_schema,
            profile_title: (fd.get("profile_title") || "").toString().trim(),
            profile_summary: (fd.get("profile_summary") || "").toString().trim(),
            contact_email: (fd.get("contact_email") || "").toString().trim(),
            public_website_url: (fd.get("public_website_url") || "").toString().trim(),
          };
          Object.keys(fixed || {}).forEach(function (key) {
            body[key] = fixed[key];
          });
          out.hidden = false;
          out.textContent = "…";
          postJson(contract.route || "/portal/api/v2/tenant/profile-basics", body).then(function (res) {
            out.textContent = JSON.stringify(res.json, null, 2);
            if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
          });
        });
      }
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
            if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
          });
        });
      }
      return;
    }
    if (kind === "csm_onboarding_form") {
      var contract = region.submit_contract || {};
      var initial = contract.initial_values || {};
      var fixed = contract.fixed_request_fields || {};
      var options = contract.onboarding_action_options || [];
      var optHtml = options
        .map(function (a) {
          return (
            '<option value="' +
            escapeHtml(a) +
            '"' +
            (a === (initial.onboarding_action || "") ? " selected" : "") +
            ">" +
            escapeHtml(a) +
            "</option>"
          );
        })
        .join("");
      var html =
        '<form id="v2-csm-onboarding-form" class="v2-card" style="max-width:560px">' +
        "<h3>AWS-CSM onboarding</h3>" +
        '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
        escapeHtml(contract.request_schema || "") +
        "</code></p>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">onboarding_action</label>' +
        '<select name="onboarding_action" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px">' +
        optHtml +
        "</select>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
        '<input name="profile_id" value="' +
        escapeHtml(initial.profile_id || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
        '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply onboarding step</button>' +
        "</form>" +
        '<pre id="v2-csm-onboarding-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
      content.innerHTML = html;
      var form = document.getElementById("v2-csm-onboarding-form");
      var out = document.getElementById("v2-csm-onboarding-result");
      if (form && out) {
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var fd = new FormData(form);
          var body = {
            schema: contract.request_schema,
            profile_id: (fd.get("profile_id") || "").toString().trim(),
            onboarding_action: (fd.get("onboarding_action") || "").toString().trim(),
          };
          if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
          if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
          out.hidden = false;
          out.textContent = "…";
          postJson(contract.route || "/portal/api/v2/admin/aws/csm-onboarding", body).then(function (res) {
            out.textContent = JSON.stringify(res.json, null, 2);
            if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
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

  function applyEnvelope(env, options) {
    if (!env || env.schema !== RUNTIME_ENVELOPE_SCHEMA) {
      showFatal("Invalid runtime envelope schema from shell route.");
      return;
    }
    var comp = env.shell_composition;
    if (!comp || !comp.regions) {
      showFatal("Runtime envelope is missing shell_composition.regions.");
      return;
    }
    if (options && options.trackDirectView) {
      lastDirectView = {
        url: options.url,
        requestBody: JSON.parse(JSON.stringify(options.requestBody || {})),
      };
    } else if (options && options.clearDirectView) {
      lastDirectView = null;
    }
    lastEnvelope = env;
    applyChrome(comp);
    lastComposition = comp;
    if (window.PortalShell && typeof window.PortalShell.rebalanceWorkbench === "function") {
      window.PortalShell.rebalanceWorkbench();
    }
    var act = comp.regions.activity_bar || {};
    renderActivityItems(act.items);
    renderControlPanel(comp.regions.control_panel);
    renderWorkbench(comp.regions.workbench);
    renderInspector(comp.regions.inspector);
    return env;
  }

  function loadShell(requestBody) {
    lastShellRequest = requestBody;
    lastDirectView = null;
    return postJson(SHELL_URL, requestBody).then(function (r) {
      var env = r.json;
      if (!r.ok || !env) {
        showFatal(
          "Shell POST failed (HTTP " +
            r.status +
            "). Check auth, nginx upstream (6101), and service logs. " +
            (r.bodySnippet ? "Body: " + r.bodySnippet : "")
        );
        return;
      }
      return applyEnvelope(env, { clearDirectView: true });
    });
  }

  function loadRuntimeView(url, requestBody) {
    return postJson(url, requestBody).then(function (r) {
      var env = r.json;
      if (!r.ok || !env) {
        showFatal(
          "Runtime POST failed (HTTP " +
            r.status +
            "). " +
            (r.bodySnippet ? "Body: " + r.bodySnippet : "")
        );
        return;
      }
      return applyEnvelope(env, { trackDirectView: true, url: url, requestBody: requestBody });
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

    document.addEventListener("mycite:v2:inspector-dismiss-request", function () {
      postShellChrome({ inspector_collapsed: true });
    });
    document.addEventListener("mycite:v2:inspector-toggle-request", function () {
      var collapsed = !!(lastComposition && lastComposition.inspector_collapsed);
      postShellChrome({ inspector_collapsed: !collapsed });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
