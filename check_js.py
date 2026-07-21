#!/usr/bin/env python3
"""Syntax-check every inline <script> served by templates.py.

Why this exists: the templates are Python strings containing JavaScript, so a
single-backslash escape like \\n inside a JS string literal is consumed by Python
and becomes a real newline — which breaks the JS string, kills the whole script,
and silently renders an empty screen. Python's own syntax check cannot catch that.

Run before every deploy:   python3 check_js.py
"""
import os, re, subprocess, sys, tempfile, types, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def load_templates():
    # templates.py imports flask.session at module level; stub it out.
    if "flask" not in sys.modules:
        fake = types.ModuleType("flask"); fake.session = {}
        sys.modules["flask"] = fake
    spec = importlib.util.spec_from_file_location("templates", os.path.join(HERE, "templates.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    if subprocess.run(["node", "--version"], capture_output=True).returncode != 0:
        print("node not available — skipping JS check"); return 0
    t = load_templates()
    names = [n for n in dir(t) if n.endswith("_HTML") and isinstance(getattr(t, n), str)]
    failures, checked = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            html = getattr(t, name)
            for idx, m in enumerate(re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S)):
                js = m.group(1)
                if not js.strip():
                    continue
                # Server-side placeholders aren't valid JS on their own.
                for ph in set(re.findall(r"__[A-Z_]+__", js)):
                    js = js.replace(ph, '"X"')
                path = os.path.join(tmp, f"{name}_{idx}.js")
                with open(path, "w") as f:
                    f.write(js)
                r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
                checked += 1
                if r.returncode != 0:
                    first = [l for l in r.stderr.splitlines() if "Error" in l or "^" in l]
                    failures.append((name, idx, "\n    ".join(first[:3])))
    if failures:
        print(f"\n{len(failures)} script block(s) FAILED:\n")
        for name, idx, err in failures:
            print(f"  ✗ {name} (block {idx})\n    {err}\n")
        return 1
    print(f"✅ {checked} inline script blocks across {len(names)} screens — all valid")
    return 0

if __name__ == "__main__":
    sys.exit(main())
