/**
 * Activity bar and control-panel renderers for the V2 portal shell.
 * Keeps shell core focused on orchestration and runtime validation.
 */
(function () {
  var api = window.PortalShellRegionRenderers || (window.PortalShellRegionRenderers = {});

  function activityIconMarkup(item, escapeHtml) {
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

  function renderControlPanelTabs(region, escapeHtml) {
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

  function renderControlPanelSection(sec, secIndex, escapeHtml) {
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

  function renderModule(title, subtitle, region, escapeHtml) {
    return (
      '<div class="ide-controlpanel__module">' +
      '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">' +
      escapeHtml(title) +
      "</div><div class=\"ide-controlpanel__moduleSub\">" +
      escapeHtml(subtitle) +
      "</div></div>" +
      renderControlPanelTabs(region, escapeHtml) +
      (region.sections || [])
        .map(function (section, index) {
          return renderControlPanelSection(section, index, escapeHtml);
        })
        .join("") +
      "</div>"
    );
  }

  api.renderActivityBar = function (ctx) {
    var region = ctx.region || {};
    var escapeHtml = ctx.escapeHtml;
    var loadShell = ctx.loadShell;
    var nav = document.getElementById("v2-activity-nav");
    var items = region.items || [];
    if (!nav) return;
    if (!items.length) {
      nav.innerHTML =
        '<p class="ide-sessionLine ide-sessionLine--dim" style="padding:8px;text-align:center;font-size:10px">No activity items from shell composition.</p>';
      return;
    }
    nav.innerHTML = "";
    items.forEach(function (item) {
      var link = document.createElement("a");
      link.className =
        "ide-activitylink ide-activitylink--" +
        escapeHtml((item.nav_kind || "tool").replace(/[^a-z_-]/gi, "").toLowerCase()) +
        (item.active ? " is-active" : "");
      link.href = item.href || "#";
      link.setAttribute("aria-label", item.aria_label || item.label || "");
      link.setAttribute("title", item.aria_label || item.label || "");
      link.innerHTML =
        activityIconMarkup(item, escapeHtml) +
        '<span class="ide-activitylabel">' +
        escapeHtml(item.label || "") +
        "</span>";
      link.addEventListener("click", function (event) {
        event.preventDefault();
        if (!item.shell_request) return;
        loadShell(item.shell_request);
      });
      nav.appendChild(link);
    });
  };

  api.renderControlPanel = function (ctx) {
    var region = ctx.region || {};
    var root = ctx.target || document.getElementById("portalControlPanel");
    var escapeHtml = ctx.escapeHtml;
    var loadShell = ctx.loadShell;
    var kind = region.kind || "";
    if (!root) return;

    if (kind === "system_control_panel") {
      root.innerHTML = renderModule(
        "SYSTEM",
        "Core sandbox and datum-facing workbench.",
        region,
        escapeHtml
      );
    } else if (kind === "network_control_panel") {
      root.innerHTML = renderModule(
        "NETWORK",
        "Scaffolded hosted and relationship root.",
        region,
        escapeHtml
      );
    } else if (kind === "utilities_control_panel") {
      root.innerHTML = renderModule(
        "UTILITIES",
        "Tool management, config, and follow-on utility tabs.",
        region,
        escapeHtml
      );
    } else if (kind === "aws_csm_control_panel") {
      root.innerHTML = renderModule(
        "AWS-CSM",
        "Family-local domain and mailbox context.",
        region,
        escapeHtml
      );
    } else if ((region.sections || []).length) {
      root.innerHTML = (region.sections || [])
        .map(function (section, index) {
          return renderControlPanelSection(section, index, escapeHtml);
        })
        .join("");
    } else {
      root.innerHTML =
        '<section class="ide-controlpanel__section"><header class="ide-controlpanel__title">Context</header><div class="ide-controlpanel__empty">No page-specific control panel is available.</div></section>';
    }

    Array.prototype.forEach.call(root.querySelectorAll("[data-controlpanel-tab-id], .ide-controlpanel__link"), function (node) {
      node.addEventListener("click", function (event) {
        event.preventDefault();
        var shellRequest = null;
        if (node.hasAttribute("data-controlpanel-tab-id")) {
          var tabId = node.getAttribute("data-controlpanel-tab-id") || "";
          var tabs = region.tabs || [];
          var tabMatch = tabs.filter(function (tab) {
            return String(tab.tab_id || "") === tabId;
          })[0];
          shellRequest = tabMatch && tabMatch.shell_request;
        } else {
          var secIndex = Number(node.getAttribute("data-controlpanel-section-index") || "-1");
          var entryIndex = Number(node.getAttribute("data-controlpanel-entry-index") || "-1");
          var section = ((region.sections || [])[secIndex] || {});
          var entry = ((section.entries || [])[entryIndex] || {});
          shellRequest = entry && entry.shell_request;
        }
        if (shellRequest) {
          loadShell(shellRequest);
        }
      });
    });
  };
})();
