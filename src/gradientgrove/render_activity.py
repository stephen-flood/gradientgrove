#!/usr/bin/env python3

"""
Render a simple interactive activity site from GradientGrove Markdown.

Source convention:

    ordinary top-level Markdown
        -> landing page

    !!! activity "Activity title"
        -> activity

        !!! step "Step title"
            -> step within that activity

The current state is stored in the URL:

    ?activity=2&step=3

Navigation uses ordinary links. JavaScript only reads the URL and reveals
the selected activity and step.

python render_activity.py INPUT.md [OUTPUT.html]
"""

from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
from pathlib import Path

from mkdocs.utils.meta import get_data

# from gradientgrove.markdown_publish import build_tree
from gradientgrove import markdown_publish
import yaml
from urllib.parse import urlencode

import base64
import json

THEME_VARIABLES = {
    "background": "--gg-bg",
    "paper": "--gg-paper",
    "text": "--gg-text",
    "primary": "--gg-primary",
    "accent": "--gg-accent",
    "secondary": "--gg-secondary",
}

JUPYTERLITE_REPL = "https://gradientgrove.com/jupyterlite/repl/index.html"
# JUPYTERLITE_REPL = "https://jupyterlite.readthedocs.io/en/stable/_static/repl/index.html"


def theme_to_css(theme):
    """Convert activity_theme YAML settings to CSS variable overrides."""

    declarations = [
        f"{THEME_VARIABLES[name]}: {value};"
        for name, value in theme.items()
        if name in THEME_VARIABLES
    ]

    if not declarations:
        return ""

    return ":root { " + " ".join(declarations) + " }"

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>

<style>
{default_css}

{theme_css}

</style>
</head>

<body>

<nav class="top">
<a href="?">Home</a>
{topnav}
</nav>

<main>

<section id="landing" class="landing">
{landing}
</section>

{activities}

</main>

<script src="https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js"></script>

<script>
const activity = new URLSearchParams(location.search).get("activity");
const page = document.querySelector(`#activity-${{activity}}`);

// function showStep(n) {{
//     page.querySelectorAll(".exercise").forEach(step => step.hidden = true);
//     page.querySelector(`#activity-${{activity}}-step-${{n}}`).hidden = false;

//     const url = new URL(location);
//     url.searchParams.set("exercise", n);
//     history.replaceState(null, "", url);
// }}
function showStep(n) {{

    globalThis.cancelPythonInput?.();
    globalThis.cancelPythonInput = null;

    page.querySelectorAll(".exercise").forEach(step => step.hidden = true);

    const step = page.querySelector(
        `#activity-${{activity}}-step-${{n}}`
    );

    step.hidden = false;
    
    // Run python app if present
    step.querySelectorAll(".python-app").forEach(app => {{
        delete app.dataset.ran;
    }});
    setTimeout(runVisiblePythonApps, 0);

    const url = new URL(location);
    url.searchParams.set("exercise", n);
    history.replaceState(null, "", url);
}}

if (activity) {{
    document.querySelector("#landing").hidden = true;
    page.hidden = false;

    document
        .querySelector(`nav.top a[data-activity="${{activity}}"]`)
        ?.classList.add("active");

    if (page.querySelector(".exercise")) {{
        const step = Number(
            new URLSearchParams(location.search).get("exercise") || 1
        );

        showStep(step);
    }}
}}
document.querySelectorAll("blockquote, pre").forEach(element => {{
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";

    const text = element.textContent;

    button.addEventListener("click", async () => {{
        await navigator.clipboard.writeText(text);

        button.textContent = "Copied!";
        setTimeout(() => {{
            button.textContent = "Copy";
        }}, 1500);
    }});

    element.appendChild(button);
}});

// One interpreter shared by every Python app.
let pythonAppPyodide = null;
let pythonAppNamespace = null;
let pythonAppQueue = Promise.resolve();

let pythonAppOutput = null;

globalThis.pythonAppInput = prompt => new Promise((resolve, reject) =>  {{

    globalThis.cancelPythonInput = () =>
        reject(new Error("Input cancelled"));

    const row = document.createElement("div");
    const label = document.createElement("span");
    const input = document.createElement("input");

    label.textContent = prompt;
    input.type = "text";

    row.append(label, input);
    pythonAppOutput.append(row);

    input.addEventListener("keydown", event => {{
        if (event.key !== "Enter") return;

        event.preventDefault();
        input.disabled = true;
        
        globalThis.cancelPythonInput = null;

        resolve(input.value);
    }});

    input.focus();
}});

