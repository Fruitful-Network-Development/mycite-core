/**
 * Activity bar and control-panel renderers for the one-shell portal.
 */
(function () {
  var api = window.PortalShellRegionRenderers || (window.PortalShellRegionRenderers = {});

  function activityIconMarkup(iconId) {
    var id = String(iconId || "generic");
    var svg = "";
    if (id === "system") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7.5h16v9H4z"></path><path d="M8 16.5h8"></path><path d="M10 4.5h4"></path>' +
        "</svg>";
    } else if (id === "network") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="6" cy="12" r="2.2"></circle><circle cx="18" cy="6" r="2.2"></circle><circle cx="18" cy="18" r="2.2"></circle>' +
        '<path d="M8 11l7.8-4"></path><path d="M8 13l7.8 4"></path>' +
        "</svg>";
    } else if (id === "utilities") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7h16v10H4z"></path><path d="M9 7V5.5h6V7"></path><path d="M12 11v5"></path><path d="M9.5 13.5h5"></path>' +
        "</svg>";
    } else if (id === "aws") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M7.5 17.5h8a4 4 0 0 0 .7-7.94A5.2 5.2 0 0 0 6.7 8.5 3.6 3.6 0 0 0 7.5 17.5z"></path>' +
        '<path d="M8 20c2 .9 5 .9 8 0"></path>' +
        "</svg>";
    } else if (id === "cts_gis") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 20s5-4.3 5-9a5 5 0 1 0-10 0c0 4.7 5 9 5 9z"></path><circle cx="12" cy="11" r="1.8"></circle>' +
        "</svg>";
    } else if (id === "fnd_ebi") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4.5 6.5h15"></path><path d="M4.5 12h15"></path><path d="M4.5 17.5h9"></path>' +
        '<path d="M17 16l2.5 2.5"></path><circle cx="14.5" cy="13.5" r="3.5"></circle>' +
        "</svg>";
    } else {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="12" cy="12" r="8"></circle>' +
        "</svg>";
    }
    return '<span class="ide-activityicon" aria-hidden="true">' + svg + "</span>";
  }

  function bindSurfaceNavigation(node, entry, ctx) {
    if (!node || !entry) return;
    node.addEventListener("click", function (event) {
      if (entry.shell_request) {
        event.preventDefault();
        ctx.loadShell(entry.shell_request);
      }
    });
  }

  api.renderActivityBar = function (ctx) {
    var region = ctx.region || {};
    var nav = ctx.target || document.getElementById("v2-activity-nav");
    var items = region.items || [];
    if (!nav) return;
    if (!items.length) {
      nav.innerHTML = '<p class="ide-sessionLine ide-sessionLine--dim" style="padding:8px;text-align:center;font-size:10px">No surfaces.</p>';
      return;
    }
    nav.innerHTML = "";
    items.forEach(function (item) {
      var link = document.createElement("a");
      link.className = "ide-activitylink" + (item.active ? " is-active" : "");
      link.href = item.href || "#";
      link.setAttribute("aria-label", item.label || "");
      link.setAttribute("title", item.label || "");
      link.innerHTML = activityIconMarkup(item.icon_id);
      bindSurfaceNavigation(link, item, ctx);
      nav.appendChild(link);
    });
  };

  function renderEntry(entry, escapeHtml) {
    var meta = entry.meta ? '<small>' + escapeHtml(entry.meta) + "</small>" : "";
    return (
      '<a class="ide-controlpanel__link' +
      (entry.active ? " is-active" : "") +
      '" href="' +
      escapeHtml(entry.href || "#") +
      '">' +
      "<span>" +
      escapeHtml(entry.label || "") +
      "</span>" +
      meta +
      "</a>"
    );
  }

  function renderFacts(facts, escapeHtml) {
    if (!facts || !facts.length) return "";
    return (
      '<dl class="v2-surface-dl">' +
      facts
        .map(function (fact) {
          return (
            "<dt>" +
            escapeHtml(fact.label || "") +
            "</dt><dd><strong>" +
            escapeHtml(fact.value || "—") +
            "</strong>" +
            (fact.detail ? "<br />" + escapeHtml(fact.detail) : "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function renderSelectionEntry(entry, escapeHtml) {
    var meta = entry.meta ? '<small>' + escapeHtml(entry.meta) + "</small>" : "";
    var prefix = entry.prefix ? '<span class="ide-controlpanel__entryPrefix">' + escapeHtml(entry.prefix) + "</span>" : "";
    var body =
      '<span class="ide-controlpanel__entryBody">' +
      prefix +
      '<span class="ide-controlpanel__entryLabel">' +
      escapeHtml(entry.label || "") +
      "</span>" +
      meta +
      "</span>";
    if (entry.shell_request || entry.href) {
      return (
        '<a class="ide-controlpanel__selectionEntry' +
        (entry.active ? " is-active" : "") +
        '" href="' +
        escapeHtml(entry.href || "#") +
        '">' +
        body +
        "</a>"
      );
    }
    return (
      '<div class="ide-controlpanel__selectionEntry is-static' +
      (entry.active ? " is-active" : "") +
      '">' +
      body +
      "</div>"
    );
  }

  function renderFocusSelectionPanel(ctx, root, region) {
    var contextItems = region.context_items || [];
    var verbTabs = region.verb_tabs || [];
    var groups = region.groups || [];
    var actions = region.actions || [];
    root.innerHTML =
      '<section class="ide-controlpanel__selectionPanel">' +
      '<header class="ide-controlpanel__selectionHeader">' +
      '<div class="ide-controlpanel__title">' +
      ctx.escapeHtml(region.title || "Control Panel") +
      '</div><div class="ide-controlpanel__surfaceLabel">' +
      ctx.escapeHtml(region.surface_label || "") +
      "</div></header>" +
      '<div class="ide-controlpanel__contextRows">' +
      contextItems
        .map(function (item) {
          return (
            '<div class="ide-controlpanel__contextRow">' +
            '<span class="ide-controlpanel__contextKey">' +
            ctx.escapeHtml(item.label || "") +
            ':</span><span class="ide-controlpanel__contextValue">' +
            ctx.escapeHtml(item.value || "—") +
            "</span></div>"
          );
        })
        .join("") +
      "</div>" +
      (verbTabs.length
        ? '<div class="ide-controlpanel__verbTabs">' +
          verbTabs
            .map(function (tab, index) {
              return (
                '<button type="button" class="ide-controlpanel__verbTab' +
                (tab.active ? " is-active" : "") +
                '" data-control-verb-index="' +
                String(index) +
                '">' +
                ctx.escapeHtml(tab.label || "") +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : "") +
      groups
        .map(function (group) {
          return (
            '<section class="ide-controlpanel__selectionGroup">' +
            (group.title
              ? '<header class="ide-controlpanel__selectionGroupTitle">' + ctx.escapeHtml(group.title) + "</header>"
              : "") +
            '<div class="ide-controlpanel__selectionList">' +
            (group.entries || [])
              .map(function (entry) {
                return renderSelectionEntry(entry, ctx.escapeHtml);
              })
              .join("") +
            "</div></section>"
          );
        })
        .join("") +
      (actions.length
        ? '<div class="ide-controlpanel__actions">' +
          actions
            .map(function (action, index) {
              return (
                '<button type="button" class="ide-controlpanel__action ide-controlpanel__action--full" data-control-action-index="' +
                String(index) +
                '">' +
                ctx.escapeHtml(action.label || "") +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : "") +
      "</section>";

    Array.prototype.forEach.call(root.querySelectorAll("[data-control-verb-index]"), function (node) {
      var index = Number(node.getAttribute("data-control-verb-index"));
      var entry = verbTabs[index];
      bindSurfaceNavigation(node, entry, ctx);
    });
    var flatEntries = [];
    groups.forEach(function (group) {
      (group.entries || []).forEach(function (entry) {
        flatEntries.push(entry);
      });
    });
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__selectionEntry"), function (node, index) {
      bindSurfaceNavigation(node, flatEntries[index], ctx);
    });
    Array.prototype.forEach.call(root.querySelectorAll("[data-control-action-index]"), function (node) {
      node.addEventListener("click", function () {
        var index = Number(node.getAttribute("data-control-action-index"));
        var action = actions[index] || {};
        if (action.action_kind === "copy_text" && action.value) {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard.writeText(String(action.value)).catch(function () {});
          }
        }
      });
    });
  }

  api.renderControlPanel = function (ctx) {
    var region = ctx.region || {};
    var root = ctx.target || document.getElementById("portalControlPanel");
    if (!root) return;
    if (region.kind === "focus_selection_panel") {
      renderFocusSelectionPanel(ctx, root, region);
      return;
    }
    var sections = region.sections || [];
    root.innerHTML =
      '<section class="ide-controlpanel__section">' +
      '<header class="ide-controlpanel__title">' +
      ctx.escapeHtml(region.title || "Context") +
      "</header>" +
      sections
        .map(function (section) {
          return (
            '<div class="ide-controlpanel__module' +
            (section.compressed ? " is-compressed" : "") +
            '">' +
            '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">' +
            ctx.escapeHtml(section.title || "Section") +
            "</div></div>" +
            renderFacts(section.facts || [], ctx.escapeHtml) +
            '<ul class="ide-controlpanel__list">' +
            (section.entries || [])
              .map(function (entry) {
                return "<li>" + renderEntry(entry, ctx.escapeHtml) + "</li>";
              })
              .join("") +
            "</ul></div>"
          );
        })
        .join("") +
      "</section>";
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__link"), function (link, index) {
      var flatEntries = [];
      sections.forEach(function (section) {
        (section.entries || []).forEach(function (entry) {
          flatEntries.push(entry);
        });
      });
      bindSurfaceNavigation(link, flatEntries[index], ctx);
    });
  };
})();
