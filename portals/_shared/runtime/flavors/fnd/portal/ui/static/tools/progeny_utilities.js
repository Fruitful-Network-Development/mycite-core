(function () {
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function isObject(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function api(method, path, body) {
    var response = await fetch(path, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    var payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.error || payload.description || ("HTTP " + response.status));
    }
    return payload;
  }

  function getValueAtPath(root, path) {
    var current = root;
    var parts = String(path || "").split(".");
    for (var i = 0; i < parts.length; i += 1) {
      if (!isObject(current)) return undefined;
      current = current[parts[i]];
    }
    return current;
  }

  function setValueAtPath(root, path, value) {
    var parts = String(path || "").split(".");
    var current = root;
    for (var i = 0; i < parts.length - 1; i += 1) {
      var key = parts[i];
      if (!isObject(current[key])) current[key] = {};
      current = current[key];
    }
    current[parts[parts.length - 1]] = value;
  }

  function flattenTemplate(node, prefix, out) {
    if (Array.isArray(node)) {
      out.push({ path: prefix, value: node, kind: "json" });
      return;
    }
    if (isObject(node)) {
      var keys = Object.keys(node);
      if (!keys.length) {
        out.push({ path: prefix, value: node, kind: "json" });
        return;
      }
      keys.forEach(function (key) {
        flattenTemplate(node[key], prefix ? prefix + "." + key : key, out);
      });
      return;
    }
    var kind = typeof node === "boolean" ? "boolean" : (typeof node === "number" ? "number" : "text");
    out.push({ path: prefix, value: node, kind: kind });
  }

  function parseFieldValue(input, kind) {
    if (kind === "boolean") {
      return input.checked;
    }
    var raw = String(input.value || "");
    if (kind === "number") {
      var num = Number(raw);
      return Number.isFinite(num) ? num : 0;
    }
    if (kind === "json") {
      if (!raw.trim()) return Array.isArray(kind.value) ? [] : {};
      return JSON.parse(raw);
    }
    return raw;
  }

  function openInspector(node, title) {
    if (window.PortalInspector && typeof window.PortalInspector.open === "function") {
      window.PortalInspector.open({ title: title, node: node });
    }
  }

  async function openTemplateEditor(progenyType) {
    var payload = await api("GET", "/portal/api/progeny/templates/" + encodeURIComponent(progenyType));
    var item = isObject(payload.item) ? payload.item : {};
    var wrap = document.createElement("div");
    wrap.innerHTML = [
      '<article class="card">',
      '<div class="card__kicker">Hosted Template</div>',
      '<div class="card__title">' + escapeHtml(progenyType) + ' template</div>',
      '<div class="card__body">',
      '<p>Edit the hosted template JSON stored in <code>private/network/hosted.json</code>.</p>',
      '<textarea data-template-json style="width:100%;min-height:420px;font-family:ui-monospace,monospace;">' + escapeHtml(JSON.stringify(item, null, 2)) + '</textarea>',
      '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.75rem;">',
      '<button type="button" class="ops-btn" data-save-template>Save Template</button>',
      '</div>',
      '<pre class="ops-status" data-template-status style="margin-top:0.75rem;">Ready.</pre>',
      '</div>',
      '</article>'
    ].join("");
    var saveBtn = qs("[data-save-template]", wrap);
    var status = qs("[data-template-status]", wrap);
    var textarea = qs("[data-template-json]", wrap);
    saveBtn.addEventListener("click", async function () {
      try {
        var body = JSON.parse(textarea.value || "{}");
        var response = await api("PUT", "/portal/api/progeny/templates/" + encodeURIComponent(progenyType), body);
        status.textContent = "Saved to " + String(response.written_to || "hosted.json");
        window.setTimeout(function () { window.location.reload(); }, 400);
      } catch (err) {
        status.textContent = "Error: " + err.message;
      }
    });
    openInspector(wrap, progenyType + " template");
  }

  async function openInstanceEditor(instanceId, progenyType) {
    var record = await api("GET", "/portal/api/progeny/instances/" + encodeURIComponent(instanceId));
    var templatePayload = await api("GET", "/portal/api/progeny/templates/" + encodeURIComponent(progenyType));
    var item = isObject(record.item) ? record.item : {};
    var template = isObject(templatePayload.item) ? templatePayload.item : {};
    var fields = [];
    flattenTemplate(template, "", fields);
    fields = fields.filter(function (field) {
      return field.path && field.path !== "contract";
    });

    var wrap = document.createElement("div");
    var html = [
      '<article class="card">',
      '<div class="card__kicker">Progeny Instance</div>',
      '<div class="card__title">' + escapeHtml(instanceId) + '</div>',
      '<div class="card__body">',
      '<p>Editable fields are derived from the selected hosted progeny template.</p>',
      '<form data-instance-form style="display:grid;gap:0.75rem;">'
    ];
    fields.forEach(function (field) {
      var currentValue = getValueAtPath(item, field.path);
      if (typeof currentValue === "undefined") currentValue = field.value;
      html.push('<label style="display:grid;gap:0.3rem;">');
      html.push('<span style="font-size:0.75rem;color:var(--ink2);">' + escapeHtml(field.path) + '</span>');
      if (field.kind === "boolean") {
        html.push('<input type="checkbox" data-field-path="' + escapeHtml(field.path) + '" data-field-kind="boolean" ' + (currentValue ? "checked" : "") + ' />');
      } else if (field.kind === "json") {
        html.push('<textarea data-field-path="' + escapeHtml(field.path) + '" data-field-kind="json" style="min-height:100px;font-family:ui-monospace,monospace;">' + escapeHtml(JSON.stringify(currentValue, null, 2)) + '</textarea>');
      } else {
        html.push('<input type="text" data-field-path="' + escapeHtml(field.path) + '" data-field-kind="' + escapeHtml(field.kind) + '" value="' + escapeHtml(currentValue) + '" />');
      }
      html.push('</label>');
    });
    html.push('</form>');
    html.push('<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.75rem;">');
    html.push('<button type="button" class="ops-btn" data-save-instance>Save Instance</button>');
    html.push('</div>');
    html.push('<pre class="ops-status" data-instance-status style="margin-top:0.75rem;">Ready.</pre>');
    html.push('</div></article>');
    wrap.innerHTML = html.join("");

    var saveBtn = qs("[data-save-instance]", wrap);
    var status = qs("[data-instance-status]", wrap);
    saveBtn.addEventListener("click", async function () {
      try {
        var next = JSON.parse(JSON.stringify(item));
        qsa("[data-field-path]", wrap).forEach(function (fieldNode) {
          var path = fieldNode.getAttribute("data-field-path") || "";
          var kind = fieldNode.getAttribute("data-field-kind") || "text";
          var value;
          if (kind === "json") {
            value = JSON.parse(String(fieldNode.value || "{}"));
          } else if (kind === "boolean") {
            value = !!fieldNode.checked;
          } else if (kind === "number") {
            var num = Number(fieldNode.value || "0");
            value = Number.isFinite(num) ? num : 0;
          } else {
            value = String(fieldNode.value || "");
          }
          setValueAtPath(next, path, value);
        });
        var response = await api("PUT", "/portal/api/progeny/instances/" + encodeURIComponent(instanceId), next);
        status.textContent = "Saved to " + String(response.written_to || "instance");
        window.setTimeout(function () { window.location.reload(); }, 400);
      } catch (err) {
        status.textContent = "Error: " + err.message;
      }
    });

    openInspector(wrap, instanceId);
  }

  qsa("[data-progeny-edit-template]").forEach(function (button) {
    button.addEventListener("click", function () {
      openTemplateEditor(button.getAttribute("data-progeny-type") || "member").catch(function (err) {
        window.alert(err.message);
      });
    });
  });

  qsa("[data-progeny-edit-instance]").forEach(function (button) {
    button.addEventListener("click", function () {
      openInstanceEditor(
        button.getAttribute("data-instance-id") || "",
        button.getAttribute("data-progeny-type") || "member"
      ).catch(function (err) {
        window.alert(err.message);
      });
    });
  });
})();
