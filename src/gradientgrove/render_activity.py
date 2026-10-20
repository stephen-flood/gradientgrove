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
    setTimeout(() => runVisiblePythonApps(), 0);

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
if ("{arrow_navigation}" === "exercises" && page) {{
    page.querySelectorAll(".activity-arrow").forEach(arrow => {{
        arrow.addEventListener("click", event => {{
            const delta = arrow.classList.contains("activity-arrow-right") ? 1 : -1;
            const current = Number(new URLSearchParams(location.search).get("exercise") || 1);
            const next = current + delta;
            const count = page.querySelectorAll(".exercise").length;

            if (next >= 1 && next <= count) {{
                event.preventDefault();
                showStep(next);
            }} else if (delta < 0 && Number(activity) > 1) {{
                event.preventDefault();
                const previous = Number(activity) - 1;
                const last = document.querySelector(`#activity-${{previous}}`)
                    .querySelectorAll(".exercise").length || 1;
                location.href = `?activity=${{previous}}&exercise=${{last}}`;
            }}
        }});
    }});
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
</script>

<script>
{pyodide_js}
</script>

<script>
{llm_local_js}
</script>

<script>
{llm_chat_js}
</script>

</body>
</html>
"""




PYODIDE_JS = r"""
function getPyodide() {
    pythonAppPyodide ??= (async () => {
        const base = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
        if (!globalThis.loadPyodide) {
            await new Promise((resolve, reject) => {
                const script = document.createElement("script");
                script.src = base + "pyodide.js";
                script.onload = resolve;
                script.onerror = () => {
                    script.remove();
                    reject(new Error("Could not load Pyodide. Please try again."));
                };
                document.head.append(script);
            });
        }
        return globalThis.loadPyodide({indexURL: base});
    })().catch(error => {
        pythonAppPyodide = null;
        throw error;
    });
    return pythonAppPyodide;
}

// One interpreter shared by every Python app.
let pythonAppPyodide = null;
let pythonAppNamespace = null;
let pythonAppQueue = Promise.resolve();

let pythonAppOutput = null;

globalThis.pythonAppInput = prompt => new Promise((resolve, reject) =>  {

    globalThis.cancelPythonInput = () =>
        reject(new Error("Input cancelled"));

    const row = document.createElement("div");
    const label = document.createElement("span");
    const input = document.createElement("input");

    label.textContent = prompt;
    input.type = "text";

    row.append(label, input);
    pythonAppOutput.append(row);

    input.addEventListener("keydown", event => {
        if (event.key !== "Enter") return;

        event.preventDefault();
        input.disabled = true;
        
        globalThis.cancelPythonInput = null;

        resolve(input.value);
    });

    input.focus();
});

function runVisiblePythonApps() {
    for (const app of document.querySelectorAll(".python-app:not(.python-edit)")) {
        if (app.dataset.ran || !app.getClientRects().length) continue;

        app.dataset.ran = "true";
        pythonAppQueue = pythonAppQueue.then(() => runPythonApp(app));
    }
}

async function runPythonApp(app) {
    const output = app.querySelector(".python-app-output");
    
    pythonAppOutput = output;

    const source = app.querySelector(".python-app-source").value;

    const write = text =>
        output.append(document.createTextNode(text + "\n"));

    output.replaceChildren();

    try {
        const pyodide = await getPyodide();

        pyodide.setStdout({ batched: write });
        pyodide.setStderr({ batched: write });

        // Make Python input() wait for our inline field.
        await pyodide.runPythonAsync(`
        import builtins
        from js import pythonAppInput
        from pyodide.ffi import run_sync

        def _inline_input(prompt=""):
            return run_sync(pythonAppInput(prompt))

        builtins.input = _inline_input
        `);

        // Reset variables unless {persist} is specified.
        if (!pythonAppNamespace || app.dataset.persist !== "true") {
            pythonAppNamespace?.destroy();
            pythonAppNamespace = pyodide.runPython("dict()");
        }

        await pyodide.runPythonAsync(source, {
            globals: pythonAppNamespace
        });
    } catch (error) {
        write(String(error));
    }
}

// Autorun apps on the landing page or selected activity.
setTimeout(runVisiblePythonApps, 0);

// Also run apps revealed inside expandable details.
document.addEventListener("toggle", () => {
    setTimeout(runVisiblePythonApps, 0);
}, true);


document.addEventListener("click", event => {
    const app = event.target.closest(".python-run")?.closest(".python-edit");
    if (!app) return;

    pythonAppQueue = pythonAppQueue.then(() => runPythonApp(app));
});
"""

LLM_CHAT_JS = r"""
// LLM chat (chat + completion, with optional tool calls)
document.querySelectorAll(".llm-chat").forEach(root => {
    const cfg = JSON.parse(root.querySelector(".llm-config").value);
    const log = root.querySelector(".llm-messages");
    const prompt = root.querySelector(".llm-prompt");
    const model = root.querySelector(".llm-model");
    const send = root.querySelector(".llm-send");
    const clear = root.querySelector(".llm-clear");
    const tools = Array.isArray(cfg.tools) ? cfg.tools : [];

    const sourceLink = document.createElement("a");
    sourceLink.textContent = "Model card";
    sourceLink.className = "llm-model-source";
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    model.after(" ", sourceLink);

    function updateModelLink() {
        const spec = cfg.models[model.value];
        const url = spec.model_url || (
            spec.backend === "transformersjs"
                ? `https://huggingface.co/${spec.model_id}`
                : null
        );
        sourceLink.hidden = !url;
        if (url) sourceLink.href = url;
    }

    const run = document.createElement("button");
    run.type = "button";
    run.textContent = "Run tool";
    run.hidden = true;
    //clear.before(run);
    run.className = "llm-run";

    const initialHistory = cfg.history || [];
    let history = [...initialHistory];

    let pending = null;
    let namespace = null;

    // function write(text) {
    //     log.append(document.createTextNode(text + "\n\n"));
    //     log.scrollTop = log.scrollHeight;
    // }

    function write(text) {
        const types = [
            ["You: ", "user"],
            ["Model: ", "agent"],
            ["Tool requested: ", "tool-call"],
            ["Running tool: ", "tool-running"],
            ["Tool result: ", "tool-result"],
            ["Python: ", "python"],
            ["Error: ", "error"]
        ];

        const entry = document.createElement("div");
        const match = types.find(([prefix]) => text.startsWith(prefix));

        entry.className = "llm-message llm-" + (match?.[1] || "info");

        if (match) {
            const label = document.createElement("strong");
            label.textContent = match[0];
            entry.append(label, document.createTextNode(text.slice(match[0].length)));
        } else {
            entry.textContent = text;
        }
        
        if (match?.[1] === "tool-call") {
            entry.append(run);
        }

        log.append(entry);
        log.scrollTop = log.scrollHeight;
    }
    
    function responseError(message, response) {
        return new Error(
            message + "\nModel response:\n" +
            JSON.stringify(response, null, 2)
        );
    }

    function busy(value) {
        send.disabled = prompt.disabled = value || pending !== null;
        clear.disabled = model.disabled = run.disabled = value;
        run.hidden = pending === null;
    }

    async function reset() {
        history = [...initialHistory];
        pending = null;
        namespace?.destroy();
        namespace = null;
        log.replaceChildren();
        if (cfg.state?.length) {
            busy(true);
            const box = document.createElement("div");
            box.className = "llm-message llm-tool-result";
            log.append(box);

            try {
                await showState(box);
            } catch (error) {
                write("Error: " + error.message);
            }
        }
        history.forEach(m => {
            if (m.role === "user" || m.role === "assistant")
                write((m.role === "user" ? "You: " : "Model: ") + m.content);
        });
        prompt.value = "";
        send.textContent = (cfg.models[model.value].api || cfg.api) === "completion"
            ? "Complete (current prompt only)" : "Send";    
        updateModelLink()
        busy(false);
    }

    clear.onclick = reset;
    model.onchange = reset;

    async function ask(turn, allowTools = true, onChunk = () => {}) {
        const spec = cfg.models[model.value];
        const api = spec.api || cfg.api || "chat";
        
        const system = root.querySelector(".llm-system")?.value ?? cfg.system;
        const messages = system
            ? [{role: "system", content: system}, ...turn]
            : turn;

        // pull parameters from config
        const parameters = {
            ...cfg.parameters,
            ...spec.parameters
        };

        root.querySelectorAll(".llm-control").forEach(control => {
            parameters[control.dataset.param] = Number(control.value);
        });

        const payload = {
            model: model.value,
            ...parameters
        };

        // const payload = {
        //    model: model.value,
        //    ...cfg.parameters,
        //    ...spec.parameters
        //};
        //root.querySelectorAll(".llm-control").forEach(control => {
        //    payload[control.dataset.param] = Number(control.value);
        //});

        if (api === "chat") {
            payload.messages = messages;
            if (tools.length) {
                payload.tools = tools;
                payload.tool_choice = allowTools ? "auto" : "none";
                payload.parallel_tool_calls = false;
                payload.stream = false;
            }
        } else {
            payload.prompt = turn.at(-1).content;
        }

        // payload.stream = api === "completion" || !tools.length;
        payload.stream = api === "completion"
            ? !payload.logprobs
            : !tools.length;

        

        // Local inference using Transformers.js
        if (spec.backend === "transformersjs") {
            const choice = await ggAskLocal(
                spec, api, {...payload, parameters}, onChunk,
                status => { send.textContent = status; },
                template => write("Serialized chat prompt:\n" + template)
            );
            return {api, choice};
        }

        // Remote API handling 
        const userKey = root.querySelector(".llm-key")?.value.trim();
        const encodedKey = spec.api_key || cfg.api_key;
        const key = userKey || (encodedKey ? atob(encodedKey) : "");
        const headers = {"Content-Type": "application/json"};
        if (key) headers.Authorization = `Bearer ${key}`;

        const response = await fetch(spec.endpoint, {
            method: "POST", headers, body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const detail = await response.text();
            throw new Error(`${response.status}: ${detail || response.statusText}`);
        }

        if (payload.stream) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "", answer = "";

            while (true) {
                const {value, done} = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, {stream: true});
                const events = buffer.split(/\r?\n\r?\n/);
                buffer = events.pop();

                for (const event of events) {
                    const data = event.match(/^data:\s*(.*)$/m)?.[1];
                    if (!data || data === "[DONE]") continue;

                    const choice = JSON.parse(data).choices?.[0];
                    const chunk = api === "chat"
                        ? choice?.delta?.content : choice?.text;

                    if (chunk) {
                        answer += chunk;
                        onChunk(chunk);
                    }
                }
            }

            if (!answer) throw new Error("The model returned no text.");
            return {
                api,
                choice: api === "chat"
                    ? {message: {content: answer}}
                    : {text: answer}
            };
        }

        const data = await response.json();
        const choice = data.choices?.[0];
        if (!choice) {
            throw responseError("The model returned no choices.", data);
        }
        return {api, choice};
    }
        
    async function showState(box) {
        if (!cfg.state?.length) return;

        const task = async () => {
            const pyodide = await getPyodide();

            if (!namespace) {
                namespace = pyodide.runPython("dict()");
                await pyodide.runPythonAsync(cfg.python, {globals: namespace});
            }

            namespace.set("_gg_names", JSON.stringify(cfg.state));
            return pyodide.runPythonAsync(
                'import json\njson.dumps({n: globals().get(n) ' +
                'for n in json.loads(_gg_names)}, default=str)',
                {globals: namespace}
            );
        };

        const result = pythonAppQueue.then(task, task);
        pythonAppQueue = result.catch(() => {});

        const details = document.createElement("details");
        details.className = "llm-state";
        details.innerHTML = "<summary>State</summary>";

        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(JSON.parse(await result), null, 2);
        details.append(pre);
        box.append(details);
    }


    function execute(call) {
        const task = async () => {
            const name = call.function.name;
            if (!tools.some(t => t.type === "function" && t.function?.name === name)) {
                throw new Error("Unknown tool: " + name);
            }
            const args = JSON.parse(call.function.arguments);
            if (typeof cfg.python !== "string") {
                throw new Error("Tools require a python block.");
            }
            const pyodide = await getPyodide();
            pyodide.setStdout({batched: text => write("Python: " + text)});
            pyodide.setStderr({batched: text => write("Python: " + text)});

            // Define the instructor's Python functions once per chat.
            if (!namespace) {
                namespace = pyodide.runPython("dict()");
                try {
                    await pyodide.runPythonAsync(cfg.python, {globals: namespace});
                } catch (error) {
                    namespace.destroy();
                    namespace = null;
                    throw error;
                }
            }

            // Arguments are passed as data, never as executable Python source.
            namespace.set("_gg_request", JSON.stringify({name, args}));
            return pyodide.runPythonAsync(
                'import json as _gg_json\n' +
                '_gg_call = _gg_json.loads(_gg_request)\n' +
                '_gg_json.dumps(globals()[_gg_call["name"]](**_gg_call["args"]), allow_nan=False)',
                {globals: namespace}
            );
        };
        const result = pythonAppQueue.then(task, task);
        pythonAppQueue = result.catch(() => {});
        return result;
    }

    function showLogprobs(choice) {
        const lp = choice.logprobs;
        if (!lp?.tokens?.length) return;

        const box = log.lastElementChild;
        box.lastChild.remove(); // Replace plain completion text with tokens.

        const probabilities = document.createElement("pre");
        probabilities.hidden = true;

        lp.tokens.forEach((token, i) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "llm-token";
            button.textContent = token;
            button.title = "Click for token probabilities";

            button.onclick = () => {
                const candidates = {...(lp.top_logprobs?.[i] || {})};

                // Include the generated token even if it is not in the top alternatives.
                if (lp.token_logprobs?.[i] != null)
                    candidates[token] = lp.token_logprobs[i];

                probabilities.textContent =
                    `Token ${i + 1}: ${JSON.stringify(token)}\n` +
                    Object.entries(candidates)
                        .sort((a, b) => b[1] - a[1])
                        .map(([t, p]) =>
                            `${t === token ? "→ " : "  "}${JSON.stringify(t)}: ` +
                            `${(100 * Math.exp(p)).toFixed(1)}%`
                        ).join("\n");

                probabilities.hidden = false;
            };

            box.append(button);
        });

        box.append(probabilities);
    }

    send.onclick = async () => {
        const text = prompt.value.trim();
        if (!text || send.disabled) return;
        const turn = [...history, {role: "user", content: text}];
        prompt.value = "";
        busy(true);

        const normalSendLabel = send.textContent;

        write("You: " + text);

        try {
            let streamed = false;
            const {api, choice} = await ask(turn, true, chunk => {
                if (!streamed) {
                    write("Model: ");
                    streamed = true;
                }
                log.lastElementChild.lastChild.textContent += chunk;
                log.scrollTop = log.scrollHeight;
            });
            const message = choice.message;
            const calls = api === "chat" && tools.length
                ? (message?.tool_calls || [])
                : [];

            if (!Array.isArray(calls) || calls.length > 1) {
                throw responseError("Only one tool call is allowed per turn.", choice);
            }
            if (calls.length) {
                const call = calls[0];
                if (call.type !== "function" || !call.id || !call.function?.name) {
                    throw responseError("Invalid function call returned by the model.", choice);
                }
                history = [...turn, message];
                pending = call;
                if (message.content) write("Model: " + message.content);
                write("Tool requested: " + call.function.name + " " + call.function.arguments);
            } else {
                const answer = api === "chat" ? message?.content : choice.text;
                if (typeof answer !== "string") {
                    throw responseError("The model returned no text.", choice);
                }
                history = [...turn, {role: "assistant", content: answer}];
                if (!streamed) write("Model: " + answer);
                if (api === "completion") showLogprobs(choice);
            }
        } catch (error) {
            write("Error: " + error.message);
            prompt.value = text;
        } finally {
            send.textContent = normalSendLabel;
            busy(false);
        }
    };

    run.onclick = async () => {
        if (!pending || run.disabled) return;
        const call = pending;
        busy(true);
        write("Running tool: " + call.function.name);
        const box = log.lastElementChild;
        try {
            let content;
            try {
                content = await execute(call);
            } catch (error) {
                history.push({
                    role: "tool", tool_call_id: call.id,
                    content: JSON.stringify({error: error.message})
                });
                write("Error: " + error.message);
                return;
            }
            history.push({role: "tool", tool_call_id: call.id, content});
            
            //write("Tool result: " + content);
            box.append(document.createTextNode("\nTool result: " + content));
            box.classList.replace("llm-tool-running", "llm-tool-result");

            await showState(box);

            const {choice} = await ask(history, false);
            const message = choice.message;
            if (message?.tool_calls?.length) {
                throw new Error("Only one tool call is allowed per turn.", choice);
            }
            if (typeof message?.content !== "string") {
                throw new Error("The model returned no text.", choice);
            }
            history.push(message);
            write("Model: " + message.content);
        } catch (error) {
            write("Error: " + error.message);
        } finally {
            pending = null;
            busy(false);
        }
    };
    reset();
});
"""


LLM_LOCAL_JS = r"""
function localLLMWorker() {
    let lib, llm, modelId, queue = Promise.resolve();
    const send = (id, type, data = {}) => postMessage({id, type, ...data});

    async function run({id, spec, api, payload}) {
        const {pipeline, TextStreamer, LogitsProcessor, env} = lib ??=
            await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.0');
        env.allowLocalModels = false;
        env.backends.onnx.wasm.numThreads = 1;

        // Load model, preferring GPU with CPU fallback.
        if (modelId !== spec.model_id) {

            // extract parameters
            const {
                model, messages: _, prompt: __, tools, tool_choice,
                parallel_tool_calls, stream, logprobs, max_tokens,
                ...generation
            } = payload;

            await llm?.dispose();
            llm = null;
            modelId = null;
            send(id, 'status', {text: 'Loading model...'});
            const load = (device, dtype) =>
                pipeline('text-generation', spec.model_id, {device, dtype});
            try {
                if (!await navigator.gpu?.requestAdapter())
                    throw Error('No usable WebGPU adapter');
                //llm = await load('webgpu', 'q4f16');
                llm = await load('webgpu', 'q4');
            } catch {
                send(id, 'status', {text: 'Using CPU...'});
                llm = await load('wasm', 'q8');
            }
            modelId = spec.model_id;
        }

        //if (api === 'chat' && payload.tools?.length)
        //    throw Error('Local tool calling is not yet supported.');

        const t = llm.tokenizer;

        // Tool calling
        const toolMode = api === 'chat' && !!payload.tools?.length;
        let messages = payload.messages;

        if (toolMode) {
            // Restore previous tool calls as ordinary assistant text.
            messages = messages.map(m => m.tool_calls
                ? {role: 'assistant', content: m.tool_call_text}
                : {role: m.role, content: m.content}
            );

            const instructions =
                'List of tools: ' +
                JSON.stringify(payload.tools.map(t => t.function)) + '\n' +
                (payload.tool_choice === 'none'
                    ? 'Use the tool result to answer. Do not call another tool.'
                    : 'If a tool is needed, output ONLY JSON: ' +
                    '{"name":"function_name","arguments":{"key":"value"}}. ' +
                    'Otherwise answer normally.');

            if (messages[0]?.role === 'system')
                messages[0].content += '\n' + instructions;
            else
                messages.unshift({role: 'system', content: instructions});
        }


        if (api === 'chat' && spec.show_template)
            send(id, 'template', {text: t.apply_chat_template(
                messages,
                {tokenize: false, add_generation_prompt: true}
            )});

        const n = api === 'completion'
            ? Math.max(0, Math.min(10, Math.floor(Number(payload.logprobs) || 0)))
            : 0;

        const probs = {tokens: [], token_logprobs: [], top_logprobs: []};
        const token = i => t.decode([i], {
            skip_special_tokens: false,
            clean_up_tokenization_spaces: false
        });
        let next, answer = '';

        // Capture the probability distribution before sampling.
        class Capture extends LogitsProcessor {
            _call(ids, logits) {
                const a = logits[0].data, top = [];

                for (let i = 0; i < a.length; i++) {
                    const j = top.findIndex(k => a[i] > a[k]);
                    if (j >= 0) top.splice(j, 0, i);
                    else if (top.length < n) top.push(i);
                    if (top.length > n) top.pop();
                }

                const m = a[top[0]];
                const z = m + Math.log(
                    top.reduce((s, i) => s + Math.exp(a[i] - m), 0)
                );

                next = {a, top, z};
                return logits;
            }
        }


        const streamer = new TextStreamer(t, {
            skip_prompt: true,
            callback_function: chunk => {
                answer += chunk;
                // send(id, 'chunk', {chunk});
                if (!toolMode) send(id, 'chunk', {chunk});
            },
            token_callback_function: ids => {
                if (!next) return;
                const {a, top, z} = next;
                for (const k of ids) {
                    const i = Number(k);
                    probs.tokens.push(token(i));
                    probs.token_logprobs.push(a[i] - z);
                    probs.top_logprobs.push(Object.fromEntries(
                        top.map(j => [token(j), a[j] - z])
                    ));
                }
                next = null;
            }
        });

        
        const {max_tokens, logprobs, ...generation} = payload.parameters;
        const temperature = Number(generation.temperature ?? 1);

        send(id, 'status', {text: 'Generating...'});

        await llm(api === 'chat' ? messages : payload.prompt, {
            ...generation,
            max_new_tokens: Math.max(1, Math.min(2048, Math.floor(Number(
                generation.max_new_tokens ?? max_tokens ??
                (api === 'chat' ? 512 : 32)
            )))),
            do_sample: generation.do_sample ?? (temperature > 0),
            temperature: temperature > 0 ? temperature : 1,
            streamer,
            logits_processor: n ? [new Capture()] : []
        });


        //const temperature = Number(payload.temperature ?? 1);
        //send(id, 'status', {text: 'Generating...'});
        //await llm(api === 'chat' ? messages : payload.prompt, {
        //    ...generation,
        //    max_new_tokens: Math.max(1, Math.min(2048,
        //        Math.floor(Number(max_tokens ?? (api === 'chat' ? 512 : 32)))
        //    )),
        //    do_sample: temperature > 0,
        //    streamer,
        //    logits_processor: n ? [new Capture()] : []
        //});
        //await llm(api === 'chat' ? messages : payload.prompt, {
        //    max_new_tokens: Math.max(1, Math.min(2048,
        //    Math.floor(Number(
        //        payload.max_tokens ?? (api === "chat" ? 512 : 32)
        //    )))),
        //    do_sample: temperature > 0,
        //    temperature: temperature > 0 ? temperature : 1,
        //    //top_k: Number(payload.top_k ?? 50),
        //    top_k: n || 5,
        //    streamer,
        //    logits_processor: n ? [new Capture()] : []
        //});

        // convert JSON into tool call
        let message = {content: answer};

        if (toolMode && payload.tool_choice !== 'none') {
            try {
                const json = answer.match(/\{[\s\S]*\}/)?.[0];
                const call = JSON.parse(json);

                if (payload.tools.some(t => t.function.name === call.name) &&
                    call.arguments &&
                    typeof call.arguments === 'object' &&
                    !Array.isArray(call.arguments)) {

                    message = {
                        content: null,
                        tool_call_text: answer,
                        tool_calls: [{
                            id: `local_${id}`,
                            type: 'function',
                            function: {
                                name: call.name,
                                arguments: JSON.stringify(call.arguments)
                            }
                        }]
                    };
                }
            } catch {
                // Not a valid JSON tool call; treat as ordinary text.
            }
        }

        const choice = api === 'chat'
            ? {message}
            : {text: answer};

        //const choice = api === 'chat'
        //    ? {message: {content: answer}}
        //    : {text: answer};
        if (n) choice.logprobs = probs;
        send(id, 'done', {choice});
    }

    self.onmessage = ({data}) => {
        queue = queue.then(() => run(data)).catch(e =>
            send(data.id, 'error', {message: String(e.message || e)}));
    };
}

