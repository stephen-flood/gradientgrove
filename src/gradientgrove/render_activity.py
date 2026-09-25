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

THEME_VARIABLES = {
    "background": "--gg-bg",
    "paper": "--gg-paper",
    "text": "--gg-text",
    "primary": "--gg-primary",
    "accent": "--gg-accent",
    "secondary": "--gg-secondary",
}


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

    document
        .querySelector(`nav.top a[data-activity="${{activity}}"]`)
        ?.classList.add("active");

    const step = Number(
        new URLSearchParams(location.search).get("exercise") || 1
    );

    showStep(step);
}}
</script>

</body>
</html>
"""


def render(source, title, theme=None, exercise_position="bottom"):
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

        prev_activity = (
            f'<a class="activity-arrow activity-arrow-left" '
            f'href="?activity={i - 1}&exercise=1" '
            f'aria-label="Previous activity"></a>'
            if i > 1 else ""
        )

        next_activity = (
            f'<a class="activity-arrow activity-arrow-right" '
            f'href="?activity={i + 1}&exercise=1" '
            f'aria-label="Next activity"></a>'
            if i < len(activities) else ""
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
            step_title = step.title or f"Step {j}"
            
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

        exercise_body = "".join(steps_html)

        activity_content = (
            f'<div class="activity-content">'
            f'{activity_body}'
            f'</div>'
        )

        if exercise_position == "top":
            stack = exercise_body + activity_content
        else:
            stack = activity_content + exercise_body

        activity_html.append(
            f'<section class="activity" id="activity-{i}" hidden>'
            f'{prev_activity}'
            f'{next_activity}'
            f'<h1>{html.escape(activity_title)}</h1>'
            f'<div class="activity-stack">'
            f'{stack}'
            f'</div>'
            f'</section>'
        )            

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