function runVisiblePythonApps() {{
    for (const app of document.querySelectorAll(".python-app:not(.python-edit)")) {{
        if (app.dataset.ran || !app.getClientRects().length) continue;

        app.dataset.ran = "true";
        pythonAppQueue = pythonAppQueue.then(() => runPythonApp(app));
    }}
}}

async function runPythonApp(app) {{
    const output = app.querySelector(".python-app-output");
    
    pythonAppOutput = output;

    const source = app.querySelector(".python-app-source").value;

    const write = text =>
        output.append(document.createTextNode(text + "\\n"));

    output.replaceChildren();

    try {{
        pythonAppPyodide ??= loadPyodide();
        const pyodide = await pythonAppPyodide;

        pyodide.setStdout({{ batched: write }});
        pyodide.setStderr({{ batched: write }});
        //pyodide.setStdin({{
        //    stdin: () => window.prompt("Python input:") ?? ""
        //}});

        // Make Python input() wait for our inline field.
        await pyodide.runPythonAsync(`
        import builtins
        from js import pythonAppInput
        from pyodide.ffi import run_sync

        def _inline_input(prompt=""):
            return run_sync(pythonAppInput(prompt))

        builtins.input = _inline_input
        `);

        // Reset variables unless {{persist}} is specified.
        if (!pythonAppNamespace || app.dataset.persist !== "true") {{
            pythonAppNamespace?.destroy();
            pythonAppNamespace = pyodide.runPython("dict()");
        }}

        await pyodide.runPythonAsync(source, {{
            globals: pythonAppNamespace
        }});
    }} catch (error) {{
        write(String(error));
    }}
}}

// Autorun apps on the landing page or selected activity.
setTimeout(runVisiblePythonApps, 0);

// Also run apps revealed inside expandable details.
document.addEventListener("toggle", () => {{
    setTimeout(runVisiblePythonApps, 0);
}}, true);


document.addEventListener("click", event => {{
    const app = event.target.closest(".python-run")?.closest(".python-edit");
    if (!app) return;

    pythonAppQueue = pythonAppQueue.then(() => runPythonApp(app));
}});


// LLM chat
document.querySelectorAll(".llm-chat").forEach(root => {{
    const cfg = JSON.parse(root.querySelector(".llm-config").value);
    const log = root.querySelector(".llm-messages");
    const prompt = root.querySelector(".llm-prompt");
    const model = root.querySelector(".llm-model");
    const send = root.querySelector(".llm-send");
    const clear = root.querySelector(".llm-clear");
    let history = [];

    function reset() {{
        history = [];
        log.replaceChildren();
        prompt.value = "";
    }}

    clear.onclick = reset;
    model.onchange = reset;

    send.onclick = async () => {{
        const text = prompt.value.trim();
        if (!text) return;

        const spec = cfg.models[model.value];
        const api = spec.api || cfg.api || "chat";
        const messages = [...history, {{role: "user", content: text}}];

        if (cfg.system)
            messages.unshift({{role: "system", content: cfg.system}});

        const payload = {{
            model: model.value,
            ...cfg.parameters,
            ...spec.parameters
        }};

        root.querySelectorAll(".llm-control").forEach(control => {{
            payload[control.dataset.param] = Number(control.value);
        }});

        if (api === "chat") {{
            payload.messages = messages;
        }} else {{
            payload.prompt = messages
                .map(m => `${{m.role}}: ${{m.content}}`)
                .join("\\n") + "\\nassistant:";
        }}

        const userKey = root.querySelector(".llm-key")?.value.trim();
        const encodedKey = spec.api_key || cfg.api_key;
        const key = userKey || (encodedKey ? atob(encodedKey) : "");

        const headers = {{"Content-Type": "application/json"}};
        if (key) headers.Authorization = `Bearer ${{key}}`;

        prompt.value = "";
        send.disabled = true;
        log.insertAdjacentText("beforeend", `You: ${{text}}\n\n`);

        try {{
            const response = await fetch(spec.endpoint, {{
                method: "POST",
                headers,
                body: JSON.stringify(payload)
            }});

            if (!response.ok)
                throw new Error(`${{response.status}} ${{response.statusText}}`);

            const choice = (await response.json()).choices[0];
            const answer = api === "chat"
                ? choice.message.content
                : choice.text;

            history.push(
                {{role: "user", content: text}},
                {{role: "assistant", content: answer}}
            );

            log.insertAdjacentText("beforeend", `Model: ${{answer}}\n\n`);
        }} catch (error) {{
            log.insertAdjacentText("beforeend", `Error: ${{error.message}}\n\n`);
        }} finally {{
            send.disabled = false;
            log.scrollTop = log.scrollHeight;
        }}
    }};
}});
</script>