// Main-thread interface.
let ggWorker, ggNext = 0;
const ggJobs = new Map();

function ggAskLocal(spec, api, payload, onChunk, onStatus, onTemplate) {
    if (!ggWorker) {
        const url = URL.createObjectURL(new Blob(
            [`(${localLLMWorker.toString()})();`],
            {type: 'text/javascript'}
        ));
        ggWorker = new Worker(url, {type: 'module'});
        URL.revokeObjectURL(url);

        ggWorker.onmessage = ({data: d}) => {
            const j = ggJobs.get(d.id);
            if (!j) return;
            if (d.type === 'chunk') j.onChunk(d.chunk);
            if (d.type === 'status') j.onStatus(d.text);
            if (d.type === 'template') j.onTemplate(d.text);
            if (d.type === 'done' || d.type === 'error') {
                ggJobs.delete(d.id);
                d.type === 'done'
                    ? j.resolve(d.choice)
                    : j.reject(Error(d.message));
            }
        };

        ggWorker.onerror = e => {
            ggJobs.forEach(j => j.reject(
                Error(e.message || 'Worker failed')
            ));
            ggJobs.clear();
            ggWorker.terminate();
            ggWorker = null;
        };
    }

    const id = ++ggNext;
    return new Promise((resolve, reject) => {
        ggJobs.set(id, {
            resolve, reject, onChunk, onStatus, onTemplate
        });
        ggWorker.postMessage({id, spec, api, payload});
    });
}
"""


# LLM_CHAT_JS = r"""
# // LLM chat
# document.querySelectorAll(".llm-chat").forEach(root => {{
#     const cfg = JSON.parse(root.querySelector(".llm-config").value);
#     const log = root.querySelector(".llm-messages");
#     const prompt = root.querySelector(".llm-prompt");
#     const model = root.querySelector(".llm-model");
#     const send = root.querySelector(".llm-send");
#     const clear = root.querySelector(".llm-clear");
#     let history = [];

