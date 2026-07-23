from __future__ import annotations
import time 
import argparse
import copy
import xml.etree.ElementTree as ET
import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
import subprocess
import html

from gradientgrove.latex_fast_renderer import render_latex_fast

from pathlib import Path 

from textwrap import dedent ### !!! useful !!!

import re
import subprocess
import textwrap

from string import Template

# --------------------
# Initalize various ouput templates
# --------------------

DEFAULT_LATEX_ENV_MAP = {
    "frame":    {"name": "frame",    "collapsible": False, "style": "frame"},
    
    "exercise": {"name": "exercise", "collapsible": False, "style": "note"},
    "Exercise": {"name": "exercise", "collapsible": False, "style": "note"},
    
    "answer":   {"name": "answer",   "collapsible": True,  "style": "info"},
    "Answer":   {"name": "answer",   "collapsible": True,  "style": "info"},
    
    "abstract": {"name": "abstract", "collapsible": True,  "style": "abstract"},

    ## Hide environments and dump contents only
    ## Combine with putting the other in omit_envs to allow different text for article and presentation
    # "presentation": {"name": "presentation", "collapsible": True, "style": None},
    # "article":      {"name": "article",      "collapsible": True, "style": None},
    # 
    ## Display both    
    "presentation": {"name": "presentation", "collapsible": True, "style": "presentation"},
    "article":      {"name": "article",      "collapsible": True, "style": "article"},

 }

REVEALJS_TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$title</title>

  <link rel="stylesheet" href="$reveal_js_path/reveal.css">
  <link rel="stylesheet" href="$reveal_js_path/theme/$theme.css">

  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js-plugins@latest/customcontrols/style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js-plugins@latest/chalkboard/style.css">

  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js"></script>

<style>

                             
                             
  .reveal .slides section {
    text-align: left;
  }

  .reveal .slides section h1,
  .reveal .slides section h2,
  .reveal .slides section h3,
  .reveal .slides section h4,
  .reveal .slides section p,
  .reveal .slides section ul,
  .reveal .slides section ol,
  .reveal .slides section blockquote {
    text-align: left;
  }

    .reveal { 
        font-size: 18pt; 
    }

    .reveal pre code { 
        font-size: 15.75pt;
        line-height: 1.35;
        max-height: none;
        padding: 0.4em 0.4em;
    }

    .reveal h1 { font-size: 33pt; }
    .reveal h2 { font-size: 26.5pt; }
    .reveal h3 { font-size: 21.5pt; }
    .reveal h4 { font-size: 19pt; }

    .reveal .title-slide h1 { font-size: 36.25pt; }
    .reveal .section-slide h2 { font-size: 29.75pt; }

    /* scale images to match rescaled font size */
    .reveal img.latex-svg {
        zoom: 1.8;
    }
/* format frame titles like h2 without making them h2 */
    .reveal .frame-title {
      font-size: 26.5pt;
      font-weight: bold;
      margin: 0 0 0.4em 0;
      line-height: 1.2;
    }
                             
/* Prevent spaces from building up between containers */
.reveal section > * {
  margin-top: 0;
  margin-bottom: 0;
}

.reveal section > * + * {
  margin-top: 0.4em;
}

.reveal p {
  line-height: 1.25;
}
                                                          
</style>
                            
                            
  <style>
                                                          
    .reveal .title-slide,
    .reveal .section-slide {
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      height: 100%;
    }

    .reveal .theorem,
    .reveal .example,
    .reveal .answer,
    .reveal .note {
      margin: 1rem 0;
      padding: 0.75rem 1rem;
      border-left: 4px solid #888;
      background: rgba(127,127,127,0.08);
      text-align: left;
      border-radius: 0.25rem;
    }

    .reveal .theorem-title,
    .reveal .example-title,
    .reveal .answer-title,
    .reveal .note-title {
      font-weight: bold;
      margin-bottom: 0.5rem;
    }

    .reveal pre {
      width: 100%;
    }

    .reveal img {
      max-width: 100%;
      height: auto;
    }

    $extra_css
  </style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
      $slides_html
    </div>
  </div>

  <script src="$reveal_js_path/reveal.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js-menu@2.1.0/menu.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js-plugins@latest/customcontrols/plugin.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js-plugins@latest/chalkboard/plugin.js"></script>

  <script>
    Reveal.initialize({
      hash: true,
      controls: true,
      controlsTutorial: true,
      controlsLayout: "bottom-right",
      controlsBackArrows: "faded",
      progress: true,
      slideNumber: true,
      center: true,
      margin: 0,

                             
      transition: 'fade', // none/fade/slide/convex/concave/zoom
      transitionSpeed: 'fast', // default/fast/slow
                                                                                       
      // Prevent autoscaling to enforce default frame size
      minScale: 1,
      maxScale: 1,

      // The "normal" size of the presentation, aspect ratio will
      // be preserved when the presentation is scaled to fit different
      // resolutions. Can be specified using percentage units.
      //width: 1280,
      //height: 720,
      width: 1000,
      height: 700,
                                
        menu: {
        side: "left",
        width: "normal",
        numbers: true,
        titleSelector: "",
        hideMissingTitles: true,
        openButton: true,
        keyboard: true
        },

      customcontrols: {
        controls: [
          {
            icon: '<i class="fa fa-pen-square"></i>',
            title: 'Toggle chalkboard (B)',
            action: 'RevealChalkboard.toggleChalkboard();'
          },
          {
            icon: '<i class="fa fa-pen"></i>',
            title: 'Toggle notes canvas (C)',
            action: 'RevealChalkboard.toggleNotesCanvas();'
          }
        ]
      },

      chalkboard: {},

      plugins: [ RevealMenu, RevealCustomControls, RevealChalkboard ]
    });
  </script>
</body>
</html>
""")


HTML_HEADER_TEMPLATE = Template(r"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>$title</title>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js"></script>
    <style>
    $base_css_text
    </style>
    <style>
    $bootstrap_min_css_text
    </style>
    <style><!-- https://github.com/sindresorhus/github-markdown-css -->
    </style> 
    <style>
    /* Optional: center like GitHub / VS Code preview */
    .markdown-body {
    box-sizing: border-box;
    min-width: 200px;
    max-width: 980px;
    margin: 0 auto;
    padding: 32px;
    }</style>
</head>
<body class="markdown-body">
    $html_body
</body>
</html>
""")



