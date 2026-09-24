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
from gradientgrove.markdown_publish import build_tree


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>

<style>
body {{
    margin: 0;
    font-family: system-ui, sans-serif;
    background: #f7f7f7;
    color: #222;
}}

nav.top {{
    padding: 1rem;
    background: white;
    border-bottom: 1px solid #ddd;
}}

nav.top a {{
    margin-right: 1rem;
}}

main {{
    max-width: 1400px;
    margin: auto;
    padding: 1rem;
}}

.landing {{
    max-width: 800px;
}}

.activity iframe {{
    width: 100%;
    height: 65vh;
    border: 0;
    background: white;
}}

.exercise {{
    margin-top: 1rem;
    padding: 1rem;
    background: white;
    border: 1px solid #ddd;
}}

.exercise-nav {{
    display: flex;
    justify-content: space-between;
    margin-top: 1rem;
}}

.activity-list a {{
    display: block;
    margin: .5rem 0;
    padding: 1rem;
    border: 1px solid #ccc;
    background: white;
}}

.admonition,
details {{
    margin: 1rem 0;
    padding: .75rem 1rem;
    border-left: 4px solid #888;
    background: #f5f5f5;
}}

summary,
.admonition-title {{
    font-weight: bold;
}}
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

<h2>Activities</h2>
<div class="activity-list">
{activity_list}
</div>
</section>

{activities}

</main>

<script>
const activity = new URLSearchParams(location.search).get("activity");
const page = document.querySelector(`#activity-${{activity}}`);

function showStep(n) {{
    page.querySelectorAll(".exercise").forEach(step => step.hidden = true);
    page.querySelector(`#activity-${{activity}}-step-${{n}}`).hidden = false;

    const url = new URL(location);
    url.searchParams.set("exercise", n);
    history.replaceState(null, "", url);
}}

if (activity) {{
    document.querySelector("#landing").hidden = true;
    page.hidden = false;

    const step = Number(
        new URLSearchParams(location.search).get("exercise") || 1
    );

    showStep(step);
}}
</script>

</body>
</html>
"""


def render(source, title):
    """Build the GradientGrove AST and render the activity HTML page."""

    tree = build_tree(
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

    topnav = []
    activity_list = []
    activity_html = []

    for i, activity in enumerate(activities, start=1):
        activity_title = activity.title or f"Activity {i}"

        # Activity links appear both in the top navigation and landing page.
        link = (
            f'<a href="?activity={i}&step=1">'
            f'{html.escape(activity_title)}</a>'
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
            raise ValueError(
                f"{activity_title!r} has no !!! step environments."
            )

        steps_html = []

        for j, step in enumerate(steps, start=1):
            step_title = step.title or f"Step {j}"
            
            prev_button = (
                f'<button onclick="showStep({j - 1})">← Back</button>'
                if j > 1 else ""
            )

            next_button = (
                f'<button onclick="showStep({j + 1})">Next →</button>'
                if j < len(steps) else ""
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
            
            steps_html.append(
                f'<section class="exercise" id="activity-{i}-step-{j}" hidden>'
                f'<h2>{html.escape(step_title)}</h2>'
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

        activity_html.append(
            f'<section class="activity" id="activity-{i}" hidden>'
            f'<h1>{html.escape(activity_title)}</h1>'
            f'{activity_body}'
            f'{"".join(steps_html)}'
            f'</section>'
        )

    return HTML_TEMPLATE.format(
        title=html.escape(title),
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

    output.write_text(
        render(source, title),
        encoding="utf-8",
    )

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()