</body>
</html>
"""


def iframe_fence(source, language, css_class, options, md, **kwargs):
    config = yaml.safe_load(source) or {}

    url = config["url"]
    title = config.get("title", "Embedded content")

    width = config.get("width", "100%")
    height = config.get("height", "100%")
    # width = config.get("width", "117.65%")
    # height = config.get("height", "1030px")

    def encode(values):
        return urlencode({
            key: str(value).lower() if isinstance(value, bool) else value
            for key, value in values.items()
        })

    if config.get("query"):
        url += "?" + encode(config["query"])

    if config.get("hash"):
        url += "#" + encode(config["hash"])

    # return (
    #     '<p>'
    #     f'<iframe src="{html.escape(url, quote=True)}" '
    #     f'title="{html.escape(title, quote=True)}" '
    #     f'style="width: {html.escape(str(width))} !important; '
    #     f'height: {html.escape(str(height))};"></iframe>'
    #     '</p>'
    # )

    # Pass optional class for formatting output
    iframe_class = config.get("class")
    class_attr = (
        f' class="{html.escape(iframe_class, quote=True)}"'
        if iframe_class else ""
    )

    return (
        '<p>'
        f'<iframe{class_attr} src="{html.escape(url, quote=True)}" '
        f'title="{html.escape(title, quote=True)}" '
        f'style="width: {html.escape(str(width))} !important; '
        f'height: {html.escape(str(height))};"></iframe>'
        '</p>'
    )

# def interactive_python_fence(source, language, css_class, options, md, **kwargs):
#     """Render a Python code block using the JupyterLite single-cell REPL."""

#     config = {
#         "title": "Interactive Python",
#         "url": JUPYTERLITE_REPL,
#         "width": "100%",
#         "height": "500px",
#         "query": {
#             "kernel": "python",
#             "toolbar": 1,
#             "promptCellPosition": "top",
#             "clearCellsOnExecute": 1,
#             "hideCodeInput": 1,
#             "clearCodeContentOnExecute": 0,
#             "showBanner": 0,
#             "execute": 0,
#             "code": source.strip(),
#         },
#     }

#     # Reuse the normal iframe renderer rather than maintaining
#     # a second implementation of iframe URL construction.
#     return iframe_fence(
#         yaml.safe_dump(config, sort_keys=False),
#         language,
#         css_class,
#         options,
#         md,
#         **kwargs,
#     )


# def python_app_fence(source, language, css_class, options, md, **kwargs):
#     persist = "persist" in kwargs.get("attrs", {})

#     return (
#         f'<div class="python-app-slot" '
#         f'data-persist="{str(persist).lower()}">'
#         f'<textarea class="python-app-source" hidden="hidden">'
#         f'{html.escape(source)}'
#         f'</textarea>'
#         f'</div>'
#     )
def python_app_fence(source, language, css_class, options, md, **kwargs):
    persist = "persist" in kwargs.get("attrs", {})

    return (
        f'<div class="python-app" data-persist="{str(persist).lower()}">'
        '<textarea class="python-app-source" hidden="hidden">'
        f'{html.escape(source)}'
        '</textarea>'
        '<div class="python-app-output python-output"></div>'
        '</div>'
        '<p class="tool-credit">Powered by '
        '<a href="https://pyodide.org/">Pyodide</a>.</p>'
    )

def interactive_python_fence(source, language, css_class, options, md, **kwargs):
    attrs = kwargs.get("attrs", {})
    run = "run" in attrs

    # config = {
    #     "title": "Interactive Python",
    #     "url": JUPYTERLITE_REPL,
    #     "height": "500px",
    #     "query": {
    #         "kernel": "python",
    #         "showBanner": 0,
    #         "code": source.strip(),
    #     },
    config = {
        "title": "Interactive Python",
        "url": JUPYTERLITE_REPL,
        "height": "600px",
        # "height" : "100%",
        "query": {
            "kernel": "python",
            "toolbar": 1,
            "showBanner": 1,
            "hideCodeInput": 1,
            "clearCellsOnExecute": 0,
            "clearCodeContentOnExecute": 0,
            "promptCellPosition": "top",
            "code": source.strip(),
        },
    }

    if not run:
        config["query"]["execute"] = 0

    # return iframe_fence(
    #     yaml.safe_dump(config, sort_keys=False),
    #     language,
    #     css_class,
    #     options,
    #     md,
    #     **kwargs,
    # )

    return iframe_fence(
        yaml.safe_dump(config, sort_keys=False),
        language, css_class, options, md, **kwargs,
    ) + (
        '<p class="tool-credit">Powered by '
        '<a href="https://jupyterlite.readthedocs.io/">'
        'JupyterLite</a>.</p>'
    )

def python_edit_fence(source, language, css_class, options, md, **kwargs):
    return (
        '<div class="python-app python-edit" data-persist="false">'
        '<textarea class="python-app-source python-source">'
        f'{html.escape(source)}</textarea>'
        '<button type="button" class="python-run">Run</button>'
        '<div class="python-app-output python-output"></div>'
        '</div>'
        '<p class="tool-credit">Powered by '
        '<a href="https://pyodide.org/">Pyodide</a>.</p>'
    )


def python_trace_fence(source, language, css_class, options, md, **kwargs):
    params = urlencode({
        "code": source.strip(),
        "mode": "display",
        "py": "311",
    })

    url = "https://pythontutor.com/iframe-embed.html#" + params

    return (
        '<div class="python-trace">'
        f'<iframe src="{html.escape(url, quote=True)}" '
        'title="Python Tutor Code Trace" '
        'loading="lazy" '
        'style="display:block; width:100% !important; '
        'height:550px !important; transform:none !important; '
        'border:0"></iframe>'
        '<p class="tool-credit">'
        'Visualization powered by '
        '<a href="https://pythontutor.com/">Python Tutor</a> '
        '(Philip Guo).'
        '</p>'
        '</div>'
    )
# def llm_chat_fence(source, language, css_class, options, md, **kwargs):
#     from uuid import uuid4

#     cfg = yaml.safe_load(source)
#     models = [dict(name=m) if isinstance(m, str) else m for m in cfg["models"]]
#     cfg["models"] = {m["name"]: m for m in models}

#     key_html = (
#         '<label>API key: <input type="password" class="llm-key" '
#         'placeholder="Optional: use your own key" autocomplete="off"></label>'
#         if cfg.get("key_field") else ""
#     )

#     cid = "chat-" + uuid4().hex

#     code = f"CID={cid!r}\nCFG={cfg!r}\n" + r"""
# import json, builtins
# from js import document
# from pyodide.http import pyfetch
# from pyodide.ffi import create_proxy

