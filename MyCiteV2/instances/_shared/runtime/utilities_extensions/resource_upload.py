"""resource_upload — operator resource upload + raster→AVIF normalization.

Wave-1 backend for the FND portal's "upload a site-core asset" capability.
``handle_upload`` accepts raw uploaded bytes plus the operator-chosen
title/slug/given-name/owner, builds a destination filename that matches the
site-core gallery naming convention, and writes the artifact into the correct
gallery under ``<webapps_root>/clients/_shared/site-core/``:

  - icon/      .svg              (icons stay as-is)
  - image/     .avif (preferred) raster PNG/JPEG is converted to AVIF via the
                                 ``avifenc`` binary; an already-AVIF upload is
                                 passed through; other raster types are rejected
  - document/  keeps its ext     (.pdf etc.)
  - profiles/  .yaml             (profile YAML)

Filename convention (matches the live galleries):

  image / icon / document:
    0000-00-00.artifact-<kind>.<owner>.<slug>.<ext>
  profile:
    0000-00-00.artifact-profile-<given_name>.<slug>.profile.yaml
      where <given_name> is ``legal_entity`` or ``natural_entity``.

The AVIF conversion shells out to ``avifenc`` (installed at /usr/bin/avifenc)
via ``subprocess.run`` with an argument LIST — never a shell string — so there
is no shell-injection surface. ``slug``/``owner``/``given_name`` are validated
against a strict allow-list and rejected if they contain path separators or
traversal so a caller cannot escape the gallery directory.

The Wave-2 UI adds the upload form + manifest-add affordance; this module is
the pure backend (no Flask dependency) so it can be unit-tested directly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

_log = logging.getLogger("mycite.portal_host")

# Binary that converts PNG/JPEG → AVIF. Pinned to the installed absolute path
# so PATH manipulation cannot redirect it. If the binary is missing, conversion
# raises a clear UploadError rather than silently falling back.
_AVIFENC_BIN = "/usr/bin/avifenc"
_AVIFENC_MAX_AS = 2 * 1024 * 1024 * 1024  # 2 GiB address-space cap for avifenc

# Logo leaflets are 512×512 transparent-canvas AVIFs (the master-manifest
# convention). The portal venv deliberately has no Pillow — process_logos.py
# isolates raster encoding in a dedicated venv and re-invokes itself as the
# ``_encode-batch`` worker under it. The ``logo`` upload kind reuses exactly
# that proven worker (no second copy of the fit-to-512² canvas logic). The venv
# path mirrors process_logos.py's ``VENV_PY`` and is env-overridable for tests
# and alternate hosts; the script itself lives under the site-core tree
# (derived from ``webapps_root``, already a hard dependency of this module).
_DEFAULT_LOGO_ENCODER_PY = "/srv/agentic/venvs/logo-proc/bin/python"


def _logo_encoder_py() -> str:
    """The Python that runs the isolated Pillow worker, read at call time so the
    env override applies without a reimport (and so tests can point it at a stub)."""
    return os.environ.get("MYCITE_LOGO_ENCODER_PYTHON", _DEFAULT_LOGO_ENCODER_PY)

VALID_KINDS = ("icon", "image", "document", "audio", "profile", "logo")

# Galleries live under <webapps_root>/clients/_shared/site-core/<gallery>/.
_SITE_CORE_REL = ("clients", "_shared", "site-core")
_GALLERY_BY_KIND = {
    "icon": "icon",
    "image": "image",
    "document": "document",
    "audio": "audio",
    "profile": "profiles",
    # Logos are brand marks stored in the shared image/ gallery alongside the
    # existing 0000-00-00.artifact-logo.<slug>.logo.avif leaflets.
    "logo": "image",
}

# Raster inputs we accept for the image kind. Detection is by magic bytes, not
# by the (operator-supplied, untrusted) filename extension.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
# AVIF is an ISO-BMFF file: bytes 4..8 are "ftyp" and the major brand is one of
# the AVIF brands.
_AVIF_BRANDS = (b"avif", b"avis", b"av01")

# A safe path segment: lowercase/upper letters, digits, dash, underscore. No
# dots (blocks ".."), no slashes, no whitespace. This is the anti-traversal
# guard for every operator-supplied filename component.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# given_name for a profile must name the entity flavor.
_PROFILE_GIVEN_NAMES = ("legal_entity", "natural_entity")

# A plausible client domain (lowercase host with a dotted TLD). Used to scope a
# grantee upload to its own site dir.
_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+$")


def _as_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


class UploadError(ValueError):
    """Raised when an upload is malformed, unsupported, or unsafe."""


def _require_safe_segment(value: str, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise UploadError(f"{field} is required")
    if not _SAFE_SEGMENT.match(text):
        raise UploadError(
            f"{field} must contain only letters, digits, '-' or '_' "
            f"(got {value!r})"
        )
    return text


def _detect_image_kind(data: bytes) -> str:
    """Return 'png', 'jpeg', 'avif', or '' for unsupported/unknown bytes."""
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_JPEG_MAGIC):
        return "jpeg"
    # AVIF: "....ftyp<brand>" — brand sits at offset 8.
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in _AVIF_BRANDS:
        return "avif"
    return ""


def _ext_of(filename: str) -> str:
    """Lowercased extension WITHOUT the dot; '' when there is none.

    Only the suffix is used; the rest of the (untrusted) filename is discarded
    — the destination name is rebuilt from validated components.
    """
    suffix = Path(str(filename or "")).suffix
    return suffix[1:].lower() if suffix else ""


def _avifenc_rlimit() -> None:  # pragma: no cover - runs in the forked child
    """Cap the avifenc child's address space so a decompression-bomb image that
    slips past the header pixel-check can't OOM the single-worker portal host.
    2 GiB comfortably fits a legitimate <=40 MP encode but is far below the many
    GiB a multi-gigapixel raster would demand."""
    try:
        import resource as _res

        _res.setrlimit(_res.RLIMIT_AS, (_AVIFENC_MAX_AS, _AVIFENC_MAX_AS))
    except Exception:
        pass


def _convert_raster_to_avif(data: bytes, source_kind: str) -> bytes:
    """Write ``data`` to a temp file and run avifenc → return AVIF bytes."""
    with tempfile.TemporaryDirectory(prefix="resource_upload_") as tmpdir:
        src = Path(tmpdir) / f"src.{source_kind}"
        dst = Path(tmpdir) / "out.avif"
        src.write_bytes(data)
        try:
            completed = subprocess.run(
                [_AVIFENC_BIN, str(src), str(dst)],
                check=False,
                capture_output=True,
                timeout=120,
                preexec_fn=_avifenc_rlimit,
            )
        except FileNotFoundError as exc:
            raise UploadError(
                f"avifenc binary not found at {_AVIFENC_BIN}; cannot convert image"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise UploadError("avifenc timed out converting image") from exc
        if completed.returncode != 0 or not dst.exists():
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise UploadError(
                "avifenc failed to convert image"
                + (f": {detail}" if detail else "")
            )
        return dst.read_bytes()


def _resolve_image(data: bytes, slug: str) -> tuple[bytes, str]:
    """Return (final_bytes, ext) for an image upload, converting to AVIF."""
    detected = _detect_image_kind(data)
    if detected == "avif":
        return data, "avif"
    if detected in ("png", "jpeg"):
        return _convert_raster_to_avif(data, detected), "avif"
    raise UploadError(
        "unsupported image type: expected PNG, JPEG, or AVIF "
        "(detected by file content, not extension)"
    )


def _process_logos_script(webapps_root: str | Path) -> Path:
    """Path to the site-core logo pipeline whose ``_encode-batch`` worker we
    reuse to fit an uploaded brand mark onto a 512×512 transparent canvas."""
    return Path(webapps_root).joinpath(*_SITE_CORE_REL, "scripts", "process_logos.py")


def _resolve_logo(data: bytes, *, webapps_root: str | Path) -> tuple[bytes, str]:
    """Return (avif_bytes, "avif") for a logo upload, normalized to a 512×512
    transparent-canvas AVIF via process_logos.py's ``_encode-batch`` worker
    (run under the isolated Pillow venv). Raises :class:`UploadError` for an
    unsupported input or a missing/failed encoder."""
    detected = _detect_image_kind(data)
    if detected not in ("png", "jpeg", "avif"):
        raise UploadError(
            "unsupported logo image: expected PNG, JPEG, or AVIF "
            "(detected by file content, not extension)"
        )
    encoder = Path(_logo_encoder_py())
    script = _process_logos_script(webapps_root)
    if not encoder.exists():
        raise UploadError(
            f"logo encoder venv not found at {encoder}; cannot normalize logo "
            "(set MYCITE_LOGO_ENCODER_PYTHON)"
        )
    if not script.is_file():
        raise UploadError(
            f"logo pipeline not found at {script}; cannot normalize logo"
        )
    with tempfile.TemporaryDirectory(prefix="resource_logo_") as tmpdir:
        src = Path(tmpdir) / f"src.{detected}"
        dst = Path(tmpdir) / "out.avif"
        jobs = Path(tmpdir) / "jobs.json"
        results = Path(tmpdir) / "results.json"
        src.write_bytes(data)
        jobs.write_text(
            json.dumps([{"src": str(src), "dst": str(dst), "mode": "new"}])
        )
        try:
            completed = subprocess.run(
                [str(encoder), str(script), "_encode-batch", str(jobs), str(results)],
                check=False,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UploadError(f"logo normalization failed: {exc}") from exc
        if completed.returncode != 0 or not dst.exists():
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise UploadError(
                "logo normalization failed" + (f": {detail}" if detail else "")
            )
        return dst.read_bytes(), "avif"


def _build_filename(
    kind: str,
    *,
    slug: str,
    given_name: str,
    owner: str,
    ext: str,
) -> str:
    if kind == "logo":
        # Brand mark: no owner segment; the role token is "logo" and the slug
        # is the entity slug, so the name matches an existing profile's
        # predetermined logo_ref (0000-00-00.artifact-logo.<slug>.logo) and
        # resolves automatically without any profile edit.
        return f"0000-00-00.artifact-logo.{slug}.logo.{ext}"
    if kind == "profile":
        given = _require_safe_segment(given_name, field="given_name")
        # The personhood token may carry an optional -<industry> dash spec
        # (e.g. legal_entity-ag); validate the base token, per the naming
        # convention that dashes are a secondary extension of a dot-field.
        base = given.split("-", 1)[0]
        if base not in _PROFILE_GIVEN_NAMES:
            raise UploadError(
                "given_name for a profile must be 'legal_entity' or "
                f"'natural_entity' (optionally with a -<industry> suffix; "
                f"got {given_name!r})"
            )
        return f"0000-00-00.artifact-profile-{given}.{slug}.profile.yaml"
    # icon / image / document share the same shape.
    return f"0000-00-00.artifact-{kind}.{owner}.{slug}.{ext}"


def handle_upload(
    file_bytes: bytes,
    filename: str,
    kind: str,
    *,
    title: str,
    slug: str,
    given_name: str,
    owner: str,
    webapps_root: str | Path,
) -> dict[str, Any]:
    """Validate, normalize, and store an uploaded site-core artifact.

    Returns ``{"asset_id", "asset_path", "gallery"}`` on success. Raises
    :class:`UploadError` for any malformed / unsupported / unsafe input.
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise UploadError("file_bytes must be bytes")
    file_bytes = bytes(file_bytes)
    if not file_bytes:
        raise UploadError("file is empty")

    kind = str(kind or "").strip().lower()
    if kind not in VALID_KINDS:
        raise UploadError(
            f"kind must be one of {VALID_KINDS} (got {kind!r})"
        )

    # title is operator metadata only; it is not part of the path, so it does
    # not need traversal validation — only a non-empty check.
    if not str(title or "").strip():
        raise UploadError("title is required")

    # Validate the path-bearing components up front (anti-traversal).
    slug = _require_safe_segment(slug, field="slug")
    if kind not in ("profile", "logo"):
        owner = _require_safe_segment(owner, field="owner")
    else:
        owner = str(owner or "").strip()  # not used in the profile/logo filename

    # Resolve final bytes + extension per kind.
    if kind == "image":
        final_bytes, ext = _resolve_image(file_bytes, slug)
    elif kind == "logo":
        final_bytes, ext = _resolve_logo(file_bytes, webapps_root=webapps_root)
    elif kind == "icon":
        upload_ext = _ext_of(filename)
        if upload_ext and upload_ext != "svg":
            raise UploadError(
                f"icons must be SVG (got '.{upload_ext}')"
            )
        final_bytes, ext = file_bytes, "svg"
    elif kind in ("document", "audio"):
        ext = _ext_of(filename)
        if not ext:
            raise UploadError(f"{kind} upload must have a file extension")
        if not _SAFE_SEGMENT.match(ext):
            raise UploadError(f"unsafe {kind} extension: {ext!r}")
        final_bytes, ext = file_bytes, ext
    else:  # profile
        final_bytes, ext = file_bytes, "yaml"

    dest_name = _build_filename(
        kind,
        slug=slug,
        given_name=given_name,
        owner=owner,
        ext=ext,
    )

    gallery = _GALLERY_BY_KIND[kind]
    site_core = Path(webapps_root).joinpath(*_SITE_CORE_REL)
    gallery_dir = site_core / gallery
    gallery_dir.mkdir(parents=True, exist_ok=True)

    dest_path = gallery_dir / dest_name
    # Defense in depth: confirm the resolved destination stays inside the
    # gallery even after the (already-validated) name is joined.
    resolved = dest_path.resolve()
    if gallery_dir.resolve() not in resolved.parents:
        raise UploadError("resolved destination escapes the gallery directory")

    # Atomic-ish write: write to a temp sibling then replace, so a partial
    # write never leaves a half-written artifact in the gallery.
    tmp_path = gallery_dir / f".{dest_name}.{uuid.uuid4().hex}.tmp"
    try:
        tmp_path.write_bytes(final_bytes)
        tmp_path.replace(dest_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    asset_id = dest_name
    _log.info("resource_upload stored %s in %s", asset_id, gallery)
    return {
        "asset_id": asset_id,
        "asset_path": str(dest_path),
        "gallery": gallery,
    }


# Grantee dashboard uploads are intentionally narrower than the operator path
# above: a client may only add IMAGES (forced to AVIF) and DOCUMENTS to its OWN
# site, selecting from these existing artifact kinds. It cannot create or edit
# artifact TYPES/icons, upload a profile/logo/icon, or write to another site.
_GRANTEE_UPLOAD_KINDS = ("image", "document")
# Inert document extensions only — never active content (html/svg/xml/js) that
# would execute same-origin as the dashboard if a visitor opened the file.
_GRANTEE_DOC_EXTS = (
    "pdf", "txt", "csv", "md", "rtf",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
)
# Uploaded bytes land in the SHARED site-core gallery — the canonical store nginx
# aliases /assets/{images,document}/ to (clients/_shared/site-core/{image,document}/),
# keyed by the grantee's own entity so two sites never collide. The public URL
# segment ("images" plural) differs from the gallery dir name ("image").
_GRANTEE_GALLERY_DIR = {"image": "image", "document": "document"}
_GRANTEE_URL_SEGMENT = {"image": "images", "document": "document"}
_GRANTEE_ARTIFACT_TOKEN = {"image": "artifact-image", "document": "artifact-document"}
# Server-side caps (belt-and-suspenders to nginx's 12m request cap).
_GRANTEE_MAX_BYTES = 10 * 1024 * 1024          # 10 MiB per uploaded file
_GRANTEE_MAX_IMAGE_PIXELS = 40_000_000         # 40 MP — blocks a decode bomb


_IMAGE_PIXELS_SUSPECT = 1 << 60  # forces rejection by any sane pixel cap


def _image_pixel_count(data: bytes) -> int:
    """width*height read from a PNG/JPEG header WITHOUT decoding the raster, so a
    decompression-bomb image (tiny compressed, billions of pixels) is rejected
    before avifenc allocates the full bitmap. Returns 0 when undetermined (e.g.
    AVIF, already a bounded compressed format), or a huge sentinel when the JPEG
    segment structure is internally inconsistent — e.g. a crafted segment length
    that would skip the real SOF — so the caller rejects rather than trusts a
    misleading 0. (avifenc additionally runs under a hard address-space cap.)"""
    if data[:8] == _PNG_MAGIC and len(data) >= 24:
        return int.from_bytes(data[16:20], "big") * int.from_bytes(data[20:24], "big")
    if data[:3] == _JPEG_MAGIC:
        i, n = 2, len(data)
        while i + 1 < n:
            if data[i] != 0xFF:
                return _IMAGE_PIXELS_SUSPECT  # not at a marker boundary → length lied
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1  # fill byte run
                continue
            if marker in (0xD9, 0xDA):  # EOI / start-of-scan reached, no SOF seen
                return 0
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:  # standalone markers, no length
                i += 2
                continue
            if i + 4 > n:
                return _IMAGE_PIXELS_SUSPECT
            seg_len = int.from_bytes(data[i + 2:i + 4], "big")
            if seg_len < 2 or i + 2 + seg_len > n:  # length absurd / runs off the end
                return _IMAGE_PIXELS_SUSPECT
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):  # SOFn
                if i + 9 > n:
                    return _IMAGE_PIXELS_SUSPECT
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return w * h
            i += 2 + seg_len
    return 0


