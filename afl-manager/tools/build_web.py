#!/usr/bin/env python3
"""Bundle the Python engine for the browser app.

The app runs the ``aflm`` package unchanged inside the browser.  This script
packs its source files into web/engine.json, which the app loads at start-up.
Run it after changing anything in aflm/:

    python tools/build_web.py           # write the bundle
    python tools/build_web.py --check   # exit 1 if the bundle is out of date
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "engine.json"


def build() -> str:
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "aflm").glob("*.py"))}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
    return json.dumps({"version": digest, "files": files}, indent=0)


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("engine bundle is up to date" if ok else "engine bundle is STALE - run tools/build_web.py")
        sys.exit(0 if ok else 1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text) // 1024} KB, {len(json.loads(text)['files'])} files)")