BEAMER_HEADER_TEMPLATE = Template(r"""
\documentclass[ignorenonframetext]{beamer}
%\beamerdefaultoverlayspecification{<+->}
\setlength{\parskip}{0.1\baselineskip}
\usepackage{unicode-math}
\usepackage{listings}
\newcommand{\passthrough}[1]{#1}
\newcommand{\pandocbounded}[1]{#1}
\usepackage{tikz}
\usetikzlibrary{shapes.geometric} 
\usetikzlibrary{shadings}
\usetikzlibrary{arrows,calc,decorations.markings}
\usetikzlibrary{decorations.pathmorphing} 
\usetikzlibrary{positioning,fit}

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
\lstset{
language=Python,
basicstyle=\ttfamily\small,
tabsize=4,
columns=fullflexible,
upquote=true,
frame=single,
backgroundcolor=\color{white!95!black},
breaklines=true,
keepspaces=true,
showstringspaces=false,
}
\setlength{\parindent}{0pt}
\usepackage{longtable}
\usepackage{booktabs}
\newcommand{\tightlist}{}
\usetheme{Madrid}
\usepackage{multicol}
\AtBeginSection[]
{
\begin{frame}{Table of Contents}
    \footnotesize
%    \begin{multicols}{2}
    \tableofcontents[currentsection,hideallsubsections]
%    \end{multicols}
\end{frame}
}
\title{$title}
\author{$author}
\begin{document}
\begin{frame}
\maketitle
\end{frame}
""".strip())

ARTICLE_HEADER_TEMPLATE = Template(r"""
\documentclass{article}
\usepackage{beamerarticle}
\usepackage{tikz}
\usetikzlibrary{shapes.geometric} 
\usetikzlibrary{shadings}
\usetikzlibrary{arrows,calc,decorations.markings}
\usetikzlibrary{decorations.pathmorphing} 
\usetikzlibrary{positioning,fit}

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
\usepackage{unicode-math}
\usepackage{hyperref}
\usepackage[lastexercise]{exercise}
\renewcommand{\ExerciseHeader}{\textbf{\ExerciseName\ \ExerciseHeaderNB}.}
\newenvironment{exercise}{\begin{Exercise}}{\end{Exercise}}
\newenvironment{answer}{\begin{Answer}}{\end{Answer}}
\renewcommand{\AnswerHeader}{\textit{Solution (\ExerciseName~\ExerciseHeaderNB}). }
\AtEndEnvironment{Answer}{\dotfill$\square$}
\usepackage{listings}
\newcommand{\passthrough}[1]{#1}
\newcommand{\pandocbounded}[1]{#1}
\lstset{
language=Python,
basicstyle=\ttfamily\small,
tabsize=4,
columns=fullflexible,
upquote=true,
frame=single,
backgroundcolor=\color{white!95!black},
breaklines=true,
keepspaces=true,
showstringspaces=false,
}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6\baselineskip}
\usepackage{longtable}
\usepackage{booktabs}
\newcommand{\tightlist}{}
\usepackage[most]{tcolorbox}
\BeforeBeginEnvironment{frame}{\begin{tcolorbox}[enhanced,breakable,boxrule=0.6pt,colback=white,colframe=black,arc=6pt,left=6pt,right=6pt,top=6pt,bottom=6pt,]}
\AfterEndEnvironment{frame}{\end{tcolorbox}}
\title{$title}
\author{$author}
\begin{document}
\maketitle
\tableofcontents
""".strip())

# ------------------------------------------------------------
# Capture the FINAL markdown etree (after inline processing)
# ------------------------------------------------------------

class _CaptureTree(Treeprocessor):
    def __init__(self, md, sink):
        super().__init__(md)
        self.sink = sink

    def run(self, root):
        # Save a copy of the final tree so we can build our own AST from it.
        self.sink["root"] = copy.deepcopy(root)


class CaptureTreeExtension(Extension):
    def __init__(self, sink):
        super().__init__()
        self.sink = sink

    def extendMarkdown(self, md):
        proc = _CaptureTree(md, self.sink)
        # Low priority => run late, after other tree processors.
        md.treeprocessors.register(proc, "capture_tree", -1000)


# ------------------------------------------------------------
# Minimal AST wrapper
# ------------------------------------------------------------



