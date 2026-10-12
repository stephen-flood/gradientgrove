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
<div id="python-app-frame" hidden>
    <iframe
        class="python-app"
        src="/jupyterlite/repl/index.html?kernel=python&execute=0&showBanner=0&hideCodeInput=1&clearCellsOnExecute=1"
        title="Python App"
        style="width: 100%; height: 500px;">
    </iframe>
</div>

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
    page.querySelectorAll(".exercise").forEach(step => step.hidden = true);

    const step = page.querySelector(
        `#activity-${{activity}}-step-${{n}}`
    );

    step.hidden = false;
    runPythonApp(step);

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

// One shared Pyodide instance for every python-app on the page.
let pythonAppPyodide = null;
let pythonAppNamespace = null;
let pythonAppOutput = null;


// Create an inline input box and wait for Enter.
globalThis.pythonAppInput = function(prompt = "") {{
    return new Promise(resolve => {{
        const row = document.createElement("div");

        const label = document.createElement("span");
        label.textContent = prompt;

        const input = document.createElement("input");
        input.type = "text";

        row.append(label, input);
        pythonAppOutput.appendChild(row);

        input.addEventListener("keydown", event => {{
            if (event.key !== "Enter") return;

            event.preventDefault();
            input.disabled = true;
            resolve(input.value);
        }});

        input.focus();
    }});
}};


// Load Pyodide once and make ordinary Python input() use our inline box.
async function getPythonAppPyodide() {{
    if (pythonAppPyodide) return pythonAppPyodide;

    pythonAppPyodide = await loadPyodide();

    await pythonAppPyodide.runPythonAsync(`
import builtins
from js import pythonAppInput
from pyodide.ffi import run_sync

def _python_app_input(prompt=""):
    return run_sync(pythonAppInput(prompt))

builtins.input = _python_app_input
`);

    return pythonAppPyodide;
}}


// Run the python-app contained in this activity/exercise.
async function runPythonApp(scope) {{
    const app = scope.matches?.(".python-app")
        ? scope
        : scope.querySelector(".python-app");

    if (!app) return;

    const source = app.querySelector(".python-app-source");
    const output = app.querySelector(".python-app-output");

    pythonAppOutput = output;
    output.replaceChildren();

    const pyodide = await getPythonAppPyodide();

    // stdout and stderr go into this app's output box.
    const write = text =>
        output.append(document.createTextNode(text + "\\n"));

    pyodide.setStdout({{
        batched: write
    }});

    pyodide.setStderr({{
        batched: write
    }});

    // Default: fresh user namespace.
    // {persist} reuses the namespace from the previous app.
    if (!pythonAppNamespace || source.dataset.persist !== "true") {{
        pythonAppNamespace = pyodide.runPython("dict()");
    }}

    try {{
        await pyodide.runPythonAsync(source.value, {{
            globals: pythonAppNamespace
        }});
    }} catch (error) {{
        write(String(error));
    }}
}}
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


def python_app_fence(source, language, css_class, options, md, **kwargs):
    persist = "persist" in kwargs.get("attrs", {})

    return (
        f'<div class="python-app-slot" '
        f'data-persist="{str(persist).lower()}">'
        f'<textarea class="python-app-source" hidden="hidden">'
        f'{html.escape(source)}'
        f'</textarea>'
        f'</div>'
    )


def interactive_python_fence(source, language, css_class, options, md, **kwargs):
    attrs = kwargs.get("attrs", {})
    run = "run" in attrs

    config = {
        "title": "Interactive Python",
        "url": JUPYTERLITE_REPL,
        "height": "500px",
        "query": {
            "kernel": "python",
            "showBanner": 0,
            "code": source.strip(),
        },
    }

    if not run:
        config["query"]["execute"] = 0

    return iframe_fence(
        yaml.safe_dump(config, sort_keys=False),
        language,
        css_class,
        options,
        md,
        **kwargs,
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


        # Python apps in an activity share one JupyterLite/Pyodide kernel.
        if "python-app-source" in exercise_body:
            activity_body += iframe_fence(
                yaml.safe_dump({
                    "title": "Python App",
                    "url": JUPYTERLITE_REPL,
                    "class": "python-app",
                    "height": "500px",
                    "query": {
                        "kernel": "python",
                        "execute": 0,
                        "showBanner": 0,
                        "hideCodeInput": 1,
                        "clearCellsOnExecute": 1,
                    },
                }),
                "", "", {}, None,
            )

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