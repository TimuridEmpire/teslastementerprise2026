"""Generic reflection-based HTTP host for an Engineering build's generated
code. Run as its own subprocess (not imported into the router process) so a
crash, infinite loop, or unexpected exit in generated code can't take the
router down with it.

Usage: python3 generic_app_runner.py <workdir> <port>

<workdir> holds the extracted source files for one build. This script
imports each non-test .py file, finds the class that looks like "the app",
instantiates it, and exposes its public methods over HTTP so they can be
called from a form without any per-build custom wiring.

This deliberately runs generated code with the same permissions as the
process invoking it -- no sandboxing beyond binding to localhost only and
process isolation from the router. That tradeoff was an explicit choice
(Engineering's output is unreviewed LLM-generated code), not an oversight.
"""
from __future__ import annotations

import html
import importlib.util
import inspect
import json
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKIP_STEMS = {"plan"}


def _is_test_file(path: Path) -> bool:
    name = path.stem.lower()
    return name.startswith("test") or name in SKIP_STEMS


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"generated_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate_classes(workdir: Path):
    """Yield (file_stem, class) for top-level, non-test classes defined
    directly in each generated .py file (not imported from elsewhere)."""
    for path in sorted(workdir.glob("*.py")):
        if _is_test_file(path):
            continue
        try:
            module = _load_module(path)
        except Exception as exc:
            print(f"[runner] skipping {path.name}: failed to import ({exc})")
            continue
        if module is None:
            continue
        for name, obj in vars(module).items():
            if not inspect.isclass(obj) or obj.__module__ != module.__name__:
                continue
            if issubclass(obj, (unittest.TestCase, BaseException)):
                continue
            yield path.stem, obj


def _pick_app_class(workdir: Path):
    candidates = list(_candidate_classes(workdir))
    if not candidates:
        return None, None
    # Prefer a class whose name matches its file (weather_app.py -> WeatherApp).
    for stem, cls in candidates:
        if stem.replace("_", "") == cls.__name__.lower():
            return stem, cls
    return candidates[-1]


def _instantiate(cls):
    try:
        sig = inspect.signature(cls.__init__)
        required = [
            p for name, p in sig.parameters.items()
            if name != "self" and p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if required:
            names = ", ".join(p.name for p in required)
            return None, f"{cls.__name__}.__init__ requires arguments ({names}) that can't be auto-supplied."
        return cls(), None
    except Exception as exc:
        return None, f"Failed to instantiate {cls.__name__}: {exc}"


def _public_methods(instance):
    methods = []
    for name, member in inspect.getmembers(instance, predicate=inspect.ismethod):
        if name.startswith("_"):
            continue
        sig = inspect.signature(member)
        params = [p.name for p in sig.parameters.values() if p.name != "self"]
        methods.append((name, params))
    return methods


def _coerce(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 48px auto; background: #0b0d10; color: #e6e6e6; }}
  h1 {{ font-size: 18px; }}
  .sub {{ color: #888; font-size: 12px; margin-bottom: 24px; }}
  .method {{ padding: 14px; border-radius: 8px; background: #14161a; border: 1px solid #26282e; margin-bottom: 14px; }}
  .method h3 {{ margin: 0 0 8px; font-size: 13px; font-family: monospace; color: #67e8f9; }}
  input {{ padding: 6px 8px; font-size: 13px; border-radius: 6px; border: 1px solid #333; background: #16181c; color: #eee; margin: 0 6px 6px 0; width: 140px; }}
  button {{ padding: 6px 14px; font-size: 13px; border-radius: 6px; border: none; background: #34d399; color: #06120c; font-weight: 600; cursor: pointer; }}
  .result {{ margin-top: 10px; padding: 10px; border-radius: 6px; background: #0f1a14; border: 1px solid #245; font-family: monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
  .result.error {{ background: #1a0f0f; border-color: #522; color: #f87171; }}
  .error-banner {{ padding: 14px; border-radius: 8px; background: #1a0f0f; border: 1px solid #522; color: #f87171; font-family: monospace; font-size: 12px; }}
</style></head>
<body>
<h1>{title}</h1>
<div class="sub">Auto-hosted from generated source. Calls run the actual generated methods, unmodified.</div>
{body}
<script>
async function callMethod(name, paramNames) {{
  const args = paramNames.map(p => {{
    const el = document.getElementById('arg-' + name + '-' + p);
    return el.value;
  }});
  const res = await fetch('/call/' + encodeURIComponent(name), {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{args}}),
  }});
  const data = await res.json();
  const out = document.getElementById('result-' + name);
  out.textContent = data.error ? (data.error + ': ' + data.message) : JSON.stringify(data.result, null, 2);
  out.className = 'result' + (data.error ? ' error' : '');
  out.style.display = 'block';
}}
</script>
</body></html>"""


def build_page(app_class, instance, methods):
    if app_class is None:
        body = '<div class="error-banner">No suitable class found to host — no non-test .py file defines a class with public methods.</div>'
        return PAGE.format(title="No app found", body=body)
    if instance is None:
        body = f'<div class="error-banner">{html.escape(methods)}</div>'  # methods holds the error string in this branch
        return PAGE.format(title=html.escape(app_class.__name__), body=body)

    parts = []
    for name, params in methods:
        inputs = "".join(
            f'<input id="arg-{name}-{p}" placeholder="{html.escape(p)}">' for p in params
        )
        parts.append(f"""
        <div class="method">
          <h3>{html.escape(name)}({html.escape(", ".join(params))})</h3>
          {inputs}
          <button onclick="callMethod('{name}', {json.dumps(params)})">Call</button>
          <div id="result-{name}" class="result" style="display:none"></div>
        </div>""")
    return PAGE.format(title=html.escape(app_class.__name__), body="".join(parts))


class Handler(BaseHTTPRequestHandler):
    app_class = None
    instance = None
    init_error = None
    methods: list = []

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path not in ("/", ""):
            self.send_response(404)
            self.end_headers()
            return
        body = build_page(self.app_class, self.instance, self.methods if self.instance else self.init_error)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        if not self.path.startswith("/call/"):
            self.send_response(404)
            self.end_headers()
            return
        method_name = self.path[len("/call/"):]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}
        args = [_coerce(a) if isinstance(a, str) else a for a in payload.get("args", [])]

        result = {}
        if self.instance is None:
            result = {"error": "NotInstantiated", "message": self.init_error or "App was not instantiated."}
        else:
            method = getattr(self.instance, method_name, None)
            if method is None or method_name.startswith("_"):
                result = {"error": "NotFound", "message": f"No public method '{method_name}'."}
            else:
                try:
                    result = {"result": method(*args)}
                except Exception as exc:
                    result = {"error": type(exc).__name__, "message": str(exc)}

        body = json.dumps(result, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    workdir = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2])
    sys.path.insert(0, str(workdir))

    stem, app_class = _pick_app_class(workdir)
    instance, init_error, methods = None, None, []
    if app_class is not None:
        instance, init_error = _instantiate(app_class)
        if instance is not None:
            methods = _public_methods(instance)

    Handler.app_class = app_class
    Handler.instance = instance
    Handler.init_error = init_error
    Handler.methods = methods

    print(f"READY port={port} class={app_class.__name__ if app_class else None} "
          f"instantiated={instance is not None} error={init_error}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
