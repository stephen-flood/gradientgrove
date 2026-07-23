from string import Template
import subprocess
import re
import xml.etree.ElementTree as ET


LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


# Each rule is (template, mode), where mode is:
#   tex  -> recursively render children and escape ordinary text
#   raw  -> use raw text, mainly for code-like blocks or explicit LaTeX passthrough
#   none -> emit only the template
LATEX_RULES = {
    "p":          (Template("\n\n$body\n\n"), "tex"),
    "blockquote": (Template("\\begin{quote}\n$body\\end{quote}\n\n"), "tex"),

    "strong":     (Template("\\textbf{$body}"), "tex"),
    "b":          (Template("\\textbf{$body}"), "tex"),
    "em":         (Template("\\emph{$body}"), "tex"),
    "i":          (Template("\\emph{$body}"), "tex"),
    "code":       (Template("\\lstinline`$raw`"), "raw"),
    "a":          (Template("\\href{$href}{$body}"), "tex"),

    # Start list environments with a newline so nested lists do not attach to prior item text.
    "ul":         (Template("\n\\begin{itemize}\n$body\\end{itemize}\n\n"), "tex"),
    "ol":         (Template("\n\\begin{enumerate}\n$body\\end{enumerate}\n\n"), "tex"),
    "li":         (Template("\\item $body\n"), "tex"),

    "span":       (Template("$body"), "tex"),
    "div":        (Template("$body"), "tex"),
    "br":         (Template("\\\\"), "none"),
    "hr":         (Template("\n\\hrule\n"), "none"),

    "pre":        (Template("\\begin{lstlisting}\n$raw\n\\end{lstlisting}\n\n"), "raw"),
    "latexraw":   (Template("$raw\n"), "raw"),
    "pause":      (Template("\\pause\n$body"), "tex"),

    "frame":        (Template("\\begin{frame}[fragile]$title_braced\n$body\\end{frame}\n"), "tex"),
    "article":      (Template("\\mode<article>{$raw}\n"), "raw"),
    "presentation": (Template("\\mode<presentation>{$raw}\n"), "raw"),
}

LATEX_TITLE_ENVS = {
    "theorem",
    "lemma",
    "proposition",
    "corollary",
    "definition",
    "example",
    "remark",
}

LATEX_UNTITLED_ENVS = {
    "exercise",
    "answer",
    "abstract",
    "proof",
}

for env in LATEX_TITLE_ENVS:
    LATEX_RULES[env] = (
        Template(f"\\begin{{{env}}}$title_opt\n$body\\end{{{env}}}\n"),
        "tex",
    )

for env in LATEX_UNTITLED_ENVS:
    LATEX_RULES[env] = (
        Template(f"\\begin{{{env}}}\n$body\\end{{{env}}}\n"),
        "tex",
    )

for tag, command in {
    "h1": "section",
    "h2": "subsection",
    "h3": "subsubsection",
    "h4": "paragraph",
    "h5": "subparagraph",
    "h6": "subparagraph",
}.items():
    LATEX_RULES[tag] = (
        Template(f"\n\n\\{command}{{$body}}\n\n"),
        "tex",
    )


