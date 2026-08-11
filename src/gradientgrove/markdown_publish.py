from gradientgrove.markdown_ast import SyntaxTree, latex_to_markdown_main
from gradientgrove import latex_fence

import argparse
import base64
import mimetypes
import subprocess
import sys
import shutil 

# import yaml # mkdocs already depends on `pyyaml`
from mkdocs.utils.meta import get_data

from mkdocs.commands.build import get_files
from mkdocs.config import load_config
from mkdocs.structure.nav import get_navigation
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile
import re
import html

DEFAULT_EXTENSIONS = [
    "tables",
    "fenced_code",
    "toc",
    "sane_lists",
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "pymdownx.arithmatex",
    "pymdownx.details",
    "pymdownx.superfences",
]

HTML_EXTENSION_CONFIGS = {
    "pymdownx.arithmatex": {"generic": True},
    "pymdownx.superfences": {
        "custom_fences": [
            {"name": "latex", "class": "latex-svg", "format": latex_fence.latex_cache_fence},
            {"name": "tikz", "class": "latex-svg", "format": latex_fence.latex_cache_fence},
            # {"name": "latex", "class": "latex-svg", "format": latex_fence.latex_svg_fence},
            # {"name": "tikz", "class": "latex-svg", "format": latex_fence.latex_svg_fence},
        ]
    }
}

def latex_raw_fence(source, language, css_class, options, md, **kwargs):
    return (
        '<div class="admonition latexraw">'
        f'<pre><code>{html.escape(source)}</code></pre>'
        '</div>'
    )
TEX_EXTENSION_CONFIGS = {
    "pymdownx.arithmatex": {"generic": True},
    "pymdownx.superfences": {
        "custom_fences": [
            {"name": "latex", "class": "latex-raw", "format": latex_raw_fence},
            {"name": "tikz",  "class": "latex-raw", "format": latex_raw_fence},
        ]
    },
}# DEFAULT_EXTENSION_CONFIGS={
#     "pymdownx.arithmatex": {
#         "generic": True,
#     },
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
# }


DEFAULT_NUMBERED_ENVS = {
    "exercise" : "Exercise",
}

def compile_latex(filename):
    """Compile a TeX file to PDF."""
    result = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", filename.name],
        cwd=filename.parent,
        text=True,
        # capture_output=True,
        stdout=subprocess.DEVNULL,
        # stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        pdf = filename.with_suffix(".pdf")
        if not pdf.exists():
            print(f"Compile failed: {filename}")
            print(result.stdout)
            return False
        else:
            print(f"Compile succeded with errors: {filename}")
            print(result.stdout)
            return True
    return True

def resolve_local_image_paths(tree, markdown_parent):
    """Resolve existing local image src values relative to the Markdown file."""
    markdown_parent = Path(markdown_parent)
    for node in tree.walk():
        if node.name != "img" or "src" not in node.attrs:
            continue

        src = node.attrs["src"]
        parsed = urlparse(src)
        if parsed.scheme or parsed.netloc or Path(src).is_absolute():
            continue

        resolved = (markdown_parent / src).resolve()
        if resolved.exists():
            # node.attrs["src"] = str(resolved)
            node.attrs["src"] = resolved.as_posix()


def embed_local_images(tree, markdown_parent):
    """Embed existing local image src values as data URIs."""
    markdown_parent = Path(markdown_parent)
    for node in tree.walk():
        if node.name != "img" or "src" not in node.attrs:
            continue

        src = node.attrs["src"]
        parsed = urlparse(src)
        if parsed.scheme or parsed.netloc:
            continue

        image_path = Path(src)
        if not image_path.is_absolute():
            image_path = markdown_parent / image_path

        if not image_path.exists():
            continue

        mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
        image_bytes = base64.b64encode(image_path.read_bytes()).decode("ascii")
        node.attrs["src"] = f"data:{mime_type};base64,{image_bytes}"


def build_tree(text, *, omit_envs=(), number=False, render_latex_fences=True):
    """Build a Markdown syntax tree."""
    tree = SyntaxTree.from_markdown(
        text,
        extensions=DEFAULT_EXTENSIONS,
        extension_configs=HTML_EXTENSION_CONFIGS if render_latex_fences else TEX_EXTENSION_CONFIGS,
    )
    tree.prune_envs(set(omit_envs))
    if number:
        tree.number_envs(DEFAULT_NUMBERED_ENVS)
        tree.number_sections()
    return tree


def package_outputs(zip_path, outputs, *, base_directory):
    """Package generated outputs into one zip file."""
    outputs = list(dict.fromkeys(outputs))
    with ZipFile(zip_path, "w") as zf:
        print(f"Packaging Zip: {zip_path}")
        for output in outputs:
            arcname = output.relative_to(base_directory)
            print(f"Writing {arcname}")
            zf.write(output, arcname=arcname)


