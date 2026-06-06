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

import logging
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

VALID_KINDS = ("icon", "image", "document", "audio", "profile")

# Galleries live under <webapps_root>/clients/_shared/site-core/<gallery>/.
_SITE_CORE_REL = ("clients", "_shared", "site-core")
_GALLERY_BY_KIND = {
    "icon": "icon",
    "image": "image",
    "document": "document",
    "audio": "audio",
    "profile": "profiles",
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


def _build_filename(
    kind: str,
    *,
    slug: str,
    given_name: str,
    owner: str,
    ext: str,
) -> str:
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
    if kind != "profile":
        owner = _require_safe_segment(owner, field="owner")
    else:
        owner = str(owner or "").strip()  # not used in the profile filename

    # Resolve final bytes + extension per kind.
    if kind == "image":
        final_bytes, ext = _resolve_image(file_bytes, slug)
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
