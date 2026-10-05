#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
GALLERY = ROOT / "gallery.json"

def fail(msg):
    print(f"[FAIL] {msg}", file=sys.stderr)
    raise SystemExit(1)

def extract(script, name, next_marker):
    marker = f"const {name}="
    try:
        a = script.index(marker) + len(marker)
        b = script.index(next_marker, a)
    except ValueError as exc:
        fail(f"cannot locate {name}: {exc}")
    raw = script[a:b].strip().rstrip(";")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"{name} is not exact JSON: {exc}")

def main():
    if not INDEX.exists() or not GALLERY.exists():
        fail("index.html or gallery.json missing")

    html = INDEX.read_text(encoding="utf-8")
    match = re.search(r"<script>(.*)</script>", html, re.S)
    if not match:
        fail("main <script> block not found")
    script = match.group(1)

    embedded_index = extract(script, "EMBEDDED_INDEX", "const EMBEDDED_REGISTRY=")
    registry = extract(script, "EMBEDDED_REGISTRY", "const EMBEDDED_ASSETS=")
    assets = extract(script, "EMBEDDED_ASSETS", "let idx")
    gallery = json.loads(GALLERY.read_text(encoding="utf-8"))

    if gallery != registry:
        fail("gallery.json differs from EMBEDDED_REGISTRY")

    entries = registry.get("entries", [])
    ids = [e.get("class_id") for e in entries]
    if None in ids or len(ids) != len(set(ids)):
        fail("registry contains missing or duplicate class_id")

    asset_ids = set(assets)
    entry_ids = set(ids)
    if asset_ids != entry_ids:
        missing = sorted(entry_ids - asset_ids)
        extra = sorted(asset_ids - entry_ids)
        fail(f"asset/registry key mismatch; missing={missing[:8]} extra={extra[:8]}")

    published = [e["class_id"] for e in entries if e.get("status") == "PUBLISHED_PUBLIC"]
    missing_public = [cid for cid in published if cid not in assets]
    if missing_public:
        fail(f"PUBLISHED_PUBLIC entries missing assets: {missing_public[:8]}")

    for cid, manifest in assets.items():
        if not isinstance(manifest, dict):
            fail(f"{cid}: manifest is not an object")
        if manifest.get("class_id") != cid:
            fail(f"{cid}: manifest class_id mismatch")
        variants = manifest.get("variants")
        flat_assets = manifest.get("assets")
        if variants is None and flat_assets is None:
            fail(f"{cid}: no variants/assets payload")

    node = shutil.which("node")
    if not node:
        fail("node is required for JavaScript syntax validation")
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as fh:
        fh.write(script)
        js_path = fh.name
    try:
        proc = subprocess.run([node, "--check", js_path], capture_output=True, text=True)
        if proc.returncode:
            fail("JavaScript syntax check failed:\n" + (proc.stderr or proc.stdout))
    finally:
        Path(js_path).unlink(missing_ok=True)

    print("[PASS] SceneX Encyclopedia publish validation")
    print(f"       entries={len(entries)} assets={len(assets)} published_public={len(published)}")
    print(f"       generated_from_commit={registry.get('generated_from_commit','—')}")
    print(f"       families={len(embedded_index.get('families', []))}")

if __name__ == "__main__":
    main()