def convert_mkdocs_directory(path, output_directory, *, page_zip=True, **options):
    """Convert a MkDocs directory."""
    output_directory.mkdir(parents=True, exist_ok=True)

    config_file = path / "mkdocs.yml"
    if not config_file.exists():
        print(f"Error: {config_file} does not exist")
        sys.exit(1)

    config = load_config(
        config_file=str(config_file),
        theme="mkdocs",  # Default theme for zensical compatiblity
        )
    files = get_files(config)
    nav = get_navigation(files, config)
    pages = [page for page in nav.pages if page.file.src_uri.endswith(".md")]

    site_title = config['site_name']
    site_title = re.sub(r'[^A-Za-z0-9 -_]', '', site_title)
    site_title = re.sub(r'[ -]+', '_', site_title)
    site_title_md = site_title + ".md"
    site_title_zip = site_title + ".zip"

    generated = []
    # merged_file = output_directory / "mkdocs-merged.md"
    merged_file = output_directory / site_title_md
    try:
        merged = "\n\n".join(
            Path(page.file.abs_src_path).read_text(encoding="utf-8")
            for page in pages
        )
        merged_file.write_text(merged, encoding="utf-8")
        generated.extend(
            convert_file(
                merged_file, output_directory, 
                    image_base=Path(config.docs_dir),
                    **options, package_zip=False,
                )
            )
    finally:
        merged_file.unlink(missing_ok=True)

    if page_zip:
        for page in pages:
            page_source = Path(page.file.abs_src_path)
            page_output_directory = output_directory / Path(page.file.src_uri).with_suffix("").parent
            page_output_directory.mkdir(parents=True, exist_ok=True)
            generated.extend(
                convert_file(page_source, page_output_directory, 
                        image_base=Path(config.docs_dir),
                        **options, package_zip=False
                    )
                )

    version = options.get("version", "")
    # zip_name = f"mkdocs-{version}.zip" if version else "mkdocs.zip"
    zip_name = f"{site_title_zip}-{version}.zip" if version else site_title_zip
    package_outputs(output_directory / zip_name, generated, base_directory=output_directory)
    return generated

def convert_file(filename, output_directory, *, 
                 base=False, tex=False, revealjs=False,beamer=False, handout=False, tex_handout=False, 
                 version="", package_zip=True,
                 image_base=None,
    ):
    tex_generated = []
    generated = []
    version_str = f"-{version}" if version else ""

    image_base = image_base or filename.parent

    page_name = filename.stem
    default_title = re.sub(r"[_-]+", " ", page_name).title()

    # text = Path(filename).read_text(encoding="utf-8")
    text = filename.read_text(encoding="utf-8")

    # Extract metadata, separate from body
    text, meta = get_data(text) 
    title = meta.get("title", default_title)
    author = meta.get("author", "Stephen Flood")
    if isinstance(author, list):
        author = ", ".join(author)
    date = meta.get("date", "")

    if base:
        tree = build_tree(text, number=True, render_latex_fences=True)
        embed_local_images(tree, image_base)
        # variant=version_str+"-base"
        variant = version_str

        output = tree.to_html(title=title)
        output_file = output_directory / f"{page_name}{variant}.html"
        output_file.write_text(output, encoding="utf-8")

        generated.append(output_file)

    if handout:
        tree = build_tree(text, omit_envs=["answer"], number=True, render_latex_fences=True)
        embed_local_images(tree, image_base)
        
        variant=version_str+"-handout"

        output = tree.to_html(title=title)
        output_file = output_directory / f"{page_name}{variant}.html"
        output_file.write_text(output, encoding="utf-8")

        generated.append(output_file)

    if revealjs:
        tree = build_tree(text, number=True, render_latex_fences=True)
        embed_local_images(tree, image_base)
        variant=version_str+"-revealjs"

        output = tree.to_revealjs(title=title)
        output_file = output_directory / f"{page_name}{variant}.html"
        output_file.write_text(output, encoding="utf-8")

        generated.append(output_file)


    if tex:
        tree = build_tree(text, number=False, render_latex_fences=False)
        resolve_local_image_paths(tree,  image_base)
        # variant=version_str+"-base"
        variant = version_str
        output = tree.to_latex(
            title=title,
            # author="Stephen Flood",
            author=author,
            date=date,
            beamer=False,
        )

        output_file = output_directory / f"{page_name}{variant}.tex"
        output_file.write_text(output, encoding="utf-8")

        tex_generated.append(output_file)
        
        # Do/don't include tex in zip 
        # generated.append(output_file)

    if tex_handout:
        tree = build_tree(text, number=False, omit_envs = ["answer"], render_latex_fences=False)
        resolve_local_image_paths(tree, image_base)
        variant=version_str+"-handout"
        output = tree.to_latex(
            title=title,
            author="Stephen Flood",
            beamer=False,
        )

        output_file = output_directory / f"{page_name}{variant}.tex"
        output_file.write_text(output, encoding="utf-8")
        # output = output_latex_article(filename,output_directory,variant=version_str+"-base")
        tex_generated.append(output_file)

        # Do/don't include tex in zip 
        # generated.append(output_file)

    if beamer:
        tree = build_tree(text, number=False, render_latex_fences=False)
        resolve_local_image_paths(tree,  image_base)
        variant=version_str+"-slides"
        output = tree.to_latex(
            title=title,
            author="Stephen Flood",
            beamer=True,
        )

        output_file = output_directory / f"{page_name}{variant}.tex"
        output_file.write_text(output, encoding="utf-8")
        # output = output_latex_article(filename,output_directory,variant=version_str+"-base")
        tex_generated.append(output_file)

        # Do/don't include tex in zip 
        # generated.append(output_file)

    # Compile LaTeX output
    for output in tex_generated:
        print("Compiling", output)
        compile_latex(output)
        pdf_output = output.with_suffix(".pdf")
        if pdf_output.exists():
            generated.append(pdf_output)

    for tex_file in tex_generated:

        remove = {".log", ".vrb", ".fls", ".bbl",".blg"}
        # keep = {".md", ".html", ".tex", ".pdf", ".aux", ".toc", ".out", ".nav", ".snm"}
        stem = tex_file.with_suffix("")

        for f in tex_file.parent.glob(stem.name + ".*"):
            if f.name.endswith(".synctex.gz"):
                f.unlink(missing_ok=True)
            elif f.suffix in remove:
                f.unlink(missing_ok=True)

    if generated and package_zip:
        zip_file = f"{filename.stem}-{version}.zip" if version else f"{filename.stem}.zip"
        package_outputs(output_directory / zip_file, generated, base_directory=output_directory)

    return generated

