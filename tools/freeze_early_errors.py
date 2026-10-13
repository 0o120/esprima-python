"""Freeze selected published-standard Test262 parse-phase negative inputs.

Usage: python tools/freeze_early_errors.py PATH_TO_PINNED_TEST262
No JavaScript is executed. Sources retain copyright headers and provenance.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_grammar_reference import REVISION, array


def main():
    checkout = Path(sys.argv[1]).resolve()
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != REVISION:
        raise SystemExit("Test262 checkout differs from the pinned revision")
    proposed = (checkout / "features.txt").read_text(encoding="utf-8").split("## Standard language features")[0]
    excluded = {line.split("#", 1)[0].strip() for line in proposed.splitlines() if line.split("#", 1)[0].strip()}
    excluded.add("explicit-resource-management")
    cases, omitted = [], Counter()
    for path in sorted((checkout / "test/language").rglob("*.js")):
        source = path.read_text(encoding="utf-8")
        match = re.search(r"/\*---(.*?)---\*/", source, re.DOTALL)
        if not match:
            continue
        metadata = match.group(1)
        if not re.search(r"phase:\s*parse", metadata):
            continue
        features, flags = array(metadata, "features"), array(metadata, "flags")
        if set(features) & excluded:
            omitted.update(sorted(set(features) & excluded))
            continue
        negative = re.search(r"^negative:\s*\n((?:[ \t]+[^\n]*\n?)+)", metadata, re.MULTILINE)
        if negative is None or re.search(r"type:\s*SyntaxError\b", negative.group(1)) is None:
            raise ValueError(f"Parse-negative case is not an expected SyntaxError: {path}")
        mode = "module" if "module" in flags else "strict" if "onlyStrict" in flags else "script"
        cases.append({"path": path.relative_to(checkout).as_posix(), "mode": mode,
            "flags": flags, "features": features, "sha256": sha256(source.encode("utf-8")).hexdigest(), "source": source})
    target = ROOT / "tests/fixtures/test262-early-errors"
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"cases": cases}, ensure_ascii=True, indent=2) + "\n"
    license_text = (checkout / "LICENSE").read_text(encoding="utf-8")
    (target / "cases.json").write_text(payload, encoding="utf-8", newline="\n")
    (target / "LICENSE").write_text(license_text, encoding="utf-8", newline="\n")
    manifest = {"test262Revision": REVISION, "target": "ECMAScript 2026", "count": len(cases),
        "scope": "All selected core-language parse-phase SyntaxError negatives; no runtime or resolution negatives.",
        "modePolicy": "module flag uses module; onlyStrict injects a directive; remaining cases preserve raw/non-strict source.",
        "sourceEncoding": "UTF-8 decoded, line endings normalized to LF before freezing and per-source checksums.",
        "excludedFeatures": sorted(excluded), "omitted": dict(omitted),
        "files": {"cases.json": sha256(payload.encode("utf-8")).hexdigest(), "LICENSE": sha256(license_text.encode("utf-8")).hexdigest()},
        "resourceLimits": "RecursionError and other resource failures never count as SyntaxError rejection."}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Frozen {len(cases)} parse-negative cases; {len(payload.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main()