#     function reset() {{
#         history = [];
#         log.replaceChildren();
#         prompt.value = "";
#     }}

#     clear.onclick = reset;
#     model.onchange = reset;

#     send.onclick = async () => {{
#         const text = prompt.value.trim();
#         if (!text) return;

#         const spec = cfg.models[model.value];
#         const api = spec.api || cfg.api || "chat";

#         const messages = [
#             ...history,
#             {{role: "user", content: text}}
#         ];

#         if (cfg.system)
#             messages.unshift({{role: "system", content: cfg.system}});

#         const payload = {{
#             model: model.value,
#             ...cfg.parameters,
#             ...spec.parameters
#         }};

#         root.querySelectorAll(".llm-control").forEach(control => {{
#             payload[control.dataset.param] = Number(control.value);
#         }});

#         if (api === "chat") {{
#             payload.messages = messages;
#         }} else {{
#             payload.prompt = messages
#                 .map(m => `${{m.role}}: ${{m.content}}`)
#                 .join("\\n") + "\\nassistant:";
#         }}

#         const userKey = root.querySelector(".llm-key")?.value.trim();
#         const encodedKey = spec.api_key || cfg.api_key;
#         const key = userKey || (encodedKey ? atob(encodedKey) : "");

#         const headers = {{"Content-Type": "application/json"}};
#         if (key) headers.Authorization = `Bearer ${{key}}`;