class SyntaxTree:
    
    def __init__(self, 
        kind="element",
        name=None,
        tag=None,
        attrs=None,
        title=None,
        tail=None,
        text=None,
        children=None,
        etree=None,
    ):
        # Set default variables
        self.name = name          # logical name: p, ul, theorem, answer, ...
        self.tag = tag            # original etree tag: p, div, details, ...
        self.kind = kind          # document / element / admonition / details
        self.attrs = attrs or {}
        self.title = title
        self.tail = tail
        self.text= text
        self.children = children or []
        self.etree = etree        # original etree node (escape hatch / backing store)
        self.call_pandoc = False

    # @classmethod
    # def from_markdown(cls, text, *, extensions=None, extension_configs=None):
    #     sink = {}

    #     md = markdown.Markdown(
    #         extensions=(extensions or []) + [CaptureTreeExtension(sink)],
    #         extension_configs=extension_configs or {},
    #         output_format="xhtml",
    #     )

    #     md.convert(text)

    #     root = sink.get("root")
    #     if root is None:
    #         raise RuntimeError("Failed to capture final markdown etree.")

    #     return cls._from_etree(root, is_root=True)

    @classmethod
    def from_markdown(cls, text, *, extensions=None, extension_configs=None):
        md = markdown.Markdown(
            extensions=extensions or [],
            extension_configs=extension_configs or {},
            output_format="xhtml",
        )

        # Accept double escaped display math delimiters when they appear
        # on their own line (used before pymdownx.arithmatex). Avoid broad
        # replacements because LaTeX row breaks can include spacing, e.g.
        # ``\\[4pt]``, and must not be rewritten as ``\[4pt]``.
        text = re.sub(
            r"(?m)^([ \t]*)\\\\\[[ \t]*$",
            lambda match: match.group(1) + r"\[",
            text,
        )
        text = re.sub(
            r"(?m)^([ \t]*)\\\\\][ \t]*$",
            lambda match: match.group(1) + r"\]",
            text,
        )

        
        # print(text)
        print("Converting file to markdown")
        html_str = md.convert(text)
        print("Finished converting")
        # root = ET.fromstring(f"<div>{html_str}</div>")

        # print(html_str)

        wrapped_html = f"<div>{html_str}</div>"

        try:
            root = ET.fromstring(wrapped_html)
        except ET.ParseError as e:
            print("\nElementTree parse failed:")
            print(e)

            line_no, col_no = e.position

            lines = wrapped_html.splitlines()

            start = max(1, line_no - 5)
            end = min(len(lines), line_no + 5)

            print("\nNearby HTML:")
            for n in range(start, end + 1):
                line = lines[n - 1]
                print(f"{n}: {line}")
                if n == line_no:
                    print(" " * (len(str(n)) + 2 + col_no) + "^")

            raise

        progress = {
            "done": 0,
            "total": sum(1 for _ in root.iter()),
            "start": time.perf_counter(),
        }            
        tree = cls._from_etree(root, is_root=True, progress=progress)
        print()
        return tree
    
    # @classmethod
    # def from_markdown(cls, text, *, extensions=None, extension_configs=None):        
    #     # Build the SyntaxTree using the input text
    #     sink = {}

    #     md = markdown.Markdown(
    #         extensions=(extensions or []) + [CaptureTreeExtension(sink)],
    #         extension_configs=extension_configs or {},
    #         output_format="html",
    #     )

    #     # This runs the full markdown pipeline and produces the final etree.
    #     md.convert(text)

    #     root = sink.get("root")
    #     if root is None:
    #         raise RuntimeError("Failed to capture final markdown etree.")

    #     return SyntaxTree._from_etree(root, is_root=True)

    @staticmethod
    def _from_etree(el, is_root=False, progress=None):
        classes = el.attrib.get("class", "").split()

        # Progress par
        if progress is not None:
            progress["done"] += 1
            percent = progress["done"] / progress["total"]

            if progress["done"] % 25 == 0 or progress["done"] == progress["total"]:
                bar_width = 50
                filled = int(bar_width * percent)
                bar = "#" * filled + "-" * (bar_width - filled)

                elapsed = int(time.perf_counter() - progress["start"])
                remaining = int(elapsed * (1 / percent - 1)) if percent > 0 else 0

                print(
                    f"\r[{bar}]  Elapsed: {elapsed//60}:{elapsed % 60:02d}, "
                    f"Remaining: {remaining//60}:{remaining % 60:02d} ",
                    end="",
                    flush=True,
                )

        # Root wrapper
        if is_root:
            return SyntaxTree(
                name="document",
                tag=el.tag,
                kind="document",
                attrs=dict(el.attrib),
                text=el.text,
                tail=el.tail,
                children=[SyntaxTree._from_etree(child, progress=progress) for child in el],
                etree=el,
            )

        # !!! theorem / !!! note / !!!
        if el.tag == "div" and "admonition" in classes:
            env = next((c for c in classes if c != "admonition"), "admonition")

            children = list(el)
            title = None

            if children:
                first = children[0]
                if first.tag == "p" and first.attrib.get("class") == "admonition-title":
                    title = SyntaxTree._inner_text(first)
                    children = children[1:]

            return SyntaxTree(
                name=env,
                tag="div",
                kind="admonition",
                attrs={k: v for k, v in el.attrib.items() if k != "class"},
                title=title,
                text=el.text,
                tail=el.tail,
                children=[SyntaxTree._from_etree(child, progress=progress) for child in children],
                etree=el,
            )

        # ??? answer / ??? frame / ???
        if el.tag == "details":
            env = classes[0] if classes else "details"

            children = list(el)
            title = None

            if children:
                first = children[0]
                if first.tag == "summary":
                    title = SyntaxTree._inner_text(first)
                    children = children[1:]

            return SyntaxTree(
                name=env,
                tag="details",
                kind="details",
                attrs={k: v for k, v in el.attrib.items() if k != "class"},
                title=title,
                text=el.text,
                tail=el.tail,
                children=[SyntaxTree._from_etree(child, progress=progress) for child in children],
                etree=el,
            )

        # Ordinary node: p, ul, li, strong, em, code, ...
        return SyntaxTree(
            name=el.tag,
            tag=el.tag,
            kind="element",
            attrs=dict(el.attrib),
            text=el.text,
            tail=el.tail,
            children=[SyntaxTree._from_etree(child, progress=progress) for child in el],
            etree=el,
        )

    @staticmethod
    def _inner_text(el):
        return "".join(el.itertext()).strip()


    # From latex   #     

    # @staticmethod
    # def restore_placeholders(markdown_text: str, placeholder_map: dict[str, str]) -> str:
    #     """Replace standalone placeholder lines with their Markdown blocks."""
    #     for token, replacement in placeholder_map.items():
    #         pattern = rf"(?m)^[ \t]*{re.escape(token)}[ \t]*$"
    #         markdown_text = re.sub(pattern, lambda match: replacement, markdown_text)
    #     return markdown_text

    @staticmethod
    def restore_placeholders(markdown_text: str, placeholder_map: dict[str, str]) -> str:
        for token, replacement in placeholder_map.items():
            markdown_text = markdown_text.replace(
                token,
                "\n\n" + replacement.strip() + "\n\n"
            )
        return markdown_text

    @staticmethod
    def collect_block(lines, start_index, environment_name):
        """Collect a balanced \\begin{env} ... \\end{env} block."""
        block_lines = []
        depth = 0
        line_index = start_index

        begin_pat = re.compile(rf"\\begin\{{{re.escape(environment_name)}\}}")
        end_pat = re.compile(rf"\\end\{{{re.escape(environment_name)}\}}")

        while line_index < len(lines):
            current_line = lines[line_index]

            depth += len(begin_pat.findall(current_line))
            depth -= len(end_pat.findall(current_line))

            block_lines.append(current_line)
            line_index += 1

            if depth == 0:
                break

        return block_lines, line_index

    @staticmethod
    def collect_braced_argument(text: str):
        """A small helper that extracts the first balanced {...} argument from a string"""
        text = text.strip()

        if not text.startswith("{"):
            return None, text

        depth = 0
        chars = []

        for i, ch in enumerate(text[1:], start=1):
            if ch == "{":
                depth += 1
                chars.append(ch)
            elif ch == "}":
                if depth == 0:
                    return "".join(chars), text[i + 1:].strip()
                depth -= 1
                chars.append(ch)
            else:
                chars.append(ch)

        return None, text    
    
    @classmethod
    def convert_latex_block(cls, latex_text: str, start_line = 1, total_lines=None, start_time = time.perf_counter()) -> str:
        """Recursively convert one LaTeX chunk to Markdown."""
        env_map = DEFAULT_LATEX_ENV_MAP
        ignored_environments = {"multicols", "center", "flushleft", "flushright", "minipage"}
        code_environments = {"lstlisting", "verbatim", "code"}

        lines = latex_text.split("\n")
        protected_lines = []
        placeholder_map = {}
        placeholder_count = 0
        line_index = 0

        # Print progress bar
        if total_lines is None:
            total_lines = len(lines)
        bar_width = 50
        percent = min(1.0, start_line / total_lines)
        filled = int(bar_width * percent)
        bar = "#" * filled + "-" * (bar_width - filled)
        elapsed = int(time.perf_counter() - start_time)
        remaining = int(elapsed * (1 / percent - 1)) if percent > 0 else 0
        # print(f"\r[{bar}] {100 * percent:5.1f}%  line {start_line}/{total_lines}.  Elapsed: {elapsed//60}:{elapsed % 60:02d}, Remaining: {remaining//60}:{remaining % 60:02d}", end="", flush=True)
        print(f"\r[{bar}]  Elapsed: {elapsed//60}:{elapsed % 60:02d}, Remaining: {remaining//60}:{remaining % 60:02d} ", end="", flush=True)


        def new_placeholder():
            nonlocal placeholder_count
            placeholder_count += 1
            return f"OAIBLOCK{placeholder_count:04d}"

        while line_index < len(lines):

            current_line = lines[line_index]
            stripped_line = current_line.strip()
            # begin_match = re.match(r"\\begin\{([^}]+)\}(.*)", current_line)
            begin_match = re.match(r"^(\s*)\\begin\{([^}]+)\}(.*)", current_line)

            # print("converting", current_line[:30])

            if not begin_match:
                protected_lines.append(current_line)
                line_index += 1
                continue

            # environment_name, trailing_arguments = begin_match.groups()
            indent, environment_name, trailing_arguments = begin_match.groups()

            # if environment_name in ignored_environments:
            #     block_lines, line_index = cls.collect_block(lines, line_index, environment_name)
            #     protected_lines.extend(block_lines)
            #     continue

            if environment_name in ignored_environments:
                block_lines, line_index = cls.collect_block(lines, line_index, environment_name)

                body_latex = "\n".join(block_lines[1:-1])

                token = new_placeholder()
                placeholder_map[token] = cls.convert_latex_block(
                    body_latex,
                    start_line=start_line + line_index + 1,
                    total_lines=total_lines,
                    ).strip()
                protected_lines.append(token)
                continue

            if environment_name == "tikzpicture":
                block_lines, line_index = cls.collect_block(lines, line_index, environment_name)
                token = new_placeholder()
                tikz_block = "\n".join(block_lines).strip()
                placeholder_map[token] = f"```latex\n{tikz_block}\n```"
                protected_lines.append(token)
                continue

            if environment_name in code_environments:
                block_lines, line_index = cls.collect_block(lines, line_index, environment_name)

                begin_pos = block_lines[0].find(r"\begin")
                prefix = block_lines[0][:begin_pos].strip()

                if prefix:
                    protected_lines.append(prefix)

                token = new_placeholder()
                code_body = "\n".join(block_lines[1:-1]).strip("\n")
                placeholder_map[token] = f"```\n{code_body}\n```"
                protected_lines.append(token)
                continue



            if environment_name in env_map:
                block_lines, line_index = cls.collect_block(lines, line_index, environment_name)
                body_latex = "\n".join(block_lines[1:-1])
                body_markdown = cls.convert_latex_block(
                    body_latex,
                    start_line=start_line + line_index + 1,
                    total_lines=total_lines,
                    ).strip()

                env_info = env_map[environment_name]
                style = env_info.get("style")

                # style: None means: behave as if the outer environment was not there.
                if style is None:
                    token = new_placeholder()
                    placeholder_map[token] = body_markdown
                    protected_lines.append(token)
                    continue

                marker = "???" if env_map[environment_name]["collapsible"] else "!!!"
                # header = f'{marker} {env_map[environment_name]["name"]}'
                env_info = env_map[environment_name]
                block_name = env_info.get("name", environment_name)
                style = env_info.get("style")

                header = f"{marker} {block_name}"
                if style:
                    header += f" {style}"

                if environment_name == "frame":
                    trailing_arguments = re.sub(r"^\s*\[[^]]*\]\s*", "", trailing_arguments)
                    title, _ = cls.collect_braced_argument(trailing_arguments)

                    if title:
                        title = re.sub(r"\\lstinline\{([^{}]*)\}", r"`\1`", title)
                        header += f' "{title}"'
                            
                block_markdown = header
                if body_markdown:
                    block_markdown += "\n\n" + textwrap.indent(body_markdown, "    ")

                token = new_placeholder()
                placeholder_map[token] = block_markdown
                protected_lines.append(token)
                continue

            protected_lines.append(current_line)
            line_index += 1

        protected_text = "\n".join(protected_lines)

        # Strip out latex commands with on markdown analog
        strip_latex_commands = ["alert", "only", "onslide"]
        for command in strip_latex_commands:
            protected_text = re.sub(
                rf"\\{command}\{{([^{{}}]*)\}}",
                r"\1",
                protected_text,
            )

        # If this chunk is now just placeholders + blank lines, do not send it to Pandoc.
        # Pandoc may drop the placeholder lines, which makes reconstruction impossible.
        if placeholder_map and all(
            (not line.strip()) or (line.strip() in placeholder_map)
            for line in protected_lines
        ):
            parts = []
            for line in protected_lines:
                token = line.strip()
                if token in placeholder_map:
                    parts.append(placeholder_map[token])
            return "\n\n".join(parts)

        proc = subprocess.run(
            # ["pandoc", "-f", "latex", "-t", "markdown+tex_math_double_backslash+pipe_tables-simple_tables-multiline_tables-grid_tables"],
            ["pandoc", "-f", "latex", "-t", "markdown-tex_math_dollars+tex_math_single_backslash+pipe_tables-simple_tables-multiline_tables-grid_tables"],
            input=protected_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

        if proc.returncode != 0:
            print("Pandoc returncode:", proc.returncode)
            print("Pandoc stderr:")
            print(proc.stderr)

            print("\nNearby suspicious lines:")
            for i, line in enumerate(protected_text.splitlines(), start=1):
                if r"\begin" in line or r"\end" in line or "OAIBLOCK" in line:
                    print(f"{i}: {line}")

            raise RuntimeError("Pandoc conversion failed")

        result = proc.stdout

        ## Convert math delimiters to double escaped 
        # parts = re.split(r"(?<!\\)(\$\$?)", result)
        # out = []
        # in_math = None
        # for part in parts:
        #     if part in ("$", "$$"):
        #         if in_math is None:
        #             in_math = part
        #             out.append(r"\\[" if part == "$$" else r"\\(")
        #         elif part == in_math:
        #             out.append(r"\\]" if part == "$$" else r"\\)")
        #             in_math = None
        #         else:
        #             out.append(part)
        #     else:
        #         out.append(part)

        # result = "".join(out)

        # print("reconstructing  ", repr(result[:30]), len(result))
        # print("before reconstruction:", len(result))

        if placeholder_map:
            reconstructed_markdown = cls.restore_placeholders(result, placeholder_map)

            # Important fallback:
            # If Pandoc dropped all placeholder lines, reconstruct directly
            # from the pre-Pandoc protected lines.
            if not reconstructed_markdown.strip():
                parts = []
                for line in protected_lines:
                    token = line.strip()
                    if token in placeholder_map:
                        parts.append(placeholder_map[token])

                if parts:
                    reconstructed_markdown = "\n\n".join(parts)
                else:
                    reconstructed_markdown = result
        else:
            reconstructed_markdown = result


        # print("reconstructed to", repr(reconstructed_markdown[:30]), len(reconstructed_markdown), "\n", "-"*5)

        # print("after reconstruction:", len(reconstructed_markdown))

        # Clean up
        ## Ensure display math is separated from surrounding text. 
        # reconstructed_markdown = reconstructed_markdown.replace("\\[", "\n\n\\[")
        # reconstructed_markdown = reconstructed_markdown.replace("\\]", "\\]\n\n")
        # reconstructed_markdown = re.sub(r"\n{3,}", "\n\n", reconstructed_markdown)


        return reconstructed_markdown

    @classmethod
    def from_latex(
        cls,
        text,
        *,
        extensions=None,
        extension_configs=None,
    ):
        """Convert a restricted LaTeX source into normalized Markdown, then parse it."""

        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # print("length of text", len(text))
        
        # Drop full-line LaTeX comments 
        text = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("%")
        )
        # print("length of text after strip comments", len(text))

        if "\\begin{document}" in text:
            text = text.split("\\begin{document}", 1)[1]

        # print("length of text after remove headers", len(text))

        if "\\end{document}" in text:
            text = text.rsplit("\\end{document}", 1)[0]

        # print("length of text after remove end of doc", len(text))

        markdown_text = cls.convert_latex_block(text).strip() + "\n"

        ## Ensure display math is separated from surrounding text. 
        out = ""

        for line in markdown_text.splitlines():
            indent = line[:len(line) - len(line.lstrip())]

            def reindent(fragment):
                return textwrap.indent(fragment.strip(), indent)

            if "\\[" in line:
                before, line = line.split("\\[", 1)
                out += (reindent(before) + "\n") if before.strip() else ""
                out += "\n" + indent + r"\[" + "\n"

            if "\\]" in line:
                before, after = line.split("\\]", 1)
                out += (reindent(before) + "\n") if before.strip() else ""
                out += indent + r"\]" + "\n\n"
                out += (reindent(after) + "\n") if after.strip() else ""
                
            else:
                out += reindent(line) + "\n"

        markdown_text = re.sub(r"\n{3,}", "\n\n", out)

        # print("length of text after block conversion", len(markdown_text))

        tree = cls.from_markdown(
            markdown_text,
            extensions=extensions,
            extension_configs=extension_configs,
        )
        tree.markdown_text = markdown_text

        

        return tree


    # ----------------------------
    # Tree traversal / transforms
    # ----------------------------
    def validate_structure(self, in_document_root=True):
        heading_names = {"h1", "h2", "h3", "h4", "h5", "h6"}

        if self.name in heading_names and not in_document_root:
            raise ValueError(
                f"Heading {self.name!r} must be top-level in the document"
            )

        if self.name == "frame":
            for child in self.children:
                if child.name in heading_names:
                    raise ValueError(
                        "frame contents must not contain headings; use the frame title instead"
                    )

        child_top_level = (self.kind == "document")
        for child in self.children:
            child.validate_structure(in_document_root=child_top_level)
            
    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def prune_envs(self, omit_envs):
        omit_envs = set(omit_envs or [])
        kept = []
        for child in self.children:
            child.prune_envs(omit_envs)
            if child.name not in omit_envs:
                kept.append(child)
        self.children = kept
        
    def number_envs(self, labels):
        """
        labels example:
            {
                "theorem": "Theorem",
                "example": "Example",
                "answer": "Answer",
            }
        """
        counters = {env: 0 for env in labels}

        for node in self.walk():
            if node.name not in labels:
                continue

            counters[node.name] += 1
            default_titles = {
                None,
                "",
                node.name,
                node.name.capitalize(),
                labels[node.name],
            }

            if node.title in default_titles:
                node.title = f"{labels[node.name]} {counters[node.name]}"

    def number_sections(self):
        """
        Number h1, h2, ..., h6 by prefixing their text.
        """
        counters = [0, 0, 0, 0, 0, 0]

        for node in self.walk():
            if node.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                continue

            level = int(node.name[1])  # 1..6
            counters[level - 1] += 1

            for i in range(level, 6):
                counters[i] = 0

            prefix = ".".join(str(n) for n in counters[:level] if n > 0)

            if node.text:
                node.text = f"{prefix} {node.text}"
            else:
                node.text = prefix

    # def pretty_print(self, indent=0):
        # """Print the current AST in a human readable form for debugging"""
        # pad = "  " * indent
        # title = f' title="{self.title}"' if self.title is not None else ""
        # print(f"{pad}{self.name}  [kind={self.kind}, tag={self.tag}]{title}")
        # for child in self.children:
        #     child.pretty_print(indent + 1)
    def pretty_print(self, indent=0):
        """Print the AST as XML."""

        def build(node):
            attrs = {
                "name": str(node.name),
                "kind": str(node.kind),
                "tag": str(node.tag),
            }

            if node.title is not None:
                attrs["title"] = str(node.title)

            # Include original HTML attrs, such as href, class, id.
            for key, value in sorted((node.attrs or {}).items()):
                attrs[f"attr_{key}"] = str(value)

            el = ET.Element("node", attrs)

            for child in node.children:
                el.append(build(child))

            return el

        root = build(self)
        ET.indent(root, space="  ")
        print(ET.tostring(root, encoding="unicode"))
    # --------------------------------------------------------
    # Outputting the Syntax Tree to different formats
    # --------------------------------------------------------

    # ----------------------------
    # Rendering back to etree / HTML
    # ----------------------------

    def to_etree(self, transparent_envs=None):
        """Recursively rebuild the html etree based on the current AST after mutations (like numbering and removal) """
        transparent_envs = set(transparent_envs or [])

        if self.name == "page":
            el = ET.Element("section", {"class": "gg-page"})
            content = ET.SubElement(el, "div", {"class": "gg-page-content"})
            el.tail = self.tail
            for child in self.children:
                content.append(child.to_etree(transparent_envs))
            return el

        if self.name == "newpage":
            el = ET.Element("div", {"class": "gg-newpage"})
            el.tail = self.tail
            return el

        if self.name == "vfill":
            el = ET.Element("div", {"class": "gg-vfill"})
            el.tail = self.tail
            return el

        if self.name == "vspace":
            amount = self.title
            if amount in {None, "", "vspace", "Vspace"}:
                amount = "1in"
            el = ET.Element("div", {"class": "gg-vspace", "style": f"height: {amount}"})
            el.tail = self.tail
            return el

        if self.kind in {"admonition", "details"} and self.name in transparent_envs:
            el = ET.Element("div", {"class": "gg-transparent-env"})
            el.text = self.text
            el.tail = self.tail
            for child in self.children:
                el.append(child.to_etree(transparent_envs))
            return el

        if self.kind == "admonition":
            attrs = dict(self.attrs)
            attrs["class"] = f"admonition {self.name}"
            el = ET.Element("div", attrs)
            el.text = self.text
            el.tail = self.tail

            if self.title is not None:
                title_el = ET.SubElement(el, "p", {"class": "admonition-title"})
                title_el.text = self.title

            for child in self.children:
                el.append(child.to_etree(transparent_envs))

            return el

        if self.kind == "details":
            attrs = dict(self.attrs)
            if self.name != "details":
                attrs["class"] = self.name
            el = ET.Element("details", attrs)
            el.text = self.text
            el.tail = self.tail

            if self.title is not None:
                summary = ET.SubElement(el, "summary")
                summary.text = self.title

            for child in self.children:
                el.append(child.to_etree(transparent_envs))

            return el

        # ordinary element
        el = ET.Element(self.tag, self.attrs)
        el.text = self.text
        el.tail = self.tail
        for child in self.children:
            el.append(child.to_etree(transparent_envs))
        return el

    def to_html(self, omit_envs=None, title="Document", transparent_envs=None):
        if omit_envs is None:
            omit_envs = []

        omit_envs = set(omit_envs or [])

        if self.kind == "document":
            html_body = "".join(
                ET.tostring(
                    child.to_etree(transparent_envs),
                    encoding="unicode",
                    method="html",
                )
                for child in self.children
                if child.name not in omit_envs
            )

            from pathlib import Path
            SCRIPT_DIR = Path(__file__).resolve().parent
            # with (SCRIPT_DIR / "base.css").open() as f:
            #     base_css_text = f.read()
            # with (SCRIPT_DIR / "bootstrap.min.css").open() as f:
            #     bootstrap_min_css_text = f.read()
            with (SCRIPT_DIR / "gradientgrove.css").open() as f:
                base_css_text = f.read()
                bootstrap_min_css_text = f.read()

            return HTML_HEADER_TEMPLATE.safe_substitute(locals())

        return ET.tostring(
            self.to_etree(transparent_envs),
            encoding="unicode",
            method="html",
        )

    # ----------
    # Output revealjs slides
    # ----------

    def _render_reveal_content(self, transparent_envs=None):
        """Recursively interpret SyntaxTree for revealjs"""

        transparent_envs = set(transparent_envs or [])

        if self.name in transparent_envs:
            return "".join(
                child._render_reveal_content(transparent_envs)
                for child in self.children
            )

        if self.name == "frame":
            return "".join(child._render_reveal_content(transparent_envs) for child in self.children)

        if self.name == "pause":
            body = html.escape(self.text or "")
            body += "".join(
                child._render_reveal_content(transparent_envs) + html.escape(child.tail or "")
                for child in self.children
            )
            return f'<div class="fragment">{body}</div>'

        if self.kind in {"admonition", "details"}:
            title = (
                f'<div class="{self.name}-title">{html.escape(self.title)}</div>'
                if self.title else ""
            )
            body = html.escape(self.text or "")
            body += "".join(
                child._render_reveal_content(transparent_envs) + html.escape(child.tail or "")
                for child in self.children
            )
            return f'<div class="{self.name}">{title}{body}</div>'

        # Ordinary HTML node: serialize attrs directly here.
        attrs = "".join(
            f' {k}="{html.escape(str(v), quote=True)}"'
            for k, v in self.attrs.items()
        )
        body = html.escape(self.text or "")
        body += "".join(
            child._render_reveal_content(transparent_envs) + html.escape(child.tail or "")
            for child in self.children
        )
        return f"<{self.tag}{attrs}>{body}</{self.tag}>"
    
    def to_revealjs(
        self,
        *,
        title="Slides",
        # theme="black",
        # theme="white",
        # theme="beige",
        # theme="sky",
        theme="serif",
        extra_css="",
        reveal_js_path="https://cdn.jsdelivr.net/npm/reveal.js@5/dist",
        omit_envs = None,
        transparent_envs=None,
    ):
    

        omit_envs = set(omit_envs or [])

        if self.kind != "document":
            raise ValueError("to_revealjs() must be called on the document root")

        self.validate_structure()

        slides = []

        for node in self.children:
            
            if node.name in omit_envs:
                continue

            if node.name == "h1":
                heading = html.escape(node.text or "")
                heading += "".join(child._render_reveal_content(transparent_envs) for child in node.children)
                slides.append(
                    f'<section class="title-slide" data-menu-title="{html.escape(heading)}">'
                    f'<h1>{heading}</h1></section>'
                )
            elif node.name == "h2":
                heading = html.escape(node.text or "")
                heading += "".join(child._render_reveal_content(transparent_envs) for child in node.children)
                slides.append(
                    f'<section class="section-slide" data-menu-title="{html.escape(heading)}">'
                    f'<h2>{heading}</h2></section>'
                )
            elif node.name == "frame":
                slide_title = (
                    f'<div class="frame-title">{html.escape(node.title)}</div>\n'
                    if node.title else ""
                )
                body = "".join(child._render_reveal_content(transparent_envs) for child in node.children)
                slides.append(f"<section>\n{slide_title}{body}\n</section>")
                
        slides_html = "\n".join(slides)
        return REVEALJS_TEMPLATE.safe_substitute(locals())
    
    def mark_call_pandoc(self):
        """
        Mark maximal ordinary subtrees for Pandoc conversion.

        Custom containers such as the document root, admonitions, and details are
        rendered manually, so they are not themselves handed to Pandoc. Their
        adjacent Pandoc-callable children are grouped into synthetic pandoc_block
        nodes to reduce the number of Pandoc subprocess calls.
        """
        if self.kind in {"document", "admonition", "details"}:
            self.call_pandoc = False

            new_children = []
            batch = []
            END_OF_CHILDREN = None

            for child in list(self.children) + [END_OF_CHILDREN]:
                if child is not END_OF_CHILDREN:
                    child.mark_call_pandoc()

                if child is not END_OF_CHILDREN and child.call_pandoc:
                    batch.append(child)
                    continue

                # Non-Pandoc child or end sentinel: close current Pandoc batch.
                if batch:
                    block = SyntaxTree(
                        kind="element",
                        name="pandoc_block",
                        tag="div",
                        children=batch,
                    )
                    block.call_pandoc = True
                    new_children.append(block)
                    batch = []

                if child is not END_OF_CHILDREN:
                    new_children.append(child)

            self.children = new_children
            return False

        child_results = [child.mark_call_pandoc() for child in self.children]

        self.call_pandoc = all(child_results)
        return self.call_pandoc
    # def mark_call_pandoc(self):
    #     """
    #     Mark maximal ordinary subtrees that can be handed to Pandoc.

    #     Do not mark document root or custom environments.
    #     """
    #     if self.kind in {"document", "admonition", "details"}:
    #         self.call_pandoc = False
    #         for child in self.children:
    #             child.mark_call_pandoc()
    #         return False
    #     child_results = [child.mark_call_pandoc() for child in self.children]

    #     if all(child_results):
    #         self.call_pandoc = True
    #         return True
        
    #     else:
    #         self.call_pandoc = False
    #         return False
            
                
    # def mark_call_pandoc(self):
    #     """
    #     Recursively traverse the SyntaxTree, marking which nodes can be handed off to Pandoc (no admonitions as descendents)
    #     """
    #     self.call_pandoc = True

    #     for child in self.children:
    #         child.mark_call_pandoc()

    #         if child.kind in {"admonition", "details"} or not child.call_pandoc:
    #             self.call_pandoc = False
    
    def _render_latex(self, omit_envs=None, transparent_envs=None, progress=None):
        """
        Recursively traverse the Syntax tree, interpreting admonitions explicitly, and handing off everything else to pandoc
        """

        omit_envs = set(omit_envs or [])
        transparent_envs = set(transparent_envs or [])

        # progress bar
        if progress is not None:
            progress["done"] += 1
            percent = progress["done"] / progress["total"]

            if progress["done"] % 25 == 0 or progress["done"] == progress["total"]:
                bar_width = 50
                filled = int(bar_width * percent)
                bar = "#" * filled + "-" * (bar_width - filled)

                elapsed = int(time.perf_counter() - progress["start"])
                remaining = int(elapsed * (1 / percent - 1)) if percent > 0 else 0

                print(
                    f"\r[{bar}]  Elapsed: {elapsed//60}:{elapsed % 60:02d}, "
                    f"Remaining: {remaining//60}:{remaining % 60:02d} ",
                    end="",
                    flush=True,
                )

        if self.kind == "document":
            return "".join(child._render_latex(omit_envs, transparent_envs, progress=progress) for child in self.children)

        if self.kind in {"admonition", "details"}:
            env = self.name

            if env in omit_envs:
                return ""

            if env in transparent_envs:
                return "".join(child._render_latex(omit_envs, transparent_envs, progress=progress) for child in self.children)

            if env == "pause":
                body = "".join(child._render_latex(omit_envs, transparent_envs, progress=progress) for child in self.children)
                return "\\pause\n" + body

            body = "".join(child._render_latex(omit_envs, transparent_envs, progress=progress) for child in self.children)

            if env == "frame":
                title = f"{{{self.title}}}" if self.title else ""
                return f"\\begin{{frame}}[fragile]{title}\n{body}\\end{{frame}}\n"

            if self.title:
                return f"\\begin{{{env}}}[{self.title}]\n{body}\\end{{{env}}}\n"

            if env == "latexraw":
                # dump contents of latex blocks in directly
                pre = self.children[0] if self.children else None
                code = pre.children[0] if pre and pre.children else None
                return (code.text or "") + "\n" if code else ""    

            return f"\\begin{{{env}}}\n{body}\\end{{{env}}}\n" 

        if self.call_pandoc:
            input_html = ET.tostring(self.to_etree(), encoding="unicode", method="html")
            print(f"\nPANDOC node={self.name} kind={self.kind} chars={len(input_html):,}", flush=True)
            return subprocess.run(
                ["pandoc", "-f", "html+tex_math_single_backslash", "-t", "latex", "--listings"],
                # input=self.to_html(),
                input=ET.tostring(self.to_etree(), encoding="unicode", method="html"),
                text=True,
                capture_output=True,
                check=True,
            ).stdout
        
        return "".join(child._render_latex(omit_envs, transparent_envs, progress=progress) for child in self.children)

    def to_latex(
        self,
        *,
        title="Document",
        author="Stephen Flood",
        beamer=False,
        omit_envs=None,
        transparent_envs=None,
        fast=True,
    ):
        """Generate a LaTeX document output."""

        if fast:
            body = render_latex_fast(self, omit_envs=omit_envs, transparent_envs=transparent_envs)
        else:
            print("Pre-process to identify pandoc nodes.")
            self.mark_call_pandoc()

            progress = {
                "done": 0,
                "total": sum(1 for _ in self.walk()),
                "start": time.perf_counter(),
            }

            body = self._render_latex(omit_envs, transparent_envs, progress=progress)

        if beamer:
            template = BEAMER_HEADER_TEMPLATE
        else:
            template = ARTICLE_HEADER_TEMPLATE

        header = template.safe_substitute(locals())
        return header + "\n" + body + "\n\\end{document}\n"

    # def to_latex(
    #     self,
    #     *,
    #     title="Document",
    #     author="Stephen Flood",
    #     beamer=False,
    #     omit_envs=None,
    # ):
    #     """Generate a Latex Document Output"""

    #     print("Pre-process to identify pandoc nodes.")
    #     self.mark_call_pandoc()

    #     progress = {
    #         "done": 0,
    #         "total": sum(1 for _ in self.walk()),
    #         "start": time.perf_counter(),
    #     }

    #     body = self._render_latex(omit_envs, transparent_envs, progress=progress)

    #     if beamer:
    #         template = BEAMER_HEADER_TEMPLATE 
    #     else:
    #         template = ARTICLE_HEADER_TEMPLATE

    #     header = template.safe_substitute(locals())
    #     return header + "\n" + body + "\n\\end{document}\n"


