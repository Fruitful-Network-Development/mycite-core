#!/usr/bin/env python3
"""Portal icon-leaflet registry — the scriptable rename tool for portal UI icons.

Every portal icon is referenced through ``iconImg(name)`` (portal.js), where ``name`` is a
LOGICAL key mapped to a ``mycite-ui`` leaflet token by the ``MC_ICONS`` table in portal.js.
This makes the registry the single source of truth, mirroring the website asset manifests
(``clients/_shared/site-core/scripts/manifest_lint.py``): a leaflet rename touches only the
map (+ the on-disk file), never the call sites.

Commands::

    portal_icon_manifest.py check
        Verify every mapped leaflet exists on disk AND every iconImg("x") call site
        references a known logical name. Exit 1 on any violation.

    portal_icon_manifest.py retarget <logical> <new_leaf>
        Rename the on-disk leaflet (mycite-ui.<old_leaf>.svg -> mycite-ui.<new_leaf>.svg)
        and repoint MC_ICONS[<logical>] -> <new_leaf>. Call sites are untouched.

    portal_icon_manifest.py rename <old_logical> <new_logical>
        Change the logical key in MC_ICONS and rewrite every iconImg("old")/('old') call
        site across portal static/ + templates/ to the new logical name.

The shared icon dir resolves from ``MYCITE_WEBAPPS_ROOT`` (default ``/srv/webapps``).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]  # .../MyCiteV2
PORTAL_STATIC = REPO_ROOT / "instances/_shared/portal_host/static"
PORTAL_TEMPLATES = REPO_ROOT / "instances/_shared/portal_host/templates"
PORTAL_JS = PORTAL_STATIC / "portal.js"

LEAFLET_FMT = "0000-00-00.artifact-icon.mycite-ui.{leaf}.svg"
_MAP_BLOCK_RE = re.compile(r"const MC_ICONS = \{(.*?)\};", re.DOTALL)
_MAP_ENTRY_RE = re.compile(r"(\w+)\s*:\s*\"([^\"]+)\"")
_CALL_RE = re.compile(r"""iconImg\(\s*['"]([A-Za-z0-9_]+)['"]""")


def icon_dir() -> Path:
    root = os.environ.get("MYCITE_WEBAPPS_ROOT") or "/srv/webapps"
    return Path(root) / "clients" / "_shared" / "site-core" / "icon"


def parse_map(js_text: str) -> dict[str, str]:
    block = _MAP_BLOCK_RE.search(js_text)
    if not block:
        raise SystemExit("portal.js: could not find the MC_ICONS map block")
    return dict(_MAP_ENTRY_RE.findall(block.group(1)))


def _portal_source_files() -> list[Path]:
    files: list[Path] = []
    for base in (PORTAL_STATIC, PORTAL_TEMPLATES):
        if base.exists():
            files.extend(sorted(base.glob("*.js")))
            files.extend(sorted(base.glob("*.html")))
    return files


def call_sites() -> dict[str, list[str]]:
    """logical name -> list of files that call iconImg("name")."""
    out: dict[str, list[str]] = {}
    for f in _portal_source_files():
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for name in set(_CALL_RE.findall(text)):
            out.setdefault(name, []).append(f.name)
    return out


def cmd_check() -> int:
    icons = parse_map(PORTAL_JS.read_text(encoding="utf-8"))
    idir = icon_dir()
    problems: list[str] = []
    info: list[str] = []
    # 1. every mapped leaflet exists on disk (skip if the shared tree is absent, e.g. CI)
    if idir.exists():
        for logical, leaf in sorted(icons.items()):
            path = idir / LEAFLET_FMT.format(leaf=leaf)
            if not path.exists():
                problems.append(f"missing leaflet for '{logical}': {path}")
    else:
        info.append(f"icon dir absent ({idir}) — skipped on-disk leaflet check")
    # 2. every call site references a known logical name
    sites = call_sites()
    for name, files in sorted(sites.items()):
        if name not in icons:
            problems.append(f"iconImg('{name}') in {files} but '{name}' is not in MC_ICONS")
    # 3. report unused mapped icons (info, not an error)
    for logical in sorted(icons):
        if logical not in sites:
            info.append(f"mapped but unused: '{logical}'")
    for line in info:
        print(f"  info: {line}")
    if problems:
        for line in problems:
            print(f"  FAIL: {line}")
        print(f"portal_icon_manifest: {len(problems)} problem(s)")
        return 1
    print(f"portal_icon_manifest: OK ({len(icons)} icons, {len(sites)} referenced)")
    return 0


def _rewrite_map_value(js_text: str, logical: str, new_leaf: str) -> str:
    block = _MAP_BLOCK_RE.search(js_text)
    if not block:
        raise SystemExit("portal.js: MC_ICONS block not found")
    body = block.group(1)
    new_body, n = re.subn(
        rf"(\b{re.escape(logical)}\s*:\s*\")[^\"]+(\")", rf"\g<1>{new_leaf}\g<2>", body
    )
    if n != 1:
        raise SystemExit(f"portal.js: expected exactly one '{logical}' entry, changed {n}")
    return js_text[: block.start(1)] + new_body + js_text[block.end(1) :]


def cmd_retarget(logical: str, new_leaf: str) -> int:
    js_text = PORTAL_JS.read_text(encoding="utf-8")
    icons = parse_map(js_text)
    if logical not in icons:
        raise SystemExit(f"unknown logical icon '{logical}'")
    old_leaf = icons[logical]
    idir = icon_dir()
    old_path = idir / LEAFLET_FMT.format(leaf=old_leaf)
    new_path = idir / LEAFLET_FMT.format(leaf=new_leaf)
    if old_path.exists():
        old_path.rename(new_path)
        print(f"renamed leaflet {old_path.name} -> {new_path.name}")
    else:
        print(f"warning: leaflet {old_path} absent — only the map is updated")
    PORTAL_JS.write_text(_rewrite_map_value(js_text, logical, new_leaf), encoding="utf-8")
    print(f"MC_ICONS['{logical}'] -> '{new_leaf}'")
    return 0


def cmd_rename(old_logical: str, new_logical: str) -> int:
    js_text = PORTAL_JS.read_text(encoding="utf-8")
    icons = parse_map(js_text)
    if old_logical not in icons:
        raise SystemExit(f"unknown logical icon '{old_logical}'")
    if new_logical in icons:
        raise SystemExit(f"'{new_logical}' already exists")
    # change the key in the MC_ICONS block
    block = _MAP_BLOCK_RE.search(js_text)
    new_body, n = re.subn(
        rf"\b{re.escape(old_logical)}(\s*:\s*\")", rf"{new_logical}\g<1>", block.group(1)
    )
    if n != 1:
        raise SystemExit(f"portal.js: expected one '{old_logical}' key, changed {n}")
    js_text = js_text[: block.start(1)] + new_body + js_text[block.end(1) :]
    PORTAL_JS.write_text(js_text, encoding="utf-8")
    # rewrite call sites across portal source
    rewrites = 0
    for f in _portal_source_files():
        text = f.read_text(encoding="utf-8")
        new_text = re.sub(
            rf"(iconImg\(\s*['\"]){re.escape(old_logical)}(['\"])", rf"\g<1>{new_logical}\g<2>", text
        )
        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            rewrites += 1
    print(f"renamed logical '{old_logical}' -> '{new_logical}' ({rewrites} file(s) rewritten)")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "check":
        return cmd_check()
    if argv[0] == "retarget" and len(argv) == 3:
        return cmd_retarget(argv[1], argv[2])
    if argv[0] == "rename" and len(argv) == 3:
        return cmd_rename(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