#         prompt.value = "";
#         log.insertAdjacentText("beforeend", `You: ${{text}}\n\n`);

#         for (const el of [send, clear, model])
#             el.disabled = true;

#         try {{
#             const response = await fetch(spec.endpoint, {{
#                 method: "POST",
#                 headers,
#                 body: JSON.stringify(payload)
#             }});

#             if (!response.ok)
#                 throw new Error(
#                     `${{response.status}} ${{response.statusText}}`
#                 );

#             const choice = (await response.json()).choices[0];
#             const answer = api === "chat"
#                 ? choice.message.content
#                 : choice.text;

#             history.push(
#                 {{role: "user", content: text}},
#                 {{role: "assistant", content: answer}}
#             );

#             log.insertAdjacentText(
#                 "beforeend",
#                 `Model: ${{answer}}\n\n`
#             );
#         }} catch (error) {{
#             log.insertAdjacentText(
#                 "beforeend",
#                 `Error: ${{error.message}}\n\n`
#             );
#         }} finally {{
#             for (const el of [send, clear, model])
#                 el.disabled = false;

#             log.scrollTop = log.scrollHeight;
#         }}
#     }};
# }});
# """

def iframe_fence(source, language, css_class, options, md, **kwargs):
    config = yaml.safe_load(source) or {}

    url = config["url"]
    title = config.get("title", "Embedded content")

    # width = config.get("width", "100%")
    # height = config.get("height", "100%")
    width = config.get("width", "117.65%")
    height = config.get("height", "1030px")

    def encode(values):
        return urlencode({
            key: str(value).lower() if isinstance(value, bool) else value
            for key, value in values.items()
        })

    if config.get("query"):
        url += "?" + encode(config["query"])

    if config.get("hash"):
        url += "#" + encode(config["hash"])

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

