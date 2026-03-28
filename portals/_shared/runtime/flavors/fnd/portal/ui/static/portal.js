/* MyCite Portal JS
 * - Theme selector
 * - Local tab switching for page-internal panels
 * - Alias sidebar filter
 * - Workbench interface panel + shell splitters
 * Internal compatibility note: legacy IDs/class names still use "inspector".
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
  const CONTROL_PANEL_WIDTH_KEY = "mycite.layout.control_panel.width";
  const CONTROL_PANEL_OPEN_KEY = "mycite.layout.control_panel.open";
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
    const controlPanel = qs("#portalControlPanel");
    const inspector = qs("#portalInspector");
    const workbench = qs(".ide-workbench");
    const ideBody = qs(".ide-body");
    if (!shell || !controlPanel || !inspector || !workbench) return null;

    function clamp(value, min, max) {
      const n = Number(value);
      if (!Number.isFinite(n)) return min;
      return Math.min(max, Math.max(min, n));
    }

    function readShellPxVar(name, fallback) {
      const raw = getComputedStyle(shell).getPropertyValue(name);
      const value = parseInt(raw, 10);
      return Number.isFinite(value) ? value : fallback;
    }

    function hasSystemWorkbench() {
      return !!qs(".system-center-workspace");
    }

    function currentShellComposition() {
      return (shell.getAttribute("data-shell-composition") || "").trim().toLowerCase() === "tool" ? "tool" : "system";
    }

    function currentLayoutPolicy() {
      if (currentShellComposition() === "tool") {
        return {
          defaultControlPanelWidth: 320,
          defaultInspectorWidth: 360,
          minControlPanelWidth: 240,
          maxControlPanelWidth: 420,
          minInspectorWidth: 320,
          maxInspectorWidth: 720,
          minWorkbenchWidth: 0,
        };
      }
      if (hasSystemWorkbench()) {
        return {
          defaultControlPanelWidth: 248,
          defaultInspectorWidth: 300,
          minControlPanelWidth: 188,
          maxControlPanelWidth: 360,
          minInspectorWidth: 240,
          maxInspectorWidth: 440,
          minWorkbenchWidth: 920,
        };
      }
      return {
        defaultControlPanelWidth: 280,
        defaultInspectorWidth: 360,
        minControlPanelWidth: 220,
        maxControlPanelWidth: 420,
        minInspectorWidth: 280,
        maxInspectorWidth: 520,
        minWorkbenchWidth: 720,
      };
    }

    function applyControlPanelWidth(value) {
      const policy = currentLayoutPolicy();
      const width = clamp(value, policy.minControlPanelWidth, policy.maxControlPanelWidth);
      shell.style.setProperty("--ide-controlpanel-w", `${width}px`);
      return width;
    }

    function applyInspectorWidth(value) {
      if (currentShellComposition() === "tool") {
        return readShellPxVar("--ide-inspector-w", currentLayoutPolicy().defaultInspectorWidth);
      }
      const policy = currentLayoutPolicy();
      const width = clamp(value, policy.minInspectorWidth, policy.maxInspectorWidth);
      shell.style.setProperty("--ide-inspector-w", `${width}px`);
      return width;
    }

    function rebalanceWorkbench() {
      if (!ideBody || window.matchMedia("(max-width: 960px)").matches) return;
      const composition = currentShellComposition();
      const policy = currentLayoutPolicy();
      shell.classList.toggle("ide-shell--system-workbench", composition === "system" && hasSystemWorkbench());
      shell.classList.toggle("ide-shell--tool-composition", composition === "tool");
      if (composition === "tool") {
        shell.classList.remove("ide-shell--workbench-tight");
        return;
      }
      const bodyWidth = ideBody.clientWidth || window.innerWidth || 0;
      if (!bodyWidth) return;

      const activityWidth = readShellPxVar("--ide-activity-w", 72);
      const splitterWidth = readShellPxVar("--ide-splitter-w", 8);
      const controlPanelOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
      const inspectorOpen = shell.getAttribute("data-inspector-collapsed") !== "true";
      let controlPanelWidth = controlPanelOpen ? readShellPxVar("--ide-controlpanel-w", 280) : 0;
      let inspectorWidth = inspectorOpen ? readShellPxVar("--ide-inspector-w", 360) : 0;
      const controlPanelSplitterWidth = controlPanelOpen ? splitterWidth : 0;
      let workbenchWidth = bodyWidth
        - activityWidth
        - controlPanelWidth
        - inspectorWidth
        - controlPanelSplitterWidth
        - (inspectorOpen ? splitterWidth : 0);

      if (workbenchWidth >= policy.minWorkbenchWidth) return;

      let deficit = policy.minWorkbenchWidth - workbenchWidth;
      if (inspectorOpen && inspectorWidth > policy.minInspectorWidth) {
        const nextInspectorWidth = Math.max(policy.minInspectorWidth, inspectorWidth - deficit);
        deficit -= inspectorWidth - nextInspectorWidth;
        inspectorWidth = applyInspectorWidth(nextInspectorWidth);
      }

      if (deficit > 0 && controlPanelOpen && controlPanelWidth > policy.minControlPanelWidth) {
        const nextControlPanelWidth = Math.max(policy.minControlPanelWidth, controlPanelWidth - deficit);
        deficit -= controlPanelWidth - nextControlPanelWidth;
        controlPanelWidth = applyControlPanelWidth(nextControlPanelWidth);
      }

      workbenchWidth = bodyWidth
        - activityWidth
        - controlPanelWidth
        - inspectorWidth
        - controlPanelSplitterWidth
        - (inspectorOpen ? splitterWidth : 0);
      if (workbenchWidth < policy.minWorkbenchWidth) {
        shell.classList.add("ide-shell--workbench-tight");
      } else {
        shell.classList.remove("ide-shell--workbench-tight");
      }
    }

    function syncShellToggleButtons() {
      qsa("[data-shell-toggle]", shell).forEach(button => {
        const target = button.getAttribute("data-shell-toggle") || "";
        const isOpen = target === "control-panel"
          ? shell.getAttribute("data-control-panel-collapsed") !== "true"
          : shell.getAttribute("data-inspector-collapsed") !== "true";
        const forceOpen = currentShellComposition() === "tool" && target === "inspector";
        button.classList.toggle("is-active", isOpen);
        button.setAttribute("aria-pressed", isOpen ? "true" : "false");
        button.disabled = forceOpen;
        if (forceOpen) {
          button.setAttribute("title", "Tool mode keeps the interface panel visible.");
        } else {
          button.removeAttribute("title");
        }
      });
    }

    function setControlPanelWidth(value, persist) {
      const width = applyControlPanelWidth(value);
      if (persist) {
        try { window.localStorage.setItem(CONTROL_PANEL_WIDTH_KEY, String(width)); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setInspectorWidth(value, persist) {
      const width = applyInspectorWidth(value);
      if (persist && currentShellComposition() !== "tool") {
        try { window.localStorage.setItem(INSPECTOR_WIDTH_KEY, String(width)); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setControlPanelOpen(open, persist) {
      const isOpen = !!open;
      shell.setAttribute("data-control-panel-collapsed", isOpen ? "false" : "true");
      controlPanel.classList.toggle("is-collapsed", !isOpen);
      controlPanel.setAttribute("aria-hidden", isOpen ? "false" : "true");
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(CONTROL_PANEL_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setInspectorOpen(open, persist) {
      const isOpen = currentShellComposition() === "tool" ? true : !!open;
      shell.setAttribute("data-inspector-collapsed", isOpen ? "false" : "true");
      inspector.classList.toggle("is-collapsed", !isOpen);
      inspector.setAttribute("aria-hidden", isOpen ? "false" : "true");
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(INSPECTOR_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setShellComposition(mode) {
      const composition = String(mode || "").trim().toLowerCase() === "tool" ? "tool" : "system";
      shell.setAttribute("data-shell-composition", composition);
      shell.setAttribute("data-foreground-shell-region", composition === "tool" ? "interface-panel" : "center-workbench");
      workbench.setAttribute("data-foreground-visible", composition === "tool" ? "false" : "true");
      workbench.setAttribute("aria-hidden", composition === "tool" ? "true" : "false");
      inspector.setAttribute("data-primary-surface", composition === "tool" ? "true" : "false");
      inspector.setAttribute("data-surface-layout", composition === "tool" ? "primary-fill" : "sidebar");
      if (composition === "tool") {
        setInspectorOpen(true, false);
      } else {
        syncShellToggleButtons();
        rebalanceWorkbench();
      }
    }

    const storedControlPanel = parseInt(getStoredValue(CONTROL_PANEL_WIDTH_KEY), 10);
    const storedControlPanelOpen = getStoredValue(CONTROL_PANEL_OPEN_KEY);
    const storedInspector = parseInt(getStoredValue(INSPECTOR_WIDTH_KEY), 10);
    const storedInspectorOpen = getStoredValue(INSPECTOR_OPEN_KEY);
    const initialPolicy = currentLayoutPolicy();

    setControlPanelWidth(storedControlPanel || initialPolicy.defaultControlPanelWidth, false);
    setInspectorWidth(storedInspector || initialPolicy.defaultInspectorWidth, false);
    setControlPanelOpen(storedControlPanelOpen !== "0", false);
    let inspectorShouldOpen = false;
    if (storedInspectorOpen === "1") inspectorShouldOpen = true;
    else if (storedInspectorOpen === "0") inspectorShouldOpen = false;
    else inspectorShouldOpen = !!window.__PORTAL_SHELL_INSPECTOR_DEFAULT_OPEN;
    setInspectorOpen(inspectorShouldOpen, false);
    setShellComposition(currentShellComposition());
    rebalanceWorkbench();

    qsa("[data-splitter]", shell).forEach(splitter => {
      splitter.addEventListener("pointerdown", event => {
        const type = splitter.getAttribute("data-splitter") || "";
        const startX = event.clientX;
        const startControlPanel = parseInt(getComputedStyle(shell).getPropertyValue("--ide-controlpanel-w"), 10) || 280;
        const startInspector = parseInt(getComputedStyle(shell).getPropertyValue("--ide-inspector-w"), 10) || 360;

        function onMove(moveEvent) {
          if (type === "control-panel") {
            setControlPanelWidth(startControlPanel + (moveEvent.clientX - startX), false);
          } else {
            setInspectorWidth(startInspector - (moveEvent.clientX - startX), false);
          }
        }

        function onUp() {
          if (type === "control-panel") {
            const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-controlpanel-w"), 10) || startControlPanel;
            setControlPanelWidth(width, true);
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

    qsa("[data-shell-toggle]", shell).forEach(button => {
      button.addEventListener("click", () => {
        const target = button.getAttribute("data-shell-toggle") || "";
        if (target === "control-panel") {
          setControlPanelOpen(shell.getAttribute("data-control-panel-collapsed") === "true", true);
          return;
        }
        if (currentShellComposition() === "tool") {
          setInspectorOpen(true, false);
          return;
        }
        setInspectorOpen(shell.getAttribute("data-inspector-collapsed") === "true", true);
      });
    });

    window.addEventListener("resize", rebalanceWorkbench);

    return {
      setControlPanelOpen,
      setInspectorOpen,
      setInspectorWidth,
      setShellComposition,
      rebalanceWorkbench,
    };
  }

  function initInspector(layoutApi) {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    const titleEl = qs("#portalInspectorTitle");
    const contentEl = qs("#portalInspectorContent");
    if (!shell || !inspector || !titleEl || !contentEl) return;

    function systemShellRoot() {
      return qs("#systemShellInspectorRoot", contentEl);
    }

    function toolShellRoot() {
      return qs("#systemToolInterfaceRoot", contentEl);
    }

    function transientMount() {
      return qs("#portalInspectorTransientMount", contentEl);
    }

    function removeNonTransientInspectorChildren() {
      Array.from(contentEl.children).forEach((child) => {
        if (child.id === "portalInspectorTransientMount") return;
        child.remove();
      });
    }

    function setContent(payload) {
      const title = String((payload && payload.title) || "Overview").trim() || "Overview";
      const subtitle = String((payload && payload.subtitle) || "").trim();
      titleEl.textContent = subtitle ? `${title}: ${subtitle}` : title;

      const html = payload && typeof payload.html === "string" ? payload.html : "";
      const node = payload && payload.node ? payload.node : null;
      const sysRoot = systemShellRoot();
      const toolRoot = toolShellRoot();
      const tMount = transientMount();

      if ((sysRoot || toolRoot) && tMount) {
        if (sysRoot) sysRoot.hidden = true;
        if (toolRoot) toolRoot.hidden = true;
        tMount.hidden = false;
        tMount.setAttribute("aria-hidden", "false");
        tMount.innerHTML = "";
        if (node instanceof Node) {
          tMount.appendChild(node);
          return;
        }
        if (html) {
          tMount.innerHTML = html;
          return;
        }
        tMount.innerHTML = '<p class="ide-inspector__empty">Select an item to load interface panel content.</p>';
        return;
      }

      const tMountLegacy = transientMount();
      if (tMountLegacy) {
        tMountLegacy.hidden = true;
        tMountLegacy.setAttribute("aria-hidden", "true");
        tMountLegacy.innerHTML = "";
      }

      if (node instanceof Node) {
        removeNonTransientInspectorChildren();
        contentEl.insertBefore(node, tMountLegacy || null);
        return;
      }

      if (html) {
        removeNonTransientInspectorChildren();
        const holder = document.createElement("div");
        holder.innerHTML = html;
        contentEl.insertBefore(holder, tMountLegacy || null);
        return;
      }

      removeNonTransientInspectorChildren();
      const empty = document.createElement("p");
      empty.className = "ide-inspector__empty";
      empty.textContent = "Select an item to load interface panel content.";
      contentEl.insertBefore(empty, tMountLegacy || null);
    }

    function open(payload) {
      setContent(payload || {});
      if (layoutApi) layoutApi.setInspectorOpen(true, true);
      if (layoutApi) layoutApi.setInspectorWidth(parseInt(getStoredValue(INSPECTOR_WIDTH_KEY), 10) || 360, false);
    }

    function close() {
      const sysRoot = systemShellRoot();
      const toolRoot = toolShellRoot();
      const tMount = transientMount();
      if (tMount) {
        tMount.innerHTML = "";
        tMount.hidden = true;
        tMount.setAttribute("aria-hidden", "true");
      }
      if (sysRoot) sysRoot.hidden = shell.getAttribute("data-shell-composition") === "tool";
      if (toolRoot) toolRoot.hidden = shell.getAttribute("data-shell-composition") !== "tool";
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
        title: title || "Interface Panel",
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
      const title = trigger.getAttribute("data-inspector-title") || "Interface Panel";
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
  window.PortalShell = layoutApi
    ? {
        setInspectorOpen: (open, persist) => layoutApi.setInspectorOpen(!!open, persist !== false),
        setControlPanelOpen: (open, persist) => layoutApi.setControlPanelOpen(!!open, persist !== false),
        setShellComposition: (mode) => layoutApi.setShellComposition(mode),
        rebalanceWorkbench: () => layoutApi.rebalanceWorkbench && layoutApi.rebalanceWorkbench(),
      }
    : null;
  initThemeSelector();
  initLocalTabs();
  initAliasSearch();
  initInspector(layoutApi);
})();