# def setup():
#     root = document.getElementById(CID)
#     if root.hasAttribute("data-ready"):
#         return

#     log = root.querySelector(".llm-messages")
#     prompt = root.querySelector(".llm-prompt")
#     model = root.querySelector(".llm-model")
#     send_btn = root.querySelector(".llm-send")
#     clear_btn = root.querySelector(".llm-clear")
#     history = []
#     cfg = CFG

#     def clear(event=None):
#         history.clear()
#         log.replaceChildren()
#         prompt.value = ""

#     async def send(event):
#         text = prompt.value.strip()
#         if not text or send_btn.disabled:
#             return

#         for el in (send_btn, clear_btn, model):
#             el.disabled = True
#         prompt.value = ""
#         log.insertAdjacentText("beforeend", f"You: {text}\n\n")

#         try:
#             spec = cfg["models"][model.value]
#             api = spec.get("api", cfg.get("api", "chat"))
#             url = (spec.get("endpoint") or cfg["endpoint"]).rstrip("/")
#             for suffix in ("/chat/completions", "/completions"):
#                 if url.endswith(suffix):
#                     url = url[:-len(suffix)]
#                     break
#             url += {"chat": "/chat/completions",
#                     "completion": "/completions"}[api]

#             messages = history + [{"role": "user", "content": text}]
#             if cfg.get("system"):
#                 messages.insert(0, {"role": "system", "content": cfg["system"]})

#             payload = {"model": model.value, **cfg.get("parameters", {}),
#                        **spec.get("parameters", {})}
#             for el in root.querySelectorAll(".llm-control"):
#                 payload[el.getAttribute("data-param")] = json.loads(el.value)

#             if api == "chat":
#                 payload["messages"] = messages
#             else:
#                 payload["prompt"] = "\n".join(
#                     f"{m['role'].capitalize()}: {m['content']}"
#                     for m in messages
#                 ) + "\nAssistant:"

#             # r = await pyfetch(url, method="POST",
#             #     headers={"Content-Type": "application/json"},
#             #     body=json.dumps(payload))
#             key_input = root.querySelector(".llm-key")
#             key = (key_input.value.strip() if key_input else "") or \
#                 spec.get("api_key", cfg.get("api_key", ""))