def _grantee_entity_for_domain(domain: str) -> str:
    """Stable site-entity slug for an AUTO-CREATED manifest: the first DNS label,
    snake-cased (rubycorpus.com → 'rubycorpus'). Sites the operator already set
    up ship a manifest carrying the human legal-entity slug, which this never
    overrides (it is only consulted when no manifest exists)."""
    first = domain.split(".", 1)[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", first).strip("_") or "site"


def _atomic_write_manifest(path: Path, data: dict[str, Any]) -> None:
    """Served-perms atomic YAML write for the record-manifest (preserve dest
    mode, else 0644 so nginx can still serve the site). Thin shim over the shared
    :func:`atomic_io.atomic_write_yaml`."""
    from MyCiteV2.packages.adapters.filesystem.atomic_io import atomic_write_yaml

    atomic_write_yaml(path, data)


def handle_grantee_upload(
    file_bytes: bytes,
    filename: str,
    kind: str,
    *,
    title: str,
    slug: str,
    domain: str,
    clients_root: str | Path,
) -> dict[str, Any]:
    """Grantee-scoped upload of an image (→AVIF) or inert document into the
    SHARED site-core gallery (where nginx serves /assets/{images,document}/ from),
    keyed by the caller site's entity, and registered in that site's
    shared-resources record-manifest so it appears in the dashboard
    Library/Browse. Image/document only — no type/icon/profile creation. The
    manifest is read-modify-written under an exclusive file lock; a missing
    manifest is auto-created. Returns ``{asset_id, asset_path, kind}``.
    """
    import fcntl

    import yaml

    if not isinstance(file_bytes, (bytes, bytearray)) or not bytes(file_bytes):
        raise UploadError("file is empty")
    file_bytes = bytes(file_bytes)
    if len(file_bytes) > _GRANTEE_MAX_BYTES:
        raise UploadError(f"file too large (max {_GRANTEE_MAX_BYTES // (1024 * 1024)} MiB)")
    kind = _as_text(kind).lower()
    if kind not in _GRANTEE_UPLOAD_KINDS:
        raise UploadError(
            f"kind must be one of {_GRANTEE_UPLOAD_KINDS} (got {kind!r})"
        )
    if not _as_text(title):
        raise UploadError("title is required")
    slug = _require_safe_segment(slug, field="slug")
    domain = _as_text(domain).lower()
    if not _DOMAIN_RE.match(domain):
        raise UploadError("invalid domain")

    clients_root = Path(clients_root)
    frontend = clients_root / domain / "frontend"
    if not frontend.is_dir():
        raise UploadError("unknown site")
    assets_dir = frontend / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Resolve final bytes + extension per kind (before the lock).
    if kind == "image":
        pixels = _image_pixel_count(file_bytes)
        if pixels > _GRANTEE_MAX_IMAGE_PIXELS:
            raise UploadError(
                f"image too large ({pixels:,} px; max {_GRANTEE_MAX_IMAGE_PIXELS:,})"
            )
        final_bytes, ext = _resolve_image(file_bytes, slug)
    else:  # document
        ext = _ext_of(filename).lower()
        if ext not in _GRANTEE_DOC_EXTS:
            raise UploadError(
                f"document type '.{ext or '?'}' is not allowed; use one of: "
                + ", ".join(_GRANTEE_DOC_EXTS)
            )
        final_bytes = file_bytes

    # Serialize concurrent uploads for this site: two gunicorn workers otherwise
    # race the manifest read-modify-write and one append is lost. The lock lives
    # in the system temp dir (shared across workers on the host), never in the
    # served/tracked site tree. domain is _DOMAIN_RE-validated → safe filename.
    lock_path = os.path.join(tempfile.gettempdir(), f"mycite-upload-{domain}.lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        manifests = sorted(assets_dir.glob("*record-manifest*.shared_resources.yaml"))
        if manifests:
            man_path = manifests[0]
            try:
                data = yaml.safe_load(man_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise UploadError("could not read resource manifest") from exc
            if not isinstance(data, dict):
                raise UploadError("malformed resource manifest")
            man_domain = _as_text(data.get("site_domain")).lower()
            if man_domain and man_domain != domain:
                raise UploadError("manifest domain mismatch")
            site_entity = _as_text(data.get("site_entity")) or _grantee_entity_for_domain(domain)
        else:
            site_entity = _grantee_entity_for_domain(domain)
            man_path = assets_dir / (
                f"0000-00-00.record-manifest.{site_entity}-website.shared_resources.yaml"
            )
            data = {
                "manifest_kind": "shared_resources",
                "site_entity": site_entity,
                "site_domain": domain,
                "resources": {},
            }

        asset_id = f"0000-00-00.{_GRANTEE_ARTIFACT_TOKEN[kind]}.{site_entity}.{slug}"
        dest_name = f"{asset_id}.{ext}"
        gallery_dir = clients_root.joinpath("_shared", "site-core", _GRANTEE_GALLERY_DIR[kind])
        gallery_dir.mkdir(parents=True, exist_ok=True)
        dest_path = gallery_dir / dest_name
        if gallery_dir.resolve() not in dest_path.resolve().parents:
            raise UploadError("resolved destination escapes the gallery directory")
        asset_web_path = f"/assets/{_GRANTEE_URL_SEGMENT[kind]}/{dest_name}"

        # Build the manifest entry (replace any same-id entry, else append),
        # remembering the on-disk name of a superseded same-id asset so a
        # different-extension re-upload doesn't orphan the old bytes.
        resources = data.setdefault("resources", {})
        if not isinstance(resources, dict):
            raise UploadError("malformed resource manifest resources")
        bucket = resources.setdefault(kind, [])
        if not isinstance(bucket, list):
            raise UploadError(f"malformed resource manifest resources.{kind}")
        superseded = {
            _as_text(e.get("asset_path")).rsplit("/", 1)[-1]
            for e in bucket
            if isinstance(e, dict) and _as_text(e.get("asset_id")) == asset_id
        }
        bucket[:] = [
            e for e in bucket
            if not (isinstance(e, dict) and _as_text(e.get("asset_id")) == asset_id)
        ]
        bucket.append({
            "asset_id": asset_id,
            "asset_path": asset_web_path,
            "consumers": [],
            "entity_scope": site_entity,
        })

        # Commit ORDER: stage bytes → write manifest → replace into the gallery.
        # The dest file is only touched AFTER the manifest is durably written, so
        # a manifest-write failure leaves the prior asset + manifest intact (no
        # data loss, no never-listed orphan).
        tmp = gallery_dir / f".{dest_name}.{uuid.uuid4().hex}.tmp"
        try:
            tmp.write_bytes(final_bytes)
            os.chmod(tmp, 0o644)                     # other-readable for nginx
            _atomic_write_manifest(man_path, data)   # manifest first
            tmp.replace(dest_path)                   # then commit the bytes
        finally:
            if tmp.exists():
                tmp.unlink()
        # Drop a superseded same-id file whose name (extension) changed.
        for old_name in superseded:
            if old_name and old_name != dest_name:
                try:
                    (gallery_dir / old_name).unlink()
                except OSError:
                    pass
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    _log.info("grantee_upload stored %s for %s", asset_id, domain)
    return {"asset_id": asset_id, "asset_path": asset_web_path, "kind": kind}