class DocumentTree:

    def __init__(self, text, *, extensions=None, extension_configs=None,
            kind="element",
            name=None,
            tag=None,
            attrs=None,
            title=None,
            tail=None,
            children=None,
            etree=None,):

        tree = SyntaxTree(kind, name, tag, attrs, title, tail, children, etree)

        md = markdown.Markdown(
            extensions=extensions or [],
            extension_configs=extension_configs or {},
            output_format="xhtml",
        )

        html_str = md.convert(text)
        root = ET.fromstring(f"<div>{html_str}</div>")

        self.children = SyntaxTree._from_etree(root, is_root=False)
        self.kind = "document"

    # def __init__ (self, text, *, extensions=None, extension_configs=None,
    #         kind="element",
    #         name=None,
    #         tag=None,
    #         attrs=None,
    #         title=None,
    #         tail=None,
    #         children=None,
    #         etree=None,):

    #     tree = SyntaxTree(kind,name,tag,attrs,title,tail,children,etree)
            
    #     # Build the SyntaxTree using the input text
    #     sink = {}

    #     md = markdown.Markdown(
    #         extensions=(extensions or []) + [CaptureTreeExtension(sink)],
    #         extension_configs=extension_configs or {},
    #         output_format="html",
    #     )

    #     # This runs the full markdown pipeline and produces the final etree.
    #     md.convert(text)

    #     root = sink.get("root")
    #     if root is None:
    #         raise RuntimeError("Failed to capture final markdown etree.")

    #     self.children= SyntaxTree._from_etree(root, is_root=False)
    
    #     self.kind = "document"



