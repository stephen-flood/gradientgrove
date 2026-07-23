"""Utilities for rendering LaTeX/TikZ fenced blocks to SVG for Markdown pipelines.


Requirements:
    - pdflatex and dvisvgm
    - Python-Markdown with pymdown-extensions


MkDocs (mkdocs.yml):
    markdown_extensions:
    - attr_list
    - pymdownx.superfences:
        custom_fences:
            - name: latex
              class: latex-svg
              format: !!python/name:latex_fence.latex_svg_fence # no caching
              format: !!python/name:latex_fence.latex_cache_fence # with caching
           


Python-Markdown:
    import latex_fence
    html = markdown.markdown(
        text,
        extensions=["attr_list", "pymdownx.superfences"],
        extension_configs={"pymdownx.superfences": {"custom_fences": [
            {"name": "latex", "class": "latex-svg", "format": latex_fence.latex_svg_fence}
        ]}},
    )
"""

from __future__ import annotations

import base64
import html
import subprocess
import tempfile
from pathlib import Path

import hashlib


WRAPPER = r"""
\documentclass[border=1pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{shapes.geometric} 
\usetikzlibrary{shadings}
\usetikzlibrary{arrows,calc,decorations.markings}
\usetikzlibrary{decorations.pathmorphing} 
\usetikzlibrary{positioning,fit}

\usetikzlibrary{graphs, graphdrawing}
\usegdlibrary{trees}

%%
\tikzstyle{decision} = [diamond, draw, fill=gray!10, text width=6em, text badly centered, inner sep=0pt]
\tikzstyle{block} = [rectangle, draw, fill=gray!10, text width=6em, text centered, rounded corners, minimum height=2em]
\tikzstyle{reference} = [-latex,decorate, decoration={snake,pre length=4pt,post length=4pt}]
\tikzstyle{box} = [minimum height=0.75cm,minimum width=0.75cm]

\tikzset{gridlines/.style={very thin,step=1}}
\tikzset{axes/.style={latex-latex}}
\tikzset{curve/.style={color=black,stealth-stealth}}
\tikzset{open circle/.style={color=black, very thick, fill=white}}
\tikzset{closed circle/.style={color=black, very thick, fill=black}}

\usepackage{pgfplots} 
\pgfplotsset{width=7cm,compat=1.18}
\pgfplotsset{colormap={CM}{color(-1cm)=(orange!60) color(0cm)=(black!20) color(1cm)=(blue!60!white)}}
%% Simple Style to do Dimensions
\pgfarrowsdeclarecombine*{|<}{>|}{latex}{latex}{|}{|}
\tikzset{dimen/.style={|<->|,>=latex,thin,every rectangle node/.style={fill=white,midway,font=\sffamily}},}
%% Usage
%% standard dimension:
%%		\draw [dimen] (1,0) -- (1,1.75) node {$f(x)$};
%% short dimension:
%%   \draw [dimen] (0,-.5) -- (0.4,-.5) node[below=1mm,midway] {$\Delta x$};
%%%% Begin: Set up TikZ Package and Styles %%%%

%%%% Begin: TikZ SPLINE 
%%	Draw spline through (x1,y1) with slope m1 and (x2,y2) with slope m2
%%		\drawtikzspline(x1,y1,m1,x2,y2,m2)
%%
\def\drawtikzspline(#1,#2,#3,#4,#5,#6){ \draw[curve,domain=(#1):(#4)] plot (\x , { ( (((#3) + (#6))*(#1) - ((#3) + (#6))*(#4) - 2*(#2) + 2*(#5))/((#1)^3 - 3*((#1)^2)*(#4) + 3*(#1)*((#4)^2) - (#4)^3) )*((\x)^3) + ( -(((#3) + 2*(#6))*((#1)^2) + ((#3) - (#6))*(#1)*(#4) - (2*(#3) + (#6))*((#4)^2) - 3*((#1) + (#4))*(#2) + 3*((#1) + (#4))*(#5))/((#1)^3 - 3*((#1)^2)*(#4) + 3*(#1)*((#4)^2) - (#4)^3) ) *((\x)^2) + ( ((#6)*((#1)^3) + (2*(#3) + (#6))*((#1)^2)*(#4) - ((#3) + 2*(#6))*(#1)*((#4)^2) - (#3)*((#4)^3) - 6*(#1)*(#4)*(#2) + 6*(#1)*(#4)*(#5))/((#1)^3 - 3*((#1)^2)*(#4) + 3*(#1)*((#4)^2) - (#4)^3) ) * (\x) + ( -((#6)*((#1)^3)*(#4) + ((#3) - (#6))*((#1)^2)*(#4)^2 - (#3)*(#1)*((#4)^3) - (3*(#1)*((#4)^2) - (#4)^3)*(#2) - ((#1)^3 - 3*((#1)^2)*(#4))*(#5))/((#1)^3 - 3*((#1)^2)*(#4) + 3*(#1)*((#4)^2) - (#4)^3))}) }
%%%% End: TikZ SPLINE 

\usepackage{beamerarticle}
\begin{document}
\noindent 
%s
\end{document}
""".strip()