def main():
    """Run the command-line converter."""
  
    # TODO: Package ALL files in a zip, including PDF

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Optional file or directory (defaults to MkDocs merge mode in current directory)",
    )

    parser.add_argument("--version", "-v", type=str, default="", help="Optional version number")
    parser.add_argument("--base", action="store_true", help="Generate HTML base document")
    parser.add_argument("--handout", action="store_true", help="Generate HTML handout")
    parser.add_argument("--revealjs", action="store_true", help="Generate revealjs slides")
    parser.add_argument("--html", action="store_true", help="Generate *all* HTML documents")
    parser.add_argument("--tex", action="store_true", help="Generate TeX base document")
    parser.add_argument("--pdf", action="store_true", help="Generate TeX base document")
    parser.add_argument("--pdf-handout", action="store_true", help="Generate TeX handout")
    parser.add_argument("--beamer", action="store_true", help="Generate Beamer slides")
    parser.add_argument("--all", action="store_true", help="Generate all outputs")
    parser.add_argument(
        "--mkdocs-page-zip",
        dest="mkdocs_page_zip",
        action="store_true",
        default=False,
        help="In MkDocs mode, include each source page's outputs in the single .publish_cache/mkdocs.zip package (default)",
    )
    parser.add_argument(
        "--no-mkdocs-page-zip",
        dest="mkdocs_page_zip",
        action="store_false",
        help="In MkDocs mode, only build and package the merged MkDocs output",
    )

    args = parser.parse_args()

    if args.path is None:
        path = Path(".").resolve()
    else:
        path = Path(args.path).resolve()
        if not path.exists():
            print(f"Error: {path} does not exist")
            sys.exit(1)

    options = {
        "base" : args.base or args.all or args.html,
        # "handout" : args.all or args.html or args.handout,
        # "revealjs" : args.all or args.html or args.revealjs, 
        "handout" : args.all or args.handout,
        "revealjs" : args.all or args.revealjs,   
        "tex" : args.all or args.tex or args.pdf,
        "tex_handout" : args.all or args.pdf_handout ,
        "beamer" : args.all or args.beamer ,
        "version" : args.version,
    }

    if True not in options.values():
        options["base"] = True

    if args.path is None:
        output_directory = path / ".publish_cache"
        output_directory.mkdir(parents=True, exist_ok=True)
        print(f"Got a MkDocs directory: {path}")
        convert_mkdocs_directory(path, output_directory, page_zip=args.mkdocs_page_zip, **options)

    elif path.is_file():
        tex_directory = path.parent
        output_directory = path.parent / ".publish_cache"
        output_directory.mkdir(parents=True, exist_ok=True)
        
        print(f"Got a file: {path}")

        if path.suffix.lower() == ".tex":
            markdown_path = output_directory / path.with_suffix(".md").name
            latex_to_markdown_main([str(path), str(markdown_path)])
            path = markdown_path

        generated = convert_file(
            path,
            output_directory,
            **options
        )
        # copy any generated PDFs back into the tex file directory. 
        for pdf in (p for p in generated if p.suffix == ".pdf"):
            shutil.copy2(pdf, tex_directory)

    elif path.is_dir():
        output_directory = path / ".publish_cache"
        output_directory.mkdir(parents=True, exist_ok=True)
        print(f"Got a directory: {path}")
        generated = []
        for filename in path.rglob("*.md"):
            if output_directory in filename.parents:
                continue
            generated.extend(convert_file(
                filename,
                output_directory,
                **options,
                package_zip=False,
            ))

        version = f"-{args.version}" if args.version else ""
        if generated:
            package_outputs(output_directory / f"{path.name}{version}.zip", generated, base_directory=output_directory)


if __name__ == "__main__":
    main()