def dump_modes_to_environments(text: str) -> str:
    """One-off fix for files that use beamerarticle \\mode<...>{...} blocks.

    Converts:

        \\mode<article>{...}
        \\mode<presentation>{...}

    into:

        \\begin{article}
        ...
        \\end{article}

        \\begin{presentation}
        ...
        \\end{presentation}

    Handles nested braces inside the mode body, such as \\textbf{...} and
    \\emph{...}.
    """

    def collect_balanced_brace_argument(s: str):
        """Return body and consumed length for the first balanced {...} argument."""

        leading_ws = len(s) - len(s.lstrip())
        s2 = s.lstrip()

        if not s2.startswith("{"):
            return None, 0

        depth = 0
        chars = []

        for j, ch in enumerate(s2[1:], start=1):
            if ch == "{":
                depth += 1
                chars.append(ch)
            elif ch == "}":
                if depth == 0:
                    consumed = leading_ws + j + 1
                    return "".join(chars), consumed
                depth -= 1
                chars.append(ch)
            else:
                chars.append(ch)

        return None, 0

    out = []
    i = 0
    pattern = re.compile(r"\\mode<([^>]+)>")

    while True:
        match = pattern.search(text, i)

        if not match:
            out.append(text[i:])
            break

        mode = match.group(1)

        out.append(text[i:match.start()])

        body, consumed = collect_balanced_brace_argument(text[match.end():])

        if body is None:
            # Leave malformed \mode<...> text untouched.
            out.append(text[match.start():match.end()])
            i = match.end()
            continue

        out.append(
            f"\\begin{{{mode}}}\n"
            f"{body.strip()}\n"
            f"\\end{{{mode}}}\n"
        )

        i = match.end() + consumed

    return "".join(out)