def _compile_to_svg(latex_body: str) -> bytes:
    latex_src = WRAPPER % latex_body

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "x.tex").write_text(latex_src, encoding="utf-8")

        p = subprocess.run(
            # ["pdflatex", "-halt-on-error", "-interaction=nonstopmode", "x.tex"],
            ["lualatex", "-halt-on-error", "-interaction=nonstopmode", "x.tex"],
            cwd=td,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if p.returncode != 0:
            raise RuntimeError(p.stdout)

        p = subprocess.run(
            # ["pdf2svg", str(td / "x.pdf"), str(td / "x.svg")],
            ["dvisvgm", "--bbox=min", "--pdf", str(td / "x.pdf"), "-o", str(td / "x.svg")],
            cwd=td,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if p.returncode != 0:
            raise RuntimeError(p.stdout)

        return (td / "x.svg").read_bytes()


def latex_svg_fence(source, language, css_class, options, md, **kwargs):
    """Render a LaTeX/TikZ fenced block as an embedded SVG image.

    This renderer compiles the fenced block every time Markdown is rendered.
    The generated SVG is embedded directly in the returned HTML as a base64
    data URI, so the output is self-contained and does not require separate
    image files.

    Args:
        source: The raw contents of the fenced LaTeX block.
        language: The fence language name supplied by pymdownx.superfences.
        css_class: The CSS class to apply to the generated ``img`` element.
        options: Fence options supplied by pymdownx.superfences.
        md: The active Python-Markdown instance.
        **kwargs: Additional superfences data. The ``attrs`` entry may include
            an ``alt`` value for the generated image.

    Returns:
        An HTML ``img`` element with a base64-encoded SVG data URI, or an HTML
        error block if LaTeX compilation fails.
    """
    attrs = kwargs.get("attrs") or {}

    print("COMPILING LATEX FENCE")

    # alt = attrs.get("alt", "LaTeX diagram") if isinstance(attrs, dict) else "LaTeX diagram"

    alt = "LaTeX diagram"
    if isinstance(attrs, dict):
        alt = str(attrs.get("alt", alt))
    elif isinstance(attrs, (list, tuple)):
        for item in attrs:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if str(k) == "alt":
                    alt = str(v)
                    break

    try:
        svg = _compile_to_svg(source)
    except Exception as e:
        return (
            '<div class="latex-render-error">'
            "<strong>LaTeX render error</strong>"
            f"<pre>{html.escape(str(e))}</pre>"
            "</div>"
        )

    data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
    return f'<img class="{html.escape(css_class)}" src="{data_uri}" alt="{html.escape(alt)}" />'


def latex_cache_fence(source, language, css_class, options, md, **kwargs):
    """Render a LaTeX/TikZ fenced block as a cached embedded SVG image.

    The cache key is a SHA-256 hash of the LaTeX wrapper template and the
    fenced block source. If the same source is rendered again, the previously
    generated SVG is read from ``.latex_fence_cache`` instead of recompiling.
    If the source or wrapper changes, the hash changes and a new SVG is
    compiled and cached.

    Args:
        source: The raw contents of the fenced LaTeX block.
        language: The fence language name supplied by pymdownx.superfences.
        css_class: The CSS class to apply to the generated ``img`` element.
        options: Fence options supplied by pymdownx.superfences.
        md: The active Python-Markdown instance.
        **kwargs: Additional superfences data. The ``attrs`` entry may include
            an ``alt`` value for the generated image.

    Returns:
        An HTML ``img`` element with a base64-encoded SVG data URI, or an HTML
        error block if LaTeX compilation fails.
    """    
    attrs = kwargs.get("attrs") or {}

    alt = "LaTeX diagram"
    if isinstance(attrs, dict):
        alt = str(attrs.get("alt", alt))
    elif isinstance(attrs, (list, tuple)):
        for item in attrs:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if str(k) == "alt":
                    alt = str(v)
                    break

    cache_dir = Path(".latex_fence_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    source_hash = hashlib.sha256((WRAPPER + "\0" + source).encode("utf-8")).hexdigest()
    svg_path = cache_dir / f"{source_hash}.svg"

    try:
        if svg_path.exists():
            svg = svg_path.read_bytes()
        else:
            svg = _compile_to_svg(source)
            svg_path.write_bytes(svg)
    except Exception as e:
        return (
            '<div class="latex-render-error">'
            "<strong>LaTeX render error</strong>"
            f"<pre>{html.escape(str(e))}</pre>"
            "</div>"
        )

    data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
    return f'<img class="{html.escape(css_class)}" src="{data_uri}" alt="{html.escape(alt)}" />'