def render_latex_fast(root, omit_envs=None, transparent_envs=None):
    omit_envs = set(omit_envs or [])
    transparent_envs = set(transparent_envs or [])

    def raw(node):
        out = [node.text or ""]
        for child in node.children:
            out.append(raw(child))
            out.append(child.tail or "")
        return "".join(out)

    def body(node):
        out = ["".join(LATEX_ESCAPES.get(c, c) for c in (node.text or ""))]
        for child in node.children:
            out.append(render(child))
            out.append("".join(LATEX_ESCAPES.get(c, c) for c in (child.tail or "")))
        return "".join(out)

    def render(node):
        if node.name in omit_envs:
            return ""

        if node.kind in {"admonition", "details"} and node.name in transparent_envs:
            return body(node)

        if node.kind == "document":
            return "".join(render(child) for child in node.children)

        key = node.name if node.kind in {"admonition", "details"} else (node.tag or node.name)

        # Math produced by pymdownx.arithmatex is already LaTeX-like content.
        # Display math is usually div.arithmatex; inline math is usually span.arithmatex.
        if "arithmatex" in node.attrs.get("class", "").split():
            math = raw(node).strip("\n")
            return f"\n\n{math}\n\n" if key == "div" else math

        if key not in LATEX_RULES:
            if node.kind in {"admonition", "details"}:
                # escaped_title = "".join(
                #     LATEX_ESCAPES.get(c, c) for c in (node.title or "")
                # ).replace("\n", " ")
                # title_opt = f"[{escaped_title}]" if node.title else ""
                # return f"\\begin{{{node.name}}}{title_opt}\n{body(node)}\\end{{{node.name}}}\n"
                raw_title = (node.title or "").strip()
                default_title = raw_title.lower() == node.name.lower()

                escaped_title = "".join(
                    LATEX_ESCAPES.get(c, c) for c in raw_title
                ).replace("\n", " ")

                title_opt = f"[{escaped_title}]" if raw_title and not default_title else ""
                return f"\\begin{{{node.name}}}{title_opt}\n{body(node)}\\end{{{node.name}}}\n"
            
            # Unknown ordinary HTML, including tables, goes to Pandoc.
            input_html = ET.tostring(node.to_etree(), encoding="unicode", method="html")
            proc = subprocess.run(
                ["pandoc", "-f", "html+tex_math_single_backslash", "-t", "latex", "--listings"],
                input=input_html,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            if proc.returncode:
                raise RuntimeError(proc.stderr)
            return proc.stdout

        template, mode = LATEX_RULES[key]
        tex_body = body(node) if mode == "tex" else ""
        raw_body = raw(node).strip("\n") if mode == "raw" else ""

        escaped_href = "".join(
            LATEX_ESCAPES.get(c, c) for c in (node.attrs.get("href", "") or "")
        ).replace("\n", " ")
        # escaped_title = "".join(
        #     LATEX_ESCAPES.get(c, c) for c in (node.title or "")
        # ).replace("\n", " ")
        raw_title = (node.title or "").strip()
        default_title = raw_title.lower() == key.lower()

        escaped_title = "".join(
            LATEX_ESCAPES.get(c, c) for c in raw_title
        ).replace("\n", " ")

        return template.safe_substitute({
            "body": tex_body,
            "body_stripped": tex_body.strip(),
            "raw": raw_body,
            "href": escaped_href,
            "title": escaped_title,
            # "title_opt": f"[{escaped_title}]" if node.title else "",
            # "title_braced": f"{{{escaped_title}}}" if node.title else "",
            "title_opt": f"[{escaped_title}]" if raw_title and not default_title else "",
            "title_braced": f"{{{escaped_title}}}" if raw_title and not default_title else "",
        })

    rendered = render(root)

    # Collapse excess blank lines, but do not touch lstlisting content.
    chunks = re.split(
        r"(\\begin\{lstlisting\}.*?\\end\{lstlisting\})",
        rendered,
        flags=re.DOTALL,
    )
    for i, chunk in enumerate(chunks):
        if not chunk.startswith(r"\begin{lstlisting}"):
            chunks[i] = re.sub(r"\n{3,}", "\n\n", chunk)

    return "".join(chunks).strip() + "\n"


def to_latex_fast_document(tree, *, title="Document", author="Stephen Flood", beamer=False, omit_envs=None, transparent_envs=None):
    body = render_latex_fast(tree, omit_envs=omit_envs, transparent_envs=transparent_envs)
    template = BEAMER_HEADER_TEMPLATE if beamer else ARTICLE_HEADER_TEMPLATE
    header = template.safe_substitute(locals())
    return header + "\n" + body + "\n\\end{document}\n"


# Text-bearing XML fixture for testing render_latex_fast directly.
# The text/tail attributes are semantic; XML indentation whitespace is ignored.
TEST_TREE_XML = r'''
<node name="document" kind="document" tag="div">
  <node name="h1" kind="element" tag="h1" attr_id="fast-latex-renderer-test" text="Fast LaTeX Renderer Test" />

  <node name="p" kind="element" tag="p" text="This paragraph tests ">
    <node name="strong" kind="element" tag="strong" text="bold" tail=", " />
    <node name="em" kind="element" tag="em" text="emphasis" tail=", " />
    <node name="code" kind="element" tag="code" text="inline_code(x + 1)" tail=", and " />
    <node name="a" kind="element" tag="a" attr_href="https://www.python.org/" text="a link to Python" tail="." />
  </node>

  <node name="p" kind="element" tag="p" text="This paragraph has inline math ">
    <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(a^2 + b^2 = c^2\)" tail=", escaped characters like 50% and A&amp;B, and a second sentence." />
  </node>

  <node name="h2" kind="element" tag="h2" attr_id="lists" text="Lists" />

  <node name="ul" kind="element" tag="ul">
    <node name="li" kind="element" tag="li" text="First bullet" />
    <node name="li" kind="element" tag="li" text="Second bullet with ">
      <node name="strong" kind="element" tag="strong" text="bold text" />
    </node>
    <node name="li" kind="element" tag="li" text="Third bullet with ">
      <node name="code" kind="element" tag="code" text="inline_code(&quot;inside list&quot;)" />
    </node>
    <node name="li" kind="element" tag="li" text="Nested list:">
      <node name="ul" kind="element" tag="ul">
        <node name="li" kind="element" tag="li" text="Nested item one" />
        <node name="li" kind="element" tag="li" text="Nested item two with ">
          <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(x^2\)" />
        </node>
      </node>
    </node>
  </node>

  <node name="ol" kind="element" tag="ol">
    <node name="li" kind="element" tag="li" text="First numbered item" />
    <node name="li" kind="element" tag="li" text="Second numbered item with ">
      <node name="em" kind="element" tag="em" text="emphasis" />
    </node>
    <node name="li" kind="element" tag="li" text="Third numbered item with a ">
      <node name="a" kind="element" tag="a" attr_href="https://example.com/path?a=1&amp;b=2" text="link" />
    </node>
  </node>

  <node name="h2" kind="element" tag="h2" attr_id="quote" text="Quote" />
  <node name="blockquote" kind="element" tag="blockquote">
    <node name="p" kind="element" tag="p" text="This is a block quote." />
    <node name="p" kind="element" tag="p" text="It contains ">
      <node name="strong" kind="element" tag="strong" text="bold" tail=", " />
      <node name="em" kind="element" tag="em" text="emphasis" tail=", and " />
      <node name="code" kind="element" tag="code" text="inline code" tail="." />
    </node>
  </node>

  <node name="hr" kind="element" tag="hr" />

  <node name="h2" kind="element" tag="h2" attr_id="display-math" text="Display Math" />
  <node name="div" kind="element" tag="div" attr_class="arithmatex" text="\[f(x) = x^2 - 3x + 2\]" />
  <node name="div" kind="element" tag="div" attr_class="arithmatex" text="\[\int_0^1 x^2\,dx = \frac{1}{3}\]" />

  <node name="h2" kind="element" tag="h2" attr_id="code-block" text="Code Block" />
  <node name="pre" kind="element" tag="pre" text="def square(x):&#10;    return x * x&#10;&#10;print(square(5))" />

  <node name="theorem" kind="admonition" tag="div" title="Pythagorean Theorem">
    <node name="p" kind="element" tag="p" text="If ">
      <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(a\)" tail=", " />
      <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(b\)" tail=", and " />
      <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(c\)" tail=" are the side lengths of a right triangle, then" />
    </node>
    <node name="div" kind="element" tag="div" attr_class="arithmatex" text="\[a^2 + b^2 = c^2.\]" />
  </node>

  <node name="proof" kind="admonition" tag="div" title="Proof">
    <node name="p" kind="element" tag="p" text="This is a short proof paragraph." />
    <node name="ul" kind="element" tag="ul">
      <node name="li" kind="element" tag="li" text="Use the usual area argument." />
      <node name="li" kind="element" tag="li" text="Rearrange the four congruent triangles." />
      <node name="li" kind="element" tag="li" text="Compare the remaining square areas." />
    </node>
  </node>

  <node name="example" kind="admonition" tag="div" title="Inline Features">
    <node name="p" kind="element" tag="p" text="This example contains ">
      <node name="strong" kind="element" tag="strong" text="bold" tail=", " />
      <node name="em" kind="element" tag="em" text="italic" tail=", " />
      <node name="code" kind="element" tag="code" text="inline_code" tail=", and a " />
      <node name="a" kind="element" tag="a" attr_href="https://example.com" text="link" tail="." />
    </node>
  </node>

  <node name="exercise" kind="admonition" tag="div" title="Compute a derivative">
    <node name="p" kind="element" tag="p" text="Compute" />
    <node name="div" kind="element" tag="div" attr_class="arithmatex" text="\[\frac{d}{dx}(x^3 + 2x).\]" />
  </node>

  <node name="answer" kind="details" tag="details" title="Solution">
    <node name="p" kind="element" tag="p" text="The derivative is" />
    <node name="div" kind="element" tag="div" attr_class="arithmatex" text="\[3x^2 + 2.\]" />
  </node>

  <node name="frame" kind="admonition" tag="div" title="A Beamer Frame">
    <node name="p" kind="element" tag="p" text="This paragraph should be inside a ">
      <node name="code" kind="element" tag="code" text="frame" tail="." />
    </node>
    <node name="theorem" kind="admonition" tag="div" title="Nested Theorem">
      <node name="p" kind="element" tag="p" text="Nested custom environments should render recursively." />
    </node>
    <node name="pause" kind="admonition" tag="div" title="Pause">
      <node name="p" kind="element" tag="p" text="This text should appear after a pause." />
    </node>
    <node name="ul" kind="element" tag="ul">
      <node name="li" kind="element" tag="li" text="Slide bullet one" />
      <node name="li" kind="element" tag="li" text="Slide bullet two with ">
        <node name="span" kind="element" tag="span" attr_class="arithmatex" text="\(x+y\)" />
      </node>
    </node>
  </node>

  <node name="presentation" kind="admonition" tag="div" title="Presentation" text="\bigskip\textbf{Example:} calculate the color of points with these $(x,y)$ coordinates: $(0.3,0.2)$, $(-0.7,0.4)$, and $(0.2,-0.3)$" />

  <node name="article" kind="admonition" tag="div" title="Article" text="As an example, suppose that we want to find the colors that an \emph{existing} neuron assigns to the following three $(x,y)$ points: $(0.3,0.2)$, $(-0.7,0.4)$, and $(0.2,-0.3)$" />

  <node name="latexraw" kind="admonition" tag="div" title="Latexraw" text="\begin{center}&#10;This should pass through as raw LaTeX.&#10;\end{center}" />

  <node name="h2" kind="element" tag="h2" attr_id="fallback-candidate" text="Fallback Candidate" />
  <node name="div" kind="element" tag="div" attr_class="custom-html" text="This plain div should render transparently if supported." />
</node>
'''.strip()


if __name__ == "__main__":
    class XMLSyntaxNode:
        def __init__(self, xml_el):
            self.name = xml_el.attrib.get("name")
            self.kind = xml_el.attrib.get("kind")
            self.tag = xml_el.attrib.get("tag")
            self.title = xml_el.attrib.get("title")
            self.text = xml_el.attrib.get("text", "")
            self.tail = xml_el.attrib.get("tail", "")
            self.attrs = {
                key.removeprefix("attr_"): value
                for key, value in xml_el.attrib.items()
                if key.startswith("attr_")
            }
            self.children = [XMLSyntaxNode(child) for child in xml_el]

        def to_etree(self):
            el = ET.Element(self.tag or self.name, self.attrs)
            el.text = self.text
            el.tail = self.tail
            for child in self.children:
                el.append(child.to_etree())
            return el

    tree = XMLSyntaxNode(ET.fromstring(TEST_TREE_XML))
    print(render_latex_fast(tree))