def latex_to_markdown_main(argv: list[str] | None = None) -> int:
    """Run the LaTeX-to-Markdown command-line interface."""
    parser = argparse.ArgumentParser(
        prog="gradientgrove-latex-to-markdown",
        description="Convert a LaTeX file to Markdown.",
    )
    parser.add_argument("input", type=Path, help="LaTeX input file to convert.")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Markdown output file. Defaults to the input path with a .md suffix.",
    )
    parser.add_argument(
        "--no-dump-modes",
        action="store_true",
        help=r"Do not convert Beamer \mode<...>{...} blocks into environments before parsing.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output is not None else input_path.with_suffix(".md")

    contents = input_path.read_text(encoding="utf-8")
    if not args.no_dump_modes:
        contents = dump_modes_to_environments(contents)

    tree = SyntaxTree.from_latex(
        contents,
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
            "admonition",
            "attr_list",
            "pymdownx.details",
            "pymdownx.superfences",
        ],
    )
    output_path.write_text(tree.markdown_text, encoding="utf-8")
    print(output_path)
    return 0

### TESTING 
if __name__ == "__main__":
    raise SystemExit(latex_to_markdown_main())


#     # file_text = dedent("""
#     #     # Section One

#     #     Some **bold** text and some *italic* text.

#     #     !!! theorem "Pythagorean Theorem"