def llm_chat_fence(source, language, css_class, options, md, **kwargs):
    try:
        cfg = yaml.safe_load(source) or {}
        models = cfg.get("models", [])

        if not models:
            raise ValueError("llm-chat requires at least one model")

        for model in models:
            if not isinstance(model, dict):
                raise ValueError("Each model must contain name and endpoint")
            if "name" not in model:
                raise ValueError("Each model requires a name")
            # if "endpoint" not in model:
            #     raise ValueError(
            #         f'Model "{model["name"]}" requires an endpoint'
            #     )
            if model.get("backend") == "transformersjs":
                if not model.get("model_id"):
                    raise ValueError("Local model requires model_id")
            elif "endpoint" not in model:
                raise ValueError("Remote model requires endpoint")


            

            api = model.get("api", cfg.get("api", "chat"))
            if api not in ("chat", "completion"):
                raise ValueError(
                    f'Model "{model["name"]}" api must be '
                    '"chat" or "completion"'
                )

        # Obfuscate embedded keys. This is not security.
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
                "         Use only a restricted, rate-limited credential."
            )

        cfg["models"] = {
            model["name"]: model
            for model in models
        }

        options_html = "".join(
            f'<option value="{html.escape(str(model["name"]), quote=True)}">'
            f'{html.escape(str(model["name"]))}</option>'
            for model in models
        )

        controls_html = "".join(
            f'<label>{html.escape(name)} '
            f'<input type="number" class="llm-control" '
            f'data-param="{html.escape(name, quote=True)}" '
            f'min="{control["min"]}" '
            f'max="{control["max"]}" '
            f'step="{control.get("step", 1)}" '
            f'value="{cfg.get("parameters", {}).get(name, control["min"])}"/>'
            f'</label>'
            for name, control in cfg.get("controls", {}).items()
        )

        key_html = (
            '<label>API key: '
            '<input type="password" class="llm-key" '
            'placeholder="Optional: use your own key" '
            'autocomplete="off" /></label>'
            if cfg.get("key_field") else ""
        )

        system_html = (
            '<label>System prompt: <textarea class="llm-system" rows="2">'
            f'{html.escape(str(cfg.get("system", "")))}</textarea></label>'
            if cfg.get("show_system_prompt") else ""
        )

        tools_html = ""
        if cfg.get("tools"):
            items = ""
            for tool in cfg["tools"]:
                fn = tool["function"]
                inputs = ", ".join(
                    f'{name} ({info.get("description", info.get("type", ""))})'
                    for name, info in fn.get("parameters", {}).get("properties", {}).items()
                )
                items += (
                    f'<li><strong>{html.escape(fn["name"])}</strong>: '
                    f'{html.escape(fn.get("description", ""))} '
                    f'<i>Inputs:</i> {html.escape(inputs)}</li>'
                )
            tools_html = f'<details><summary>Available tools</summary><ul>{items}</ul></details>'
            
        return (
            '<div class="llm-chat">'
            f'<textarea class="llm-config" hidden="hidden">'
            f'{html.escape(json.dumps(cfg))}</textarea>'
            f'<label>Model: '
            f'<select class="llm-model">{options_html}</select></label>'
            f'{key_html}'
            f'{system_html}'
            f'{tools_html}'
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

    except Exception as error:
        message = f"llm-chat: {error}"
        print(f"ERROR: {message}")

        return (
            '<div class="admonition error">'
            '<p class="admonition-title">LLM Chat Error</p>'
            f'<p>{html.escape(message)}</p>'
            '</div>'
        )

def render(source, title, theme=None, exercise_position="bottom",
           arrow_navigation="activities"):
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

        # Don't provide navigation for missing titles
        if activity.title != "Activity":
            link = (
                f'<a href="?activity={i}&exercise=1" data-activity="{i}">'
                f'{html.escape(activity_title)}</a>'
            )
        else:
            print("Warning: No title for activity, not added to navigation.")
            link = ""

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
            print(f"Warning: {activity_title!r} has no exercise/step environments.")

        steps_html = []

        for j, step in enumerate(steps, start=1):
            # step_title = step.title or f"Step {j}"
            step_title_html = ET.tostring(
                list(step.etree)[0],
                encoding="unicode",
                method="html",
            )

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

    return HTML_TEMPLATE.format(
        title=html.escape(title),
        default_css=default_css,
        theme_css=theme_to_css(theme or {}),
        landing=landing,
        topnav="\n".join(topnav),
        activity_list="\n".join(activity_list),
        activities="\n".join(activity_html),
        pyodide_js=PYODIDE_JS,
        llm_chat_js=LLM_CHAT_JS,
        llm_local_js=LLM_LOCAL_JS,
        arrow_navigation=arrow_navigation,
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

    arrow_navigation = str(metadata.get("navigation", "activities")).lower()
    if arrow_navigation not in {"activities", "exercises"}:
        arrow_navigation = "activities"
        
    output.write_text(
        render(source, title, theme, exercise_position, arrow_navigation),
        encoding="utf-8",
    )

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()