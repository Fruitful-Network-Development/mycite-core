/* MyCite Portal JS
 * - Theme selector
 * - Local tab switching for page-internal panels
 * - Alias sidebar filter
 * - Workbench + Interface Panel shell splitters
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
  const WORKBENCH_OPEN_KEY = "mycite.layout.workbench.open";
  const INTERFACE_PANEL_WIDTH_KEY = "mycite.layout.interface_panel.width";
  const INTERFACE_PANEL_OPEN_KEY = "mycite.layout.interface_panel.open";
  const LEGACY_INSPECTOR_WIDTH_KEY = "mycite.layout.inspector.width";
  const LEGACY_INSPECTOR_OPEN_KEY = "mycite.layout.inspector.open";

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

  function getStoredValueFromAliases(storageKeys) {
    const keys = Array.isArray(storageKeys) ? storageKeys : [storageKeys];
    for (const key of keys) {
      const value = getStoredValue(key);
      if (value) return value;
    }
    return "";
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
    const pickers = qsa("[data-theme-selector]");
    if (!pickers.length) {
      applyTheme(detectPreferredTheme(PORTAL_THEME_STORAGE_KEY));
      return;
    }

    function ensureOptions(picker) {
      if (picker.options.length) return;
      THEME_STANDARD.themes.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = t.label;
        picker.appendChild(opt);
      });
    }

    function storageKeyForPicker(picker) {
      const scope = picker.getAttribute("data-theme-scope") || "portal";
      const orgId = picker.getAttribute("data-org-msn-id") || "default";
      return scope === "portal" ? PORTAL_THEME_STORAGE_KEY : `mycite.theme.${scope}.${orgId}`;
    }

    function syncThemeSelectors(themeId) {
      pickers.forEach(picker => {
        ensureOptions(picker);
        picker.value = themeId;
      });
    }

    pickers.forEach(ensureOptions);
    const initial = detectPreferredTheme(storageKeyForPicker(pickers[0]));
    const applied = applyTheme(initial);
    syncThemeSelectors(applied);
    syncThemedIframes(applied);

    pickers.forEach(picker => {
      if (picker.getAttribute("data-theme-init-bound") === "true") return;
      picker.setAttribute("data-theme-init-bound", "true");
      picker.addEventListener("change", () => {
        const next = applyTheme(picker.value);
        syncThemeSelectors(next);
        persistTheme(storageKeyForPicker(picker), next);
        persistTheme(PORTAL_THEME_STORAGE_KEY, next);
        syncThemedIframes(next);
      });
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
    const shellDriverV2 = document.body && document.body.getAttribute("data-portal-shell-driver") === "v2-composition";

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

    function browserRouteKey() {
      return `${window.location.pathname || ""}${window.location.search || ""}`;
    }

    function routeKeyFromValue(value) {
      const raw = String(value || "").trim();
      if (!raw) return browserRouteKey();
      try {
        const url = new URL(raw, window.location.origin);
        return `${url.pathname || ""}${url.search || ""}`;
      } catch (_) {
        return raw.startsWith("/") ? raw : browserRouteKey();
      }
    }

    function currentRouteKey(options) {
      const opts = options || {};
      return routeKeyFromValue(opts.routeKey);
    }

    function toolPanelLockIsEnabled() {
      return shell.getAttribute("data-tool-panel-lock") === "true";
    }

    function setToolPanelLock(enabled, options) {
      const opts = options || {};
      const next = currentShellComposition() === "tool" && enabled === true;
      shell.setAttribute("data-tool-panel-lock", next ? "true" : "false");
      if (next) {
        shell.setAttribute("data-tool-panel-lock-route", currentRouteKey(opts));
      } else {
        shell.removeAttribute("data-tool-panel-lock-route");
      }
      shell.classList.toggle("ide-shell--tool-panel-lock", next);
    }

    function syncToolPanelLockScope(options) {
      if (!toolPanelLockIsEnabled()) return;
      if (currentShellComposition() !== "tool") {
        setToolPanelLock(false);
        return;
      }
      const lockRoute = shell.getAttribute("data-tool-panel-lock-route") || "";
      if (lockRoute && lockRoute !== currentRouteKey(options)) {
        setToolPanelLock(false);
      }
    }

    function currentLayoutPolicy() {
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

    function workbenchIsOpen() {
      return shell.getAttribute("data-workbench-collapsed") !== "true";
    }

    function interfacePanelIsOpen() {
      const aliasState = shell.getAttribute("data-interface-panel-collapsed");
      if (aliasState === "true" || aliasState === "false") {
        return aliasState !== "true";
      }
      return shell.getAttribute("data-inspector-collapsed") !== "true";
    }

    function applyControlPanelWidth(value) {
      const policy = currentLayoutPolicy();
      const width = clamp(value, policy.minControlPanelWidth, policy.maxControlPanelWidth);
      shell.style.setProperty("--ide-controlpanel-w", `${width}px`);
      return width;
    }

    function applyInterfacePanelWidth(value) {
      const policy = currentLayoutPolicy();
      const width = clamp(value, policy.minInspectorWidth, policy.maxInspectorWidth);
      shell.style.setProperty("--ide-inspector-w", `${width}px`);
      return width;
    }

    function applyControlPanelVisibility(isOpen) {
      shell.setAttribute("data-control-panel-collapsed", isOpen ? "false" : "true");
      controlPanel.classList.toggle("is-collapsed", !isOpen);
      controlPanel.setAttribute("aria-hidden", isOpen ? "false" : "true");
    }

    function applyWorkbenchVisibility(isOpen) {
      shell.setAttribute("data-workbench-collapsed", isOpen ? "false" : "true");
      workbench.setAttribute("data-foreground-visible", isOpen ? "true" : "false");
      workbench.setAttribute("aria-hidden", isOpen ? "false" : "true");
      workbench.style.display = isOpen ? "" : "none";
    }

    function applyInterfacePanelVisibility(isOpen) {
      shell.setAttribute("data-interface-panel-collapsed", isOpen ? "false" : "true");
      shell.setAttribute("data-inspector-collapsed", isOpen ? "false" : "true");
      inspector.classList.toggle("is-collapsed", !isOpen);
      inspector.setAttribute("aria-hidden", isOpen ? "false" : "true");
      inspector.style.display = isOpen ? "" : "none";
    }

    function canHideWorkbench() {
      return interfacePanelIsOpen();
    }

    function canHideInterfacePanel() {
      return workbenchIsOpen();
    }

    function rebalanceWorkbench() {
      if (!ideBody || window.matchMedia("(max-width: 960px)").matches) return;
      const composition = currentShellComposition();
      const policy = currentLayoutPolicy();
      const workbenchOpen = workbenchIsOpen();
      const inspectorOpen = interfacePanelIsOpen();
      shell.classList.toggle("ide-shell--system-workbench", composition === "system" && hasSystemWorkbench());
      shell.classList.toggle("ide-shell--tool-composition", composition === "tool");
      const bodyWidth = ideBody.clientWidth || window.innerWidth || 0;
      if (!bodyWidth || !workbenchOpen) {
        shell.classList.remove("ide-shell--workbench-tight");
        return;
      }

      const activityWidth = readShellPxVar("--ide-activity-w", 72);
      const splitterWidth = readShellPxVar("--ide-splitter-w", 8);
      const controlPanelOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
      let controlPanelWidth = controlPanelOpen ? readShellPxVar("--ide-controlpanel-w", 280) : 0;
      let inspectorWidth = inspectorOpen ? readShellPxVar("--ide-inspector-w", 360) : 0;
      const controlPanelSplitterWidth = controlPanelOpen ? splitterWidth : 0;
      let workbenchWidth = bodyWidth
        - activityWidth
        - controlPanelWidth
        - inspectorWidth
        - controlPanelSplitterWidth
        - (inspectorOpen ? splitterWidth : 0);

      if (workbenchWidth >= policy.minWorkbenchWidth) {
        shell.classList.remove("ide-shell--workbench-tight");
        return;
      }

      let deficit = policy.minWorkbenchWidth - workbenchWidth;
      if (inspectorOpen && inspectorWidth > policy.minInspectorWidth) {
        const nextInspectorWidth = Math.max(policy.minInspectorWidth, inspectorWidth - deficit);
        deficit -= inspectorWidth - nextInspectorWidth;
        inspectorWidth = applyInterfacePanelWidth(nextInspectorWidth);
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
      shell.classList.toggle("ide-shell--workbench-tight", workbenchWidth < policy.minWorkbenchWidth);
    }

    function syncShellToggleButtons(options) {
      syncToolPanelLockScope(options);
      const composition = currentShellComposition();
      const toolLock = composition === "tool" && toolPanelLockIsEnabled();
      qsa("[data-shell-toggle]", shell).forEach(button => {
        const target = button.getAttribute("data-shell-toggle") || "";
        const baseTitle = button.getAttribute("data-shell-title") || button.getAttribute("aria-label") || "";
        let isOpen = false;
        let title = baseTitle;
        if (target === "control-panel") {
          isOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
        } else if (target === "workbench") {
          isOpen = workbenchIsOpen();
          if (composition === "tool") {
            title = toolLock
              ? "Workbench. Tool lock enabled: Workbench and Interface Panel can stay visible together. Double-click to unlock."
              : "Workbench. Tool default: single-click switches to Workbench-only. Double-click to lock co-visible mode.";
          }
        } else if (target === "interface-panel" || target === "inspector") {
          isOpen = interfacePanelIsOpen();
          if (composition === "tool") {
            title = toolLock
              ? "Interface Panel. Tool lock enabled: Workbench and Interface Panel can stay visible together. Double-click to unlock."
              : "Interface Panel. Tool default: single-click switches to Interface Panel-only. Double-click to lock co-visible mode.";
          }
        }
        const lockable = button.getAttribute("data-shell-lockable") === "tool-panel";
        button.classList.toggle("is-active", isOpen);
        button.classList.toggle("is-locked", lockable && toolLock);
        button.setAttribute("aria-pressed", isOpen ? "true" : "false");
        button.disabled = false;
        if (title) button.setAttribute("title", title);
        else button.removeAttribute("title");
      });
    }

    function setControlPanelWidth(value, persist) {
      const width = applyControlPanelWidth(value);
      if (persist) {
        try { window.localStorage.setItem(CONTROL_PANEL_WIDTH_KEY, String(width)); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setInterfacePanelWidth(value, persist) {
      const width = applyInterfacePanelWidth(value);
      if (persist) {
        try { window.localStorage.setItem(INTERFACE_PANEL_WIDTH_KEY, String(width)); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setControlPanelOpen(open, persist) {
      const isOpen = !!open;
      applyControlPanelVisibility(isOpen);
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(CONTROL_PANEL_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
      rebalanceWorkbench();
    }

    function setWorkbenchOpen(open, persist) {
      let isOpen = !!open;
      const toolExclusiveMode = currentShellComposition() === "tool" && !toolPanelLockIsEnabled();
      if (toolExclusiveMode) {
        if (isOpen) {
          applyWorkbenchVisibility(true);
          applyInterfacePanelVisibility(false);
        } else {
          applyWorkbenchVisibility(false);
          applyInterfacePanelVisibility(true);
        }
        syncShellToggleButtons();
        if (persist) {
          try { window.localStorage.setItem(WORKBENCH_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
          try { window.localStorage.setItem(INTERFACE_PANEL_OPEN_KEY, isOpen ? "0" : "1"); } catch (_) {}
        }
        rebalanceWorkbench();
        return isOpen;
      }
      if (!isOpen && !canHideWorkbench()) {
        isOpen = true;
      }
      applyWorkbenchVisibility(isOpen);
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(WORKBENCH_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
      rebalanceWorkbench();
      return isOpen;
    }

    function setInterfacePanelOpen(open, persist) {
      let isOpen = !!open;
      const toolExclusiveMode = currentShellComposition() === "tool" && !toolPanelLockIsEnabled();
      if (toolExclusiveMode) {
        if (isOpen) {
          applyInterfacePanelVisibility(true);
          applyWorkbenchVisibility(false);
        } else {
          applyInterfacePanelVisibility(false);
          applyWorkbenchVisibility(true);
        }
        syncShellToggleButtons();
        if (persist) {
          try { window.localStorage.setItem(INTERFACE_PANEL_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
          try { window.localStorage.setItem(WORKBENCH_OPEN_KEY, isOpen ? "0" : "1"); } catch (_) {}
        }
        rebalanceWorkbench();
        return isOpen;
      }
      if (!isOpen && !canHideInterfacePanel()) {
        isOpen = true;
      }
      applyInterfacePanelVisibility(isOpen);
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(INTERFACE_PANEL_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      }
      rebalanceWorkbench();
      return isOpen;
    }

    let firstV2ShellCompositionApplied = false;

    function applyShellPostureFromDom(options) {
      const opts = options || {};
      const routeKey = currentRouteKey(opts);
      const composition = currentShellComposition();
      const fromShellComposition = opts.fromShellComposition === true;
      const controlPanelOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
      let workbenchOpen = shell.getAttribute("data-workbench-collapsed") !== "true";
      let interfacePanelOpen = interfacePanelIsOpen();
      let useStoredWorkbenchPreference = opts.useStoredWorkbenchPreference === true;
      if (opts.useStoredWorkbenchPreference == null) {
        useStoredWorkbenchPreference = !fromShellComposition || firstV2ShellCompositionApplied;
      }
      if (!firstV2ShellCompositionApplied && fromShellComposition) {
        useStoredWorkbenchPreference = false;
      }
      if (useStoredWorkbenchPreference && composition !== "tool") {
        const storedWorkbenchOpen = getStoredValue(WORKBENCH_OPEN_KEY);
        if (storedWorkbenchOpen === "1") {
          workbenchOpen = true;
        } else if (storedWorkbenchOpen === "0" && interfacePanelOpen) {
          workbenchOpen = false;
        }
      }
      if (!workbenchOpen && !interfacePanelOpen) {
        workbenchOpen = true;
      }
      applyControlPanelVisibility(controlPanelOpen);
      applyWorkbenchVisibility(workbenchOpen);
      applyInterfacePanelVisibility(interfacePanelOpen);
      if (currentShellComposition() !== "tool") {
        setToolPanelLock(false);
      } else if (!shell.getAttribute("data-tool-panel-lock")) {
        setToolPanelLock(false, { routeKey: routeKey });
      }
      syncShellToggleButtons({ routeKey: routeKey });
      rebalanceWorkbench();
      if (fromShellComposition) {
        firstV2ShellCompositionApplied = true;
      }
    }

    function setShellComposition(mode, options) {
      const routeKey = currentRouteKey(options);
      const composition = String(mode || "").trim().toLowerCase() === "tool" ? "tool" : "system";
      shell.setAttribute("data-shell-composition", composition);
      if (composition !== "tool") {
        setToolPanelLock(false);
      } else {
        syncToolPanelLockScope({ routeKey: routeKey });
      }
      if (!shell.getAttribute("data-foreground-shell-region")) {
        shell.setAttribute("data-foreground-shell-region", "center-workbench");
      }
      if (!workbench.getAttribute("data-foreground-visible")) {
        workbench.setAttribute("data-foreground-visible", workbenchIsOpen() ? "true" : "false");
      }
      workbench.setAttribute("aria-hidden", workbenchIsOpen() ? "false" : "true");
      if (!inspector.getAttribute("data-primary-surface")) {
        inspector.setAttribute("data-primary-surface", "false");
      }
      if (!inspector.getAttribute("data-surface-layout")) {
        inspector.setAttribute("data-surface-layout", "sidebar");
      }
      document.dispatchEvent(new CustomEvent("mycite:shell:composition-changed", { detail: { composition } }));
      syncShellToggleButtons({ routeKey: routeKey });
      rebalanceWorkbench();
    }

    const storedControlPanel = parseInt(getStoredValue(CONTROL_PANEL_WIDTH_KEY), 10);
    const storedControlPanelOpen = getStoredValue(CONTROL_PANEL_OPEN_KEY);
    const storedInterfacePanel = parseInt(
      getStoredValueFromAliases([INTERFACE_PANEL_WIDTH_KEY, LEGACY_INSPECTOR_WIDTH_KEY]),
      10
    );
    const storedInterfacePanelOpen = getStoredValueFromAliases(
      [INTERFACE_PANEL_OPEN_KEY, LEGACY_INSPECTOR_OPEN_KEY]
    );
    const storedWorkbenchOpen = getStoredValue(WORKBENCH_OPEN_KEY);
    const initialPolicy = currentLayoutPolicy();

    setControlPanelWidth(storedControlPanel || initialPolicy.defaultControlPanelWidth, false);
    setInterfacePanelWidth(storedInterfacePanel || initialPolicy.defaultInspectorWidth, false);
    if (shellDriverV2) {
      applyShellPostureFromDom({ useStoredWorkbenchPreference: false });
    } else {
      setControlPanelOpen(storedControlPanelOpen !== "0", false);
      let interfacePanelShouldOpen = false;
      if (storedInterfacePanelOpen === "1") interfacePanelShouldOpen = true;
      else if (storedInterfacePanelOpen === "0") interfacePanelShouldOpen = false;
      else interfacePanelShouldOpen = !!window.__PORTAL_SHELL_INSPECTOR_DEFAULT_OPEN;
      setInterfacePanelOpen(interfacePanelShouldOpen, false);
      let workbenchShouldOpen = storedWorkbenchOpen !== "0";
      if (!workbenchShouldOpen && !interfacePanelIsOpen()) workbenchShouldOpen = true;
      setWorkbenchOpen(workbenchShouldOpen, false);
    }
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
            setInterfacePanelWidth(startInspector - (moveEvent.clientX - startX), false);
          }
        }

        function onUp() {
          if (type === "control-panel") {
            const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-controlpanel-w"), 10) || startControlPanel;
            setControlPanelWidth(width, true);
          } else {
            const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-inspector-w"), 10) || startInspector;
            setInterfacePanelWidth(width, true);
          }
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        }

        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      });
    });

    function dispatchShellToggleRequest(target) {
      if (target === "control-panel") {
        document.dispatchEvent(new CustomEvent("mycite:v2:control-panel-toggle-request"));
        return;
      }
      if (target === "workbench") {
        document.dispatchEvent(new CustomEvent("mycite:v2:workbench-toggle-request"));
        return;
      }
      document.dispatchEvent(new CustomEvent("mycite:v2:interface-panel-toggle-request"));
    }

    function toggleShellRegionLocally(target) {
      if (target === "control-panel") {
        setControlPanelOpen(shell.getAttribute("data-control-panel-collapsed") === "true", true);
        return;
      }
      if (target === "workbench") {
        setWorkbenchOpen(shell.getAttribute("data-workbench-collapsed") === "true", true);
        return;
      }
      setInterfacePanelOpen(!interfacePanelIsOpen(), true);
    }

    qsa("[data-shell-toggle]", shell).forEach(button => {
      const target = button.getAttribute("data-shell-toggle") || "";
      button.addEventListener("click", () => {
        const toolLockable = target === "workbench" || target === "interface-panel" || target === "inspector";
        if (currentShellComposition() === "tool" && toolLockable) {
          if (button.__myciteToggleTimer) {
            clearTimeout(button.__myciteToggleTimer);
          }
          button.__myciteToggleTimer = window.setTimeout(() => {
            button.__myciteToggleTimer = 0;
            if (shellDriverV2) {
              dispatchShellToggleRequest(target);
              return;
            }
            toggleShellRegionLocally(target);
          }, 220);
          return;
        }
        if (shellDriverV2) {
          dispatchShellToggleRequest(target);
          return;
        }
        toggleShellRegionLocally(target);
      });

      button.addEventListener("dblclick", event => {
        const lockable = target === "workbench" || target === "interface-panel" || target === "inspector";
        if (currentShellComposition() !== "tool" || !lockable) return;
        event.preventDefault();
        if (button.__myciteToggleTimer) {
          clearTimeout(button.__myciteToggleTimer);
          button.__myciteToggleTimer = 0;
        }
        const lockEnabled = !toolPanelLockIsEnabled();
        setToolPanelLock(lockEnabled, { routeKey: currentRouteKey() });
        if (!lockEnabled) {
          if (target === "workbench") setWorkbenchOpen(true, true);
          else setInterfacePanelOpen(true, true);
        } else {
          syncShellToggleButtons();
          rebalanceWorkbench();
        }
      });
    });

    window.addEventListener("resize", rebalanceWorkbench);

    return {
      setControlPanelOpen,
      setWorkbenchOpen,
      setInterfacePanelOpen,
      setInspectorOpen: setInterfacePanelOpen,
      setInterfacePanelWidth,
      setInspectorWidth: setInterfacePanelWidth,
      setShellComposition,
      syncFromDom: applyShellPostureFromDom,
      rebalanceWorkbench,
    };
  }

  function initInspector(layoutApi) {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    const titleEl = qs("#portalInspectorTitle");
    const contentEl = qs("#portalInspectorContent");
    if (!shell || !inspector || !titleEl || !contentEl) return;
    const shellDriverV2 = document.body && document.body.getAttribute("data-portal-shell-driver") === "v2-composition";

    function systemShellRoot() {
      return qs("#systemShellInspectorRoot", contentEl);
    }

    function toolShellRoot() {
      return qs("#systemToolInterfaceRoot", contentEl);
    }

    function transientMount() {
      return qs("#portalInspectorTransientMount", contentEl);
    }

    function currentComposition() {
      return shell.getAttribute("data-shell-composition") === "tool" ? "tool" : "system";
    }

    function setRootState(node, active) {
      if (!node) return;
      node.hidden = !active;
      node.setAttribute("aria-hidden", active ? "false" : "true");
      if ("inert" in node) {
        node.inert = !active;
      }
      node.toggleAttribute("data-interface-panel-active", !!active);
    }

    function activatePanelRoot(kind) {
      const sysRoot = systemShellRoot();
      const toolRoot = toolShellRoot();
      const tMount = transientMount();
      const token = String(kind || "").trim().toLowerCase();
      setRootState(sysRoot, token === "system");
      setRootState(toolRoot, token === "tool");
      setRootState(tMount, token === "transient");
      contentEl.setAttribute("data-interface-panel-active-root", token || "");
    }

    function dismissTransient() {
      const tMount = transientMount();
      if (!tMount) return;
      tMount.innerHTML = "";
      setRootState(tMount, false);
    }

    function activatePersistentRoot(forceKind) {
      dismissTransient();
      const token = String(forceKind || "").trim().toLowerCase();
      activatePanelRoot(token === "tool" || token === "system" ? token : currentComposition());
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
        if (currentComposition() === "tool") {
          activatePersistentRoot("tool");
          return;
        }
        activatePanelRoot("transient");
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
        dismissTransient();
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
      if (layoutApi) layoutApi.setInterfacePanelOpen(true, true);
      if (layoutApi) {
        layoutApi.setInterfacePanelWidth(
          parseInt(getStoredValueFromAliases([INTERFACE_PANEL_WIDTH_KEY, LEGACY_INSPECTOR_WIDTH_KEY]), 10) || 360,
          false
        );
      }
    }

    function close() {
      activatePersistentRoot();
      if (layoutApi) layoutApi.setInterfacePanelOpen(false, true);
    }

    function toggle(payload) {
      if (shell.getAttribute("data-interface-panel-collapsed") === "true") {
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
      btn.addEventListener("click", () => {
        if (shellDriverV2) {
          document.dispatchEvent(new CustomEvent("mycite:v2:interface-panel-dismiss-request"));
          return;
        }
        close();
      });
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
      if (!navLink) return;
      if (shellDriverV2) return;
      close();
    });

    document.addEventListener("mycite:shell:composition-changed", event => {
      const composition = event && event.detail && event.detail.composition;
      activatePersistentRoot(composition);
    });

    activatePersistentRoot();

    window.PortalInspector = {
      open,
      close,
      toggle,
      openTemplate,
      activatePersistentRoot,
      dismissTransient,
    };
  }

  const layoutApi = initWorkbenchLayout();
  window.PortalShell = layoutApi
    ? {
        setWorkbenchOpen: (open, persist) => layoutApi.setWorkbenchOpen(!!open, persist !== false),
        setInterfacePanelOpen: (open, persist) => layoutApi.setInterfacePanelOpen(!!open, persist !== false),
        setInspectorOpen: (open, persist) => layoutApi.setInterfacePanelOpen(!!open, persist !== false),
        setControlPanelOpen: (open, persist) => layoutApi.setControlPanelOpen(!!open, persist !== false),
        setShellComposition: (mode, options) => layoutApi.setShellComposition(mode, options),
        syncFromDom: (options) => layoutApi.syncFromDom && layoutApi.syncFromDom(options),
        rebalanceWorkbench: () => layoutApi.rebalanceWorkbench && layoutApi.rebalanceWorkbench(),
      }
    : null;
  initThemeSelector();
  initLocalTabs();
  initAliasSearch();
  initInspector(layoutApi);
  window.PortalInterfacePanel = window.PortalInspector;
})();