#             headers = {"Content-Type": "application/json"}
#             if key:
#                 headers["Authorization"] = f"Bearer {key}"

#             r = await pyfetch(
#                 url, method="POST",
#                 headers=headers,
#                 body=json.dumps(payload)
#             )

#             r.raise_for_status()
#             choice = (await r.json())["choices"][0]
#             answer = choice["message"]["content"] if api == "chat" else choice["text"]

#             history.extend([{"role": "user", "content": text},
#                             {"role": "assistant", "content": answer}])
#             log.insertAdjacentText("beforeend", f"Model: {answer}\n\n")
#         except Exception as e:
#             log.insertAdjacentText("beforeend", f"Error: {e}\n\n")
#         finally:
#             for el in (send_btn, clear_btn, model):
#                 el.disabled = False
#             log.scrollTop = log.scrollHeight

#     callbacks = [create_proxy(send), create_proxy(clear)]
#     for el, event, callback in (
#         (send_btn, "click", callbacks[0]),
#         (clear_btn, "click", callbacks[1]),
#         (model, "change", callbacks[1])
#     ):
#         el.addEventListener(event, callback)

#     builtins._gg_chat_handlers = getattr(builtins, "_gg_chat_handlers", []) + callbacks
#     root.setAttribute("data-ready", "true")

# setup()
# """

#     options_html = "".join(
#         f'<option>{html.escape(str(m["name"]))}</option>' for m in models
#     )
#     controls_html = "".join(
#         f'<label>{html.escape(k)} <input type="number" class="llm-control" '
#         f'data-param="{html.escape(k, quote=True)}" '
#         f'min="{v["min"]}" max="{v["max"]}" step="{v.get("step", 1)}" '
#         f'value="{cfg.get("parameters", {}).get(k, v["min"])}"></label>'
#         for k, v in cfg.get("controls", {}).items()
#     )

#     return (
#         f'<div class="python-app llm-chat" id="{cid}">'
#         f'<textarea class="python-app-source" hidden="hidden">'
#         f'{html.escape(code)}</textarea>'
#         f'<label>Model: <select class="llm-model">{options_html}</select></label>'
#         f'{key_html}'
#         f'<div class="llm-controls">{controls_html}</div>'
#         '<div class="llm-messages" aria-live="polite"></div>'
#         '<textarea class="llm-prompt" rows="3" placeholder="Your message"></textarea>'
#         '<div class="llm-actions">'
#         '<button type="button" class="llm-send">Send</button>'
#         '<button type="button" class="llm-clear">Clear</button>'
#         '</div><div class="python-app-output"></div></div>'
#     )

def llm_chat_fence(source, language, css_class, options, md, **kwargs):
    cfg = yaml.safe_load(source) or {}
    models = cfg.get("models", [])

    if not models:
        raise ValueError("llm-chat requires at least one model")

    for model in models:
        if not isinstance(model, dict):
            raise ValueError("Each llm-chat model must be a mapping")
        if "name" not in model:
            raise ValueError("Each llm-chat model requires a name")
        if "endpoint" not in model:
            raise ValueError(
                f'llm-chat model "{model["name"]}" requires an endpoint'
            )

        api = model.get("api", cfg.get("api", "chat"))
        if api not in ("chat", "completion"):
            raise ValueError(
                f'llm-chat model "{model["name"]}" has invalid api "{api}".  Must be "chat" or "completion"'
            )

    # Obfuscate embedded API keys. They are still recoverable in the browser.
    embedded_key = False

    if cfg.get("api_key"):
        cfg["api_key"] = base64.b64encode(
            cfg["api_key"].encode()
        ).decode()
        embedded_key = True

    for model in models:
        if model.get("api_key"):
            model["api_key"] = base64.b64encode(
                model["api_key"].encode()
            ).decode()
            embedded_key = True

    if embedded_key:
        print(
            "WARNING: llm-chat embeds an API key in client-side HTML.\n"
            "         It is obfuscated but NOT secret.\n"
            "         Only use restricted, rate-limited, internal credentials.\n\n"
            "         Do **NOT** use for any credential that could cost you money!!!.\n"
        )

    cfg["models"] = {model["name"]: model for model in models}

    options_html = "".join(
        f'<option value="{html.escape(str(model["name"]), quote=True)}">'
        f'{html.escape(str(model["name"]))}</option>'
        for model in models
    )

    controls_html = "".join(
        f'<label>{html.escape(name)} '
        f'<input type="number" class="llm-control" '
        f'data-param="{html.escape(name, quote=True)}" '
        f'min="{control["min"]}" max="{control["max"]}" '
        f'step="{control.get("step", 1)}" '
        f'value="{cfg.get("parameters", {}).get(name, control["min"])}">'
        f'</label>'
        for name, control in cfg.get("controls", {}).items()
    )

    key_html = (
        '<label>API key: '
        '<input type="password" class="llm-key" '
        'placeholder="Optional: use your own key" autocomplete="off">'
        '</label>'
        if cfg.get("key_field") else ""
    )

    return (
        '<div class="llm-chat">'
        f'<textarea class="llm-config" hidden="hidden">'
        f'{html.escape(json.dumps(cfg))}</textarea>'
        f'<label>Model: <select class="llm-model">{options_html}</select></label>'
        f'{key_html}'
        f'<div class="llm-controls">{controls_html}</div>'
        '<div class="llm-messages" aria-live="polite"></div>'
        '<textarea class="llm-prompt" rows="3" '
        'placeholder="Your message"></textarea>'
        '<div class="llm-actions">'
        '<button type="button" class="llm-send">Send</button>'
        '<button type="button" class="llm-clear">Clear</button>'
        '</div>'
        '</div>'
    )

