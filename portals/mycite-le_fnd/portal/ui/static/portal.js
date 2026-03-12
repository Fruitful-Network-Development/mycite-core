/* MyCite Portal JS
 * - Theme selector
 * - Local tab switching for page-internal panels
 * - Alias sidebar filter
 * - Workbench inspector + shell splitters
 */

(function () {
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  const THEME_STANDARD = {
    defaultTheme: "paper",
    themes: [
      { id: "paper", label: "Paper" },
      { id: "ocean", label: "Ocean" },
      { id: "forest", label: "Forest" },
      { id: "midnight", label: "Midnight" }
    ],
    sanitize(themeId) {
      const token = String(themeId || "").trim().toLowerCase();
      return this.themes.some(t => t.id === token) ? token : this.defaultTheme;
    }
  };

  const PORTAL_THEME_STORAGE_KEY = "mycite.theme.portal.default";
  const CONTEXT_WIDTH_KEY = "mycite.layout.context.width";
  const INSPECTOR_WIDTH_KEY = "mycite.layout.inspector.width";
  const INSPECTOR_OPEN_KEY = "mycite.layout.inspector.open";

  function applyTheme(themeId) {
    const safe = THEME_STANDARD.sanitize(themeId);
    THEME_STANDARD.themes.forEach(t => document.body.classList.remove(`theme-${t.id}`));
    document.body.classList.add(`theme-${safe}`);
    document.body.setAttribute("data-theme", safe);
    qsa("[data-current-theme]").forEach(node => { node.textContent = safe; });
    return safe;
  }

  function withThemeParam(rawUrl, themeId) {
    if (!rawUrl) return rawUrl;
    try {
      const u = new URL(rawUrl, window.location.origin);
      u.searchParams.set("theme", themeId);
      return u.toString();
    } catch (_) {
      return rawUrl;
    }
  }

  function persistTheme(storageKey, themeId) {
    try { window.localStorage.setItem(storageKey, themeId); } catch (_) {}
  }

  function getStoredValue(storageKey) {
    try { return window.localStorage.getItem(storageKey) || ""; } catch (_) { return ""; }
  }

  function detectPreferredTheme(storageKey) {
    try {
      const urlTheme = new URL(window.location.href).searchParams.get("theme") || "";
      if (urlTheme) return THEME_STANDARD.sanitize(urlTheme);
    } catch (_) {}
    const stored = getStoredValue(storageKey);
    return THEME_STANDARD.sanitize(stored || THEME_STANDARD.defaultTheme);
  }

  function syncThemedIframes(themeId) {
    qsa("[data-themed-iframe]").forEach(frame => {
      const src = frame.getAttribute("src") || "";
      if (!src) return;
      const themedSrc = withThemeParam(src, themeId);
      if (themedSrc && themedSrc !== src) {
        frame.setAttribute("src", themedSrc);
      }
    });
  }

  function initThemeSelector() {
    const picker = qs("[data-theme-selector]");
    if (!picker) {
      applyTheme(detectPreferredTheme(PORTAL_THEME_STORAGE_KEY));
      return;
    }

    if (!picker.options.length) {
      THEME_STANDARD.themes.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = t.label;
        picker.appendChild(opt);
      });
    }

    const scope = picker.getAttribute("data-theme-scope") || "portal";
    const orgId = picker.getAttribute("data-org-msn-id") || "default";
    const storageKey = scope === "portal" ? PORTAL_THEME_STORAGE_KEY : `mycite.theme.${scope}.${orgId}`;
    const initial = detectPreferredTheme(storageKey);

    picker.value = initial;
    const applied = applyTheme(initial);
    syncThemedIframes(applied);

    picker.addEventListener("change", () => {
      const next = applyTheme(picker.value);
      picker.value = next;
      persistTheme(storageKey, next);
      persistTheme(PORTAL_THEME_STORAGE_KEY, next);
      syncThemedIframes(next);
    });
  }

  function initLocalTabs() {
    const tabs = qsa(".hometabs__tab");
    const panels = qsa(".panel");
    if (!tabs.length || !panels.length) return;

    function setActiveTab(tabName) {
      tabs.forEach(btn => {
        const isActive = btn.getAttribute("data-tab") === tabName;
        btn.classList.toggle("is-active", isActive);
      });
      panels.forEach(p => {
        const isActive = p.getAttribute("data-panel") === tabName;
        p.classList.toggle("is-active", isActive);
      });
    }

    const first = tabs[0] && tabs[0].getAttribute("data-tab");
    if (first) setActiveTab(first);

    tabs.forEach(btn => {
      btn.addEventListener("click", () => {
        const t = btn.getAttribute("data-tab");
        if (!t) return;
        setActiveTab(t);
      });
    });
  }

  function initAliasSearch() {
    const search = qs("#aliasSearch");
    const list = qs("#aliasList");
    if (!search || !list) return;

    const items = qsa(".navcol__item", list);
    search.addEventListener("input", () => {
      const query = (search.value || "").trim().toLowerCase();
      items.forEach(li => {
        const title = qs(".navcol__linkTitle", li);
        const text = (title && title.textContent) || "";
        li.style.display = text.toLowerCase().includes(query) ? "" : "none";
      });
    });
  }

  function initWorkbenchLayout() {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    if (!shell || !inspector) return null;

    function clamp(value, min, max) {
      const n = Number(value);
      if (!Number.isFinite(n)) return min;
      return Math.min(max, Math.max(min, n));
    }

    function setContextWidth(value, persist) {
      const width = clamp(value, 220, 420);
      shell.style.setProperty("--ide-context-w", `${width}px`);
      if (persist) {
        try { window.localStorage.setItem(CONTEXT_WIDTH_KEY, String(width)); } catch (_) {}
      }
    }

    function setInspectorWidth(value, persist) {
      const width = clamp(value, 280, 520);
      shell.style.setProperty("--ide-inspector-w", `${width}px`);
      if (persist) {
        try { window.localStorage.setItem(INSPECTOR_WIDTH_KEY, String(width)); } catch (_) {}
      }
    }

    function setInspectorOpen(open, persist) {
      const isOpen = !!open;
      shell.setAttribute("data-inspector-collapsed", isOpen ? "false" : "true");
      inspector.classList.toggle("is-collapsed", !isOpen);
      inspector.setAttribute("aria-hidden", isOpen ? "false" : "true");
      if (persist) {
        try { window.localStorage.setItem(INSPECTOR_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
    }

    const storedContext = parseInt(getStoredValue(CONTEXT_WIDTH_KEY), 10);
    const storedInspector = parseInt(getStoredValue(INSPECTOR_WIDTH_KEY), 10);
    const storedInspectorOpen = getStoredValue(INSPECTOR_OPEN_KEY);

    setContextWidth(storedContext || 280, false);
    setInspectorWidth(storedInspector || 360, false);
    setInspectorOpen(storedInspectorOpen === "1", false);

    qsa("[data-splitter]", shell).forEach(splitter => {
      splitter.addEventListener("pointerdown", event => {
        const type = splitter.getAttribute("data-splitter") || "";
        const startX = event.clientX;
        const startContext = parseInt(getComputedStyle(shell).getPropertyValue("--ide-context-w"), 10) || 280;
        const startInspector = parseInt(getComputedStyle(shell).getPropertyValue("--ide-inspector-w"), 10) || 360;

        function onMove(moveEvent) {
          if (type === "context") {
            setContextWidth(startContext + (moveEvent.clientX - startX), false);
            return;
          }
          setInspectorWidth(startInspector - (moveEvent.clientX - startX), false);
        }

        function onUp() {
          if (type === "context") {
            const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-context-w"), 10) || startContext;
            setContextWidth(width, true);
          } else {
            const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-inspector-w"), 10) || startInspector;
            setInspectorWidth(width, true);
          }
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        }

        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      });
    });

    return {
      setInspectorOpen,
      setInspectorWidth
    };
  }

  function initInspector(layoutApi) {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    const titleEl = qs("#portalInspectorTitle");
    const contentEl = qs("#portalInspectorContent");
    if (!shell || !inspector || !titleEl || !contentEl) return;

    function setContent(payload) {
      const title = String((payload && payload.title) || "Details").trim() || "Details";
      const subtitle = String((payload && payload.subtitle) || "").trim();
      titleEl.textContent = subtitle ? `${title}: ${subtitle}` : title;

      const html = payload && typeof payload.html === "string" ? payload.html : "";
      const node = payload && payload.node ? payload.node : null;

      if (node instanceof Node) {
        contentEl.innerHTML = "";
        contentEl.appendChild(node);
        return;
      }

      if (html) {
        contentEl.innerHTML = html;
      } else {
        contentEl.innerHTML = '<p class="ide-inspector__empty">Select an item to inspect.</p>';
      }
    }

    function open(payload) {
      setContent(payload || {});
      if (layoutApi) layoutApi.setInspectorOpen(true, true);
      if (layoutApi) layoutApi.setInspectorWidth(parseInt(getStoredValue(INSPECTOR_WIDTH_KEY), 10) || 360, false);
    }

    function close() {
      if (layoutApi) layoutApi.setInspectorOpen(false, true);
    }

    function toggle(payload) {
      if (shell.getAttribute("data-inspector-collapsed") === "true") {
        open(payload || {});
      } else {
        close();
      }
    }

    function openTemplate(templateId, title, subtitle) {
      const tpl = qs(`#${templateId}`);
      if (!tpl || tpl.tagName.toLowerCase() !== "template") return;
      const wrap = document.createElement("div");
      wrap.appendChild(tpl.content.cloneNode(true));
      open({
        title: title || "Details",
        subtitle: subtitle || "",
        node: wrap,
      });
    }

    qsa("[data-inspector-close]").forEach(btn => {
      btn.addEventListener("click", close);
    });

    document.addEventListener("click", event => {
      const trigger = event.target && event.target.closest
        ? event.target.closest("[data-inspector-template]")
        : null;
      if (!trigger) return;
      event.preventDefault();
      const templateId = trigger.getAttribute("data-inspector-template") || "";
      const title = trigger.getAttribute("data-inspector-title") || "Details";
      const subtitle = trigger.getAttribute("data-inspector-subtitle") || "";
      if (!templateId) return;
      openTemplate(templateId, title, subtitle);
    });

    document.addEventListener("click", event => {
      const navLink = event.target && event.target.closest ? event.target.closest(".ide-activitylink") : null;
      if (navLink) close();
    });

    window.PortalInspector = {
      open,
      close,
      toggle,
      openTemplate,
    };
  }

  const layoutApi = initWorkbenchLayout();
  initThemeSelector();
  initLocalTabs();
  initAliasSearch();
  initInspector(layoutApi);
})();