#     #         If \\(a^2+b^2=c^2\\), then the triangle is right.

#     #     ??? answer "Why?"

#     #         Because this is a collapsible answer block.

#     #     ## Subsection

#     #     - First item
#     #     - Second item with `code`

#     #     # Now have some slides

#     #     !!! exercise 
            
#     #         An Exercise


#     #     !!! exercise note
            
#     #         Another one!

#     #     !!! example

#     #         This example has the default title.

#     #     !!! frame "A title!"

#     #         Some **bold** text.

#     #     !!! frame "Have more *TITLES*"

#     #         !!! theorem "Fact"

#     #             Inside a slide.

#     #         !!! pause

#     #             - first reveal
#     #             - then continue
#     # """).strip()

#     markdown_file = Path("./test_markdown.md")

#     # time1 = time.perf_counter()
#     # # Example usage:
#     # #SyntaxTree.from_markdown(
#     tree = SyntaxTree.from_markdown(
#         markdown_file,
#         extensions=[
#             "tables",
#             "fenced_code",
#             "toc",
#             "sane_lists",
#             "admonition",
#             "attr_list",
#             "pymdownx.details",
#             "pymdownx.superfences",
#         ],
#         # extension_configs={
#         #     "pymdownx.superfences": {
#         #         "custom_fences": [
#         #             {
#         #                 "name": "latex",
#         #                 "class": "latex-svg",
#         #                 "format": latex_fence.latex_svg_fence,
#         #             },
#         #             {
#         #                 "name": "tikz",
#         #                 "class": "latex-svg",
#         #                 "format": latex_fence.latex_svg_fence,
#         #             },
#         #         ]
#         #     }
#         # },
#     )
#     tree.pretty_print()

