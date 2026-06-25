/* MyCite Portal JS
 * - Theme selector
 * - Local tab switching for page-internal panels
 * - Alias sidebar filter
 * - Workbench + Interface Panel shell splitters
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
    const workbench = qs(".ide-workbench");
    const ideBody = qs(".ide-body");
    if (!shell || !controlPanel || !workbench) return null;
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
          minControlPanelWidth: 188,
          maxControlPanelWidth: 360,
          minWorkbenchWidth: 920,
        };
      }
      return {
        defaultControlPanelWidth: 280,
        minControlPanelWidth: 220,
        maxControlPanelWidth: 420,
        minWorkbenchWidth: 720,
      };
    }

    function workbenchIsOpen() {
      return shell.getAttribute("data-workbench-collapsed") !== "true";
    }

    function applyControlPanelWidth(value) {
      const policy = currentLayoutPolicy();
      const width = clamp(value, policy.minControlPanelWidth, policy.maxControlPanelWidth);
      shell.style.setProperty("--ide-controlpanel-w", `${width}px`);
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

    function canHideWorkbench() {
      // No interface panel to swap to — the workbench is always the visible primary surface.
      return false;
    }

    function rebalanceWorkbench() {
      if (!ideBody || window.matchMedia("(max-width: 960px)").matches) return;
      const composition = currentShellComposition();
      const policy = currentLayoutPolicy();
      const workbenchOpen = workbenchIsOpen();
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
      const controlPanelSplitterWidth = controlPanelOpen ? splitterWidth : 0;
      let workbenchWidth = bodyWidth - activityWidth - controlPanelWidth - controlPanelSplitterWidth;

      if (workbenchWidth >= policy.minWorkbenchWidth) {
        shell.classList.remove("ide-shell--workbench-tight");
        return;
      }

      let deficit = policy.minWorkbenchWidth - workbenchWidth;
      if (deficit > 0 && controlPanelOpen && controlPanelWidth > policy.minControlPanelWidth) {
        const nextControlPanelWidth = Math.max(policy.minControlPanelWidth, controlPanelWidth - deficit);
        deficit -= controlPanelWidth - nextControlPanelWidth;
        controlPanelWidth = applyControlPanelWidth(nextControlPanelWidth);
      }

      workbenchWidth = bodyWidth - activityWidth - controlPanelWidth - controlPanelSplitterWidth;
      shell.classList.toggle("ide-shell--workbench-tight", workbenchWidth < policy.minWorkbenchWidth);
    }

    function syncShellToggleButtons(options) {
      syncToolPanelLockScope(options);
      qsa("[data-shell-toggle]", shell).forEach(button => {
        const target = button.getAttribute("data-shell-toggle") || "";
        const baseTitle = button.getAttribute("data-shell-title") || button.getAttribute("aria-label") || "";
        let isOpen = false;
        if (target === "control-panel") {
          isOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
        }
        button.classList.toggle("is-active", isOpen);
        button.setAttribute("aria-pressed", isOpen ? "true" : "false");
        button.disabled = false;
        if (baseTitle) button.setAttribute("title", baseTitle);
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
      // The workbench is the only primary surface now (the interface-panel sidebar was
      // removed), so it is always visible regardless of the requested state.
      applyWorkbenchVisibility(true);
      syncShellToggleButtons();
      if (persist) {
        try { window.localStorage.setItem(WORKBENCH_OPEN_KEY, "1"); } catch (_) {}
      }
      rebalanceWorkbench();
      return true;
    }

    let firstV2ShellCompositionApplied = false;

    function applyShellPostureFromDom(options) {
      const opts = options || {};
      const routeKey = currentRouteKey(opts);
      const fromShellComposition = opts.fromShellComposition === true;
      const controlPanelOpen = shell.getAttribute("data-control-panel-collapsed") !== "true";
      applyControlPanelVisibility(controlPanelOpen);
      // The workbench is always visible (the interface-panel sidebar was removed).
      applyWorkbenchVisibility(true);
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
      document.dispatchEvent(new CustomEvent("mycite:shell:composition-changed", { detail: { composition } }));
      syncShellToggleButtons({ routeKey: routeKey });
      rebalanceWorkbench();
    }

    const storedControlPanel = parseInt(getStoredValue(CONTROL_PANEL_WIDTH_KEY), 10);
    const storedControlPanelOpen = getStoredValue(CONTROL_PANEL_OPEN_KEY);
    const initialPolicy = currentLayoutPolicy();

    setControlPanelWidth(storedControlPanel || initialPolicy.defaultControlPanelWidth, false);
    if (shellDriverV2) {
      applyShellPostureFromDom({ useStoredWorkbenchPreference: false });
    } else {
      setControlPanelOpen(storedControlPanelOpen !== "0", false);
      setWorkbenchOpen(true, false);
    }
    setShellComposition(currentShellComposition());
    rebalanceWorkbench();

    qsa("[data-splitter]", shell).forEach(splitter => {
      splitter.addEventListener("pointerdown", event => {
        const type = splitter.getAttribute("data-splitter") || "";
        if (type !== "control-panel") return;
        const startX = event.clientX;
        const startControlPanel = parseInt(getComputedStyle(shell).getPropertyValue("--ide-controlpanel-w"), 10) || 280;

        function onMove(moveEvent) {
          setControlPanelWidth(startControlPanel + (moveEvent.clientX - startX), false);
        }

        function onUp() {
          const width = parseInt(getComputedStyle(shell).getPropertyValue("--ide-controlpanel-w"), 10) || startControlPanel;
          setControlPanelWidth(width, true);
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
      }
    }

    function toggleShellRegionLocally(target) {
      if (target === "control-panel") {
        setControlPanelOpen(shell.getAttribute("data-control-panel-collapsed") === "true", true);
      }
    }

    qsa("[data-shell-toggle]", shell).forEach(button => {
      const target = button.getAttribute("data-shell-toggle") || "";
      button.addEventListener("click", () => {
        if (shellDriverV2) {
          dispatchShellToggleRequest(target);
          return;
        }
        toggleShellRegionLocally(target);
      });
    });

    window.addEventListener("resize", rebalanceWorkbench);

    return {
      setControlPanelOpen,
      setWorkbenchOpen,
      setShellComposition,
      syncFromDom: applyShellPostureFromDom,
      rebalanceWorkbench,
    };
  }

  const layoutApi = initWorkbenchLayout();
  window.PortalShell = layoutApi
    ? {
        setWorkbenchOpen: (open, persist) => layoutApi.setWorkbenchOpen(!!open, persist !== false),
        setControlPanelOpen: (open, persist) => layoutApi.setControlPanelOpen(!!open, persist !== false),
        setShellComposition: (mode, options) => layoutApi.setShellComposition(mode, options),
        syncFromDom: (options) => layoutApi.syncFromDom && layoutApi.syncFromDom(options),
        rebalanceWorkbench: () => layoutApi.rebalanceWorkbench && layoutApi.rebalanceWorkbench(),
      }
    : null;
  initThemeSelector();
  initLocalTabs();
  initAliasSearch();
})();
