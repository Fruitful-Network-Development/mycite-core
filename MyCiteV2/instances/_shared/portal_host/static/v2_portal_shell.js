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

  function renderMapsSvg(mapProjection) {
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
        var stroke = selected ? "#0b57d0" : "#285943";
        var fill = selected ? "rgba(11,87,208,0.28)" : "rgba(40,89,67,0.18)";
        var title = escapeHtml(props.label_text || featureId || "feature");
        if (geometry.type === "Point") {
          var point = project(geometry.coordinates || [0, 0]);
          return (
            '<g class="v2-map-feature" data-maps-feature-id="' +
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
            '<g class="v2-map-feature" data-maps-feature-id="' +
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
      var tool = comp.composition_mode === "tool" && !(wbRegion && wbRegion.kind === "maps_workbench");
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
          if (ent.gated) {
            link.classList.add("is-gated");
            link.setAttribute("aria-disabled", "true");
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
    if (kind === "maps_workbench") {
      var mapsWarnings = wb.warnings || [];
      var mapsDocumentCatalog = wb.document_catalog || [];
      var mapsSelectedDocument = wb.selected_document || {};
      var mapsSelectedRow = wb.selected_row || {};
      var mapsProjection = wb.map_projection || {};
      var mapsSelectedFeature = mapsProjection.selected_feature || {};
      var mapsLens = wb.lens_state || {};
      var mapsDiagnosticSummary = wb.diagnostic_summary || {};
      var mapsRows = wb.rows || [];
      var mapsRequestContract = wb.request_contract || {};

      function mapsRequestBody(patch) {
        var fixed = mapsRequestContract.fixed_request_fields || {};
        var bodyOut = {
          schema: mapsRequestContract.request_schema || "mycite.v2.admin.maps.read_only.request.v1",
          selected_document_id: mapsSelectedDocument.document_id || "",
          selected_row_address: mapsSelectedRow.datum_address || "",
          selected_feature_id: mapsSelectedFeature.feature_id || "",
          overlay_mode: mapsLens.overlay_mode || "auto",
          raw_underlay_visible: !!mapsLens.raw_underlay_visible,
        };
        Object.keys(fixed || {}).forEach(function (key) {
          bodyOut[key] = fixed[key];
        });
        Object.keys(patch || {}).forEach(function (key) {
          bodyOut[key] = patch[key];
        });
        return bodyOut;
      }

      function overlayCellHtml(row) {
        var overlays = row.overlay_values || [];
        if (!overlays.length) {
          return "<code>" + escapeHtml(row.primary_value_token || "—") + "</code>";
        }
        return overlays
          .map(function (overlay) {
            var display = overlay.display_value || overlay.raw_value || "—";
            var raw = overlay.raw_value || "";
            var title = overlay.anchor_label || overlay.overlay_family || "value";
            var rawHtml =
              mapsLens.raw_underlay_visible && raw
                ? '<div><small>raw: <code>' + escapeHtml(raw) + "</code></small></div>"
                : "";
            return (
              '<div style="margin-bottom:6px"><strong>' +
              escapeHtml(title) +
              ":</strong> " +
              escapeHtml(display) +
              rawHtml +
              "</div>"
            );
          })
          .join("");
      }

      var mapsWarningBlock =
        mapsWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            mapsWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var mapsCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Projection</h3><p>' +
        escapeHtml(String(mapsProjection.projection_state || "—").replace(/_/g, " ")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Documents</h3><p>' +
        escapeHtml(String(mapsDiagnosticSummary.document_count != null ? mapsDiagnosticSummary.document_count : "0")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Features</h3><p>' +
        escapeHtml(String(mapsProjection.feature_count != null ? mapsProjection.feature_count : "0")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Rows</h3><p>' +
        escapeHtml(String(mapsDiagnosticSummary.row_count != null ? mapsDiagnosticSummary.row_count : "0")) +
        "</p></article>" +
        "</div>";
      var lensHtml =
        '<div class="v2-card" style="margin-top:12px"><h3>Lens</h3>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-maps-overlay-mode="auto" style="border-radius:6px' +
        ((mapsLens.overlay_mode || "auto") === "auto" ? ';font-weight:700' : "") +
        '">Auto overlay</button>' +
        '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-maps-overlay-mode="raw_only" style="border-radius:6px' +
        ((mapsLens.overlay_mode || "auto") === "raw_only" ? ';font-weight:700' : "") +
        '">Raw only</button>' +
        '<label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="v2-maps-raw-underlay-toggle"' +
        (mapsLens.raw_underlay_visible ? " checked" : "") +
        "> show raw values</label></div></div>";
      var documentButtons =
        mapsDocumentCatalog.length > 0
          ? '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
            mapsDocumentCatalog
              .map(function (doc) {
                return (
                  '<button type="button" class="ide-sessionAction ide-sessionAction--button" data-maps-document-id="' +
                  escapeHtml(doc.document_id || "") +
                  '" style="border-radius:6px' +
                  (doc.selected ? ';font-weight:700' : "") +
                  '">' +
                  escapeHtml(doc.document_name || doc.document_id || "document") +
                  " (" +
                  escapeHtml(String(doc.projectable_feature_count != null ? doc.projectable_feature_count : 0)) +
                  ")</button>"
                );
              })
              .join("") +
            "</div>"
          : "<p>No authoritative maps documents are cataloged for this tenant.</p>";
      var selectedFeatureHtml =
        mapsSelectedFeature && mapsSelectedFeature.feature_id
          ? '<section class="v2-card" style="margin-top:12px"><h3>Selected feature</h3><dl class="v2-surface-dl">' +
            "<dt>Feature</dt><dd><code>" +
            escapeHtml(mapsSelectedFeature.feature_id || "") +
            "</code></dd><dt>Geometry</dt><dd>" +
            escapeHtml(mapsSelectedFeature.geometry_type || "—") +
            "</dd><dt>Row</dt><dd><code>" +
            escapeHtml(mapsSelectedFeature.row_address || "—") +
            "</code></dd><dt>Label</dt><dd>" +
            escapeHtml(mapsSelectedFeature.label_text || "—") +
            "</dd></dl></section>"
          : "";
      var featureRows = (((mapsProjection.feature_collection || {}).features) || []).slice(0, 24);
      var featureTable =
        featureRows.length > 0
          ? '<section class="v2-card" style="margin-top:12px"><h3>Features</h3><table class="v2-table"><thead><tr><th>Feature</th><th>Geometry</th><th>Row</th><th>Label</th></tr></thead><tbody>' +
            featureRows
              .map(function (feature) {
                var props = feature.properties || {};
                return (
                  "<tr><td><a href=\"#\" data-maps-feature-id=\"" +
                  escapeHtml(feature.id || "") +
                  "\"><code>" +
                  escapeHtml(feature.id || "") +
                  "</code></a></td><td>" +
                  escapeHtml((feature.geometry || {}).type || "—") +
                  "</td><td><code>" +
                  escapeHtml(props.row_address || "—") +
                  "</code></td><td>" +
                  escapeHtml(props.label_text || "—") +
                  "</td></tr>"
                );
              })
              .join("") +
            "</tbody></table></section>"
          : "";
      var rowTableRows = mapsRows.slice(0, 180);
      var rowTable =
        '<section class="v2-card" style="margin-top:12px"><h3>Rows</h3><table class="v2-table"><thead><tr><th>Address</th><th>Labels</th><th>Diagnostics</th><th>Overlay values</th></tr></thead><tbody>' +
        rowTableRows
          .map(function (row) {
            return (
              "<tr><td><a href=\"#\" data-maps-row-address=\"" +
              escapeHtml(row.datum_address || "") +
              "\"><code>" +
              escapeHtml(row.datum_address || "") +
              "</code></a></td><td>" +
              escapeHtml(row.label_text || "—") +
              "</td><td>" +
              escapeHtml(((row.diagnostic_states || []).join(", ")) || "ok") +
              "</td><td>" +
              overlayCellHtml(row) +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>" +
        (mapsRows.length > rowTableRows.length
          ? '<p class="ide-controlpanel__empty" style="margin-top:8px">Showing first ' +
            escapeHtml(String(rowTableRows.length)) +
            " of " +
            escapeHtml(String(mapsRows.length)) +
            " rows.</p>"
          : "") +
        "</section>";
      body.innerHTML =
        mapsWarningBlock +
        mapsCards +
        lensHtml +
        '<section class="v2-card" style="margin-top:12px"><h3>Documents</h3>' +
        documentButtons +
        "</section>" +
        renderMapsSvg(mapsProjection) +
        selectedFeatureHtml +
        featureTable +
        rowTable;

      Array.prototype.forEach.call(body.querySelectorAll("[data-maps-document-id]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            mapsRequestContract.route || "/portal/api/v2/admin/maps/read-only",
            mapsRequestBody({
              selected_document_id: el.getAttribute("data-maps-document-id") || "",
              selected_row_address: "",
              selected_feature_id: "",
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-maps-row-address]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            mapsRequestContract.route || "/portal/api/v2/admin/maps/read-only",
            mapsRequestBody({
              selected_row_address: el.getAttribute("data-maps-row-address") || "",
              selected_feature_id: "",
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-maps-feature-id]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            mapsRequestContract.route || "/portal/api/v2/admin/maps/read-only",
            mapsRequestBody({
              selected_feature_id: el.getAttribute("data-maps-feature-id") || "",
            })
          );
        });
      });
      Array.prototype.forEach.call(body.querySelectorAll("[data-maps-overlay-mode]"), function (el) {
        el.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadRuntimeView(
            mapsRequestContract.route || "/portal/api/v2/admin/maps/read-only",
            mapsRequestBody({
              overlay_mode: el.getAttribute("data-maps-overlay-mode") || "auto",
            })
          );
        });
      });
      var rawToggle = document.getElementById("v2-maps-raw-underlay-toggle");
      if (rawToggle) {
        rawToggle.addEventListener("change", function () {
          loadRuntimeView(
            mapsRequestContract.route || "/portal/api/v2/admin/maps/read-only",
            mapsRequestBody({
              raw_underlay_visible: !!rawToggle.checked,
            })
          );
        });
      }
      return;
    }
    if (kind === "tool_collapsed_inspector") {
      body.innerHTML =
        '<div class="v2-card"><h3>' +
        escapeHtml(wb.title || "Tool") +
        "</h3><p>" +
        escapeHtml(wb.subtitle || "") +
        "</p></div>";
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
    if (kind === "maps_summary") {
      var mapSelectedDocument = region.selected_document || {};
      var mapSelectedFeature = region.selected_feature || {};
      var mapSelectedRow = region.selected_row || {};
      var mapDiagnosticSummary = region.diagnostic_summary || {};
      var mapLensState = region.lens_state || {};
      var mapWarnings = (region.warnings || [])
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
        "<dt>Projection state</dt><dd>" +
        escapeHtml(String(mapDiagnosticSummary.projection_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Feature count</dt><dd>" +
        escapeHtml(String(mapDiagnosticSummary.feature_count != null ? mapDiagnosticSummary.feature_count : "0")) +
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