#     # tree.prune_envs({"draft"})
#     # tree.number_envs({
#     #     "exercise" : "Exercise",
#     #     "theorem": "Theorem",
#     #     "example": "Example",
#     #     "answer": "Answer",
#     # })
#     # tree.number_sections()
#     # html_str = tree.to_html()

#     # print("-"*20 + "Doctree" + "-"*20)
#     # tree.pretty_print()

#     # print("-"*20 + "HTML" + "-"*20)
#     # print(html_str)

#     # print("-"*20 + "File Outputs" + "-"*20)
#     # tree.pretty_print()

#     # time2 = time.perf_counter()


#     # # tree = SyntaxTree(
#     # #     file_text,
#     # #     extensions=[
#     # #         "tables",
#     # #         "fenced_code",
#     # #         "toc",
#     # #         "sane_lists",
#     # #         "admonition",
#     # #         "attr_list",
#     # #         "pymdownx.details",
#     # #         "pymdownx.superfences",
#     # #     ],
#     # #     extension_configs={},
#     # # )

#     # html_str = tree.to_revealjs(title="Test Slides")


#     # time3 = time.perf_counter()



#     # Path("test_slides.html").write_text(html_str, encoding="utf-8")
#     # print("Wrote test_slides.html")

#     ## Test OUTPUT of latex
#     #
#     # latex = tree.to_latex(
#     #     title="My Test Document",
#     #     author="Stephen Flood",
#     #     beamer=False,          # False for article mode
#     #     omit_envs={"draft"},  # optional
#     # )
#     # 
#     # Path("test.tex").write_text(latex)
#     # print("Wrote test.tex")


#     time4 = time.perf_counter()


#     # print( time2-time1, time3-time2, time4-time3)
    
    ## Test INPUT of latex

    tex_file = Path("./Flood-Programing_and_Computer_Algebra.tex")
    # tex_file = Path("./testfile.tex")
    # tex_file = Path("./Quick-Intro-to-Neural-Networks.tex")

    contents = tex_file.read_text(encoding="utf-8")
    contents = dump_modes_to_environments(contents)
    md_file = tex_file.with_suffix(".md")

    tree = SyntaxTree.from_latex(
        contents,
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
            "admonition",
            "pymdownx.arithmatex",
            "pymdownx.details",
            "pymdownx.superfences",
            "attr_list",
        ],
        extension_configs={
            "pymdownx.arithmatex": {
                "generic": True,
            },
        }
        # extension_configs={
        #     "pymdownx.superfences": {
        #         "custom_fences": [
        #             {
        #                 "name": "latex",
        #                 "class": "latex-svg",
        #                 "format": latex_fence.latex_svg_fence,
        #             },
        #             {
        #                 "name": "tikz",
        #                 "class": "latex-svg",
        #                 "format": latex_fence.latex_svg_fence,
        #             },
        #         ]
        #     }
        # },
    )

    print(md_file)

    md_file.write_text(tree.markdown_text, encoding="utf-8")