def render(source, title, theme=None, exercise_position="bottom"):
    """Build the GradientGrove AST and render the activity HTML page."""

    # HACK: Add an activity-specific custom fence to the same SuperFences
    # configuration that markdown_publish.build_tree() uses internally.
    # `fences` is a reference to that existing list, so appending here
    # mutates the shared configuration seen later by build_tree().
    # This keeps the change local to render_activity.py, but is intentionally
    # relying on shared mutable configuration rather than an explicit API.
    fences = (
        markdown_publish.HTML_EXTENSION_CONFIGS
        ["pymdownx.superfences"]
        ["custom_fences"]
    )
    if not any(fence["name"] == "iframe" for fence in fences):
        fences.append({
            "name": "iframe",
            "class": "iframe",
            "format": iframe_fence,
        })
    if not any(fence["name"] == "python-interactive" for fence in fences):
        fences.append({
            "name": "python-interactive",
            "class": "python-interactive",
            "format": interactive_python_fence,
        })
    if not any(fence["name"] == "python-app" for fence in fences):
        fences.append({
            "name": "python-app",
            "class": "python-app",
            "format": python_app_fence,
        })
    if not any(f["name"] == "python-edit" for f in fences):
        fences.append({
            "name": "python-edit",
            "class": "python-edit",
            "format": python_edit_fence,
        })
    if not any(f["name"] == "python-trace" for f in fences):
        fences.append({
            "name": "python-trace",
            "class": "python-trace",
            "format": python_trace_fence,
        })
    if not any(f["name"] == "llm-chat" for f in fences):
        fences.append({
            "name": "llm-chat",
            "class": "llm-chat",
            "format": llm_chat_fence,
        })        

    tree = markdown_publish.build_tree(
        source,
        number=False,
        render_latex_fences=True,
    )

    # Top-level activity admonitions become activities.
    activities = [
        node
        for node in tree.children
        if node.name == "activity"
    ]

    if not activities:
        raise ValueError("No top-level !!! activity environments found.")

    # Everything else at the top level becomes the landing-page introduction.
    landing = "".join(
        ET.tostring(
            node.to_etree(),
            encoding="unicode",
            method="html",
        )
        for node in tree.children
        if node.name != "activity"
    )
    # Add navigation to landing page
    landing += (
        '<a class="activity-arrow activity-arrow-right" '
        'href="?activity=1&exercise=1" '
        'aria-label="Next activity"></a>'
    )

    topnav = []
    activity_list = []
    activity_html = []

    for i, activity in enumerate(activities, start=1):
        activity_title = activity.title or f"Activity {i}"

        # Activity links appear both in the top navigation and landing page.
        # link = (
        #     f'<a href="?activity={i}&step=1">'
        #     f'{html.escape(activity_title)}</a>'
        # )

        # Don't provide navigation for missing titles
        if activity.title != "Activity":
            link = (
                f'<a href="?activity={i}&exercise=1" data-activity="{i}">'
                f'{html.escape(activity_title)}</a>'
            )
        else:
            print("Warning: No title for activity, not added to navigation.")
            link = ""

        # prev_activity = (
        #     f'<a class="activity-arrow activity-arrow-left" '
        #     f'href="?activity={i - 1}&exercise=1" '
        #     f'aria-label="Previous activity">←</a>'
        #     if i > 1 else ""
        # )

        # next_activity = (
        #     f'<a class="activity-arrow activity-arrow-right" '
        #     f'href="?activity={i + 1}&exercise=1" '
        #     f'aria-label="Next activity">→</a>'
        #     if i < len(activities) else ""
        # )

        # prev_activity = (
        #     f'<a class="activity-arrow activity-arrow-left" '
        #     f'href="?activity={i - 1}&exercise=1" '
        #     f'aria-label="Previous activity"></a>'
        #     if i > 1 else ""
        # )

        # next_activity = (
        #     f'<a class="activity-arrow activity-arrow-right" '
        #     f'href="?activity={i + 1}&exercise=1" '
        #     f'aria-label="Next activity"></a>'
        #     if i < len(activities) else ""
        # )
        prev_activity = (
            f'<a class="activity-arrow activity-arrow-left" '
            f'href="{"?" if i == 1 else f"?activity={i - 1}&exercise=1"}" '
            f'aria-label="Previous activity"></a>'
        )

        next_activity = (
            f'<a class="activity-arrow activity-arrow-right" '
            f'href="{"?" if i == len(activities) else f"?activity={i + 1}&exercise=1"}" '
            f'aria-label="Next activity"></a>'
        )

        topnav.append(link)
        activity_list.append(link)

        # Only direct-child step admonitions participate in step navigation.
        steps = [
            child
            for child in activity.children
            if child.name == "exercise"
        ]

        if not steps:
            # raise ValueError(
            #     f"{activity_title!r} has no !!! step environments."
            # )
            print(f"Warning: {activity_title!r} has no exercise/step environments.")

        steps_html = []

        for j, step in enumerate(steps, start=1):
            # step_title = step.title or f"Step {j}"
            step_title_html = ET.tostring(
                list(step.etree)[0],
                encoding="unicode",
                method="html",
            )
            
            # prev_button = (
            #     f'<button onclick="showStep({j - 1})">Back</button>'
            #     if j > 1 else ""
            # )

            if j > 1:
                prev_button = (
                    f'<button onclick="showStep({j - 1})">Back</button>'
                )
            elif i > 1:
                previous_steps = [
                    child
                    for child in activities[i - 2].children
                    if child.name == "exercise"
                ]

                prev_button = (
                    f'<a class="previous-activity-button" '
                    f'href="?activity={i - 1}&exercise={len(previous_steps)}">'
                    f'Previous Activity</a>'
                )
            else:
                prev_button = ""

            # next_button = (
            #     f'<button onclick="showStep({j + 1})">Next →</button>'
            #     if j < len(steps) else ""
            # )
            next_button = (
                f'<button onclick="showStep({j + 1})">Next</button>'
                if j < len(steps)
                else (
                    f'<a class="next-activity-button" '
                    f'href="?activity={i + 1}&exercise=1">'
                    f'Next activity</a>'
                    if i < len(activities)
                    else ""
                )
            )

            # Render the contents of the step using GradientGrove's normal
            # HTML conversion. Nested hints/details need no special handling.
            step_body = "".join(
                ET.tostring(
                    child.to_etree(),
                    encoding="unicode",
                    method="html",
                )
                for child in step.children
            )

            # steps_html.append(
            #     f'<section class="exercise" id="activity-{i}-step-{j}" hidden>'
            #     f'<h2>{html.escape(step_title)}</h2>'
            #     f'{step_body}'
            #     f'<div class="step-nav">'
            #     f'{prev_link}'
            #     f'<span>Step {j} of {len(steps)}</span>'
            #     f'{next_link}'
            #     f'</div>'
            #     f'</section>'
            # )
            
            # steps_html.append(
            #     f'<section class="exercise" id="activity-{i}-step-{j}" hidden>'
            #     f'<h2>{html.escape(step_title)}</h2>'
            #     f'{step_body}'
            #     f'<div class="exercise-nav">'
            #     f'{prev_button}'
            #     f'<span>Step {j} of {len(steps)}</span>'
            #     f'{next_button}'
            #     f'</div>'
            #     f'</section>'
            # )

            steps_html.append(
                f'<section class="exercise" id="activity-{i}-step-{j}" hidden>'
                # f'<h1 class="activity-title">{html.escape(activity_title)}</h1>'
                # f'<h2 class="exercise-title">{html.escape(step_title)}</h2>'
                f'{step_title_html}'
                f'{step_body}'
                f'<div class="exercise-nav">'
                f'{prev_button}'
                f'<span>Step {j} of {len(steps)}</span>'
                f'{next_button}'
                f'</div>'
                f'</section>'
            )
            
        # Non-step content stays visible throughout the activity.
        activity_body = "".join(
            ET.tostring(
                child.to_etree(),
                encoding="unicode",
                method="html",
            )
            for child in activity.children
            if child.name != "exercise"
        )

        # activity_html.append(
        #     f'<section class="activity" id="activity-{i}" hidden>'
        #     f'<h1>{html.escape(activity_title)}</h1>'
        #     f'{activity_body}'
        #     f'{"".join(steps_html)}'
        #     f'</section>'
        # )

        # activity_html.append(
        #     f'<section class="activity" id="activity-{i}" hidden>'
        #     f'{prev_activity}'
        #     f'{next_activity}'
        #     f'<h1>{html.escape(activity_title)}</h1>'
        #     f'{activity_body}'
        #     f'{"".join(steps_html)}'
        #     f'</section>'
        # )

        # exercise_body = "".join(steps_html)

        # if exercise_position == "top":
        #     content = exercise_body + activity_body
        # else:
        #     content = activity_body + exercise_body

        # activity_html.append(
        #     f'<section class="activity" id="activity-{i}" hidden>'
        #     f'{prev_activity}'
        #     f'{next_activity}'
        #     f'<h1>{html.escape(activity_title)}</h1>'
        #     f'{content}'
        #     f'</section>'
        # )

        # exercise_body = "".join(steps_html)

        # activity_content = (
        #     f'<div class="activity-content">'
        #     f'{activity_body}'
        #     f'</div>'
        # )

        # if exercise_position == "top":
        #     stack = exercise_body + activity_content
        # else:
        #     stack = activity_content + exercise_body

        # activity_html.append(
        #     f'<section class="activity" id="activity-{i}" hidden>'
        #     f'{prev_activity}'
        #     f'{next_activity}'
        #     # f'<h1>{html.escape(activity_title)}</h1>'
        #     f'<div class="activity-stack">'
        #     f'{stack}'
        #     f'</div>'
        #     f'</section>'
        # )            

        exercise_body = "".join(steps_html)

        activity_content = (
            f'<div class="activity-content">'
            f'{activity_body}'
            f'</div>'
        )

        if steps:
            exercise_group = (
                f'<div class="exercise-group">'
                f'{exercise_body}'
                f'</div>'
            )

            if exercise_position == "top":
                stack = exercise_group + activity_content
            else:
                stack = activity_content + exercise_group

        else:
            stack = activity_content

        activity_html.append(
            f'<section class="activity" id="activity-{i}" hidden>'
            f'{prev_activity}'
            f'{next_activity}'
            f'<div class="activity-stack">'
            f'<h1 class="activity-title">{html.escape(activity_title)}</h1>'
            f'{stack}'
            f'</div>'
            f'</section>'
        )

    activity_list_html = (
        '<h2>Activities</h2>'
        '<div class="activity-list">'
        + "\n".join(activity_list)
        + '</div>'
    )

    # Allow user to manually place list of activities
    if "<p>[ACTIVITIES]</p>" in landing:
        landing = landing.replace(
            "<p>[ACTIVITIES]</p>",
            activity_list_html,
        )
    else:
        landing += activity_list_html

    css_path = Path(__file__).resolve().parent / "activity.css"
    default_css = css_path.read_text(encoding="utf-8")  

    # return HTML_TEMPLATE.format(
    #     title=html.escape(title),
    #     landing=landing,
    #     topnav="\n".join(topnav),
    #     activity_list="\n".join(activity_list),
    #     activities="\n".join(activity_html),
    # )

    return HTML_TEMPLATE.format(
        title=html.escape(title),
        default_css=default_css,
        theme_css=theme_to_css(theme or {}),
        landing=landing,
        topnav="\n".join(topnav),
        activity_list="\n".join(activity_list),
        activities="\n".join(activity_html),
    )


def main():
    """
    Parse command-line arguments and render one Markdown file.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    source, metadata = get_data(source)

    title = metadata.get(
        "title",
        args.input.stem.replace("-", " ").title(),
    )

    output = args.output or args.input.with_suffix(".html")

    theme = metadata.get("activity_theme", {})
    exercise_position = metadata.get("exercise_position", "bottom").lower()

    if exercise_position not in {"top", "bottom"}:
        exercise_position = "bottom"

    output.write_text(
        render(source, title, theme, exercise_position),
        encoding="utf-8",
    )

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()