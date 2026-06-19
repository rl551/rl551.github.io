#!/usr/bin/env python3

import os
import re
import json
import html
import markdown
from datetime import datetime
import argparse

CITATIONS_FILE = 'citations.json'
BIB_FILE = 'bib.tex'
ADDITIONAL_BIB_FILES = ['custom.bib']

def extract_enclosed(text, start, opening, closing):
    if start >= len(text) or text[start] != opening:
        return None, start
    depth = 0
    i = start
    content = []
    while i < len(text):
        ch = text[i]
        if ch == opening:
            depth += 1
            if depth > 1:
                content.append(ch)
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return ''.join(content), i + 1
            else:
                content.append(ch)
        else:
            content.append(ch)
        i += 1
    return None, start

ENTRY_PATTERN = re.compile(
    r'@(?P<type>\w+)\s*\{\s*(?P<key>[^,]+),(?P<body>.*?)\}\s*(?=@|$)',
    re.DOTALL,
)
FIELD_PATTERN = re.compile(
    r'(?P<name>\w+)\s*=\s*\{(?P<value>[^{}]*)\}\s*,?',
    re.DOTALL,
)
BIBLIOGRAPHY_PATTERN = re.compile(r'\\bibliography\{([^{}]+)\}')

def parse_bib_file(path=BIB_FILE, return_entries=False):
    """Parse a minimal subset of BibTeX into a citation dictionary."""
    if not os.path.exists(path):
        return ({}, []) if return_entries else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as err:
        print(f"Warning: Could not read {path}: {err}")
        return ({}, []) if return_entries else {}
    citations = {}
    ordered = []
    for entry in ENTRY_PATTERN.finditer(content):
        key = entry.group('key').strip()
        body = entry.group('body')
        fields = {}
        # Parse fields with proper nested brace handling
        i = 0
        while i < len(body):
            # Find field name
            field_match = re.search(r'(\w+)\s*=\s*\{', body[i:])
            if not field_match:
                break
            
            field_name = field_match.group(1).strip().lower()
            field_start = i + field_match.end() - 1  # Position of opening brace
            
            # Extract field value using nested brace handling
            field_value, end_pos = extract_enclosed(body, field_start, '{', '}')
            if field_value is not None:
                fields[field_name] = field_value.strip()
                i = end_pos
            else:
                i += field_match.end()
        if not key:
            continue
        authors_raw = fields.get('author') or fields.get('authors')
        authors = []
        if authors_raw:
            authors = [a.strip() for a in authors_raw.split(' and ') if a.strip()]
        entry_dict = {
            'key': key,
            'type': entry.group('type').lower(),
            'title': fields.get('title'),
            'authors': authors,
            'year': fields.get('year'),
            'url': fields.get('url'),
            'journal': fields.get('journal'),
            'publisher': fields.get('publisher'),
            'archive': fields.get('archiveprefix'),
            'eprint': fields.get('eprint'),
        }
        citations[key] = entry_dict
        ordered.append((key, entry_dict))
    if return_entries:
        return citations, ordered
    return citations

def load_citations(json_path=CITATIONS_FILE, bib_path=BIB_FILE):
    """Load citation metadata from JSON and/or BibTeX."""
    combined = {}
    bib_entries = parse_bib_file(bib_path)
    combined.update(bib_entries)
    for extra in ADDITIONAL_BIB_FILES:
        extra_entries = parse_bib_file(extra)
        combined.update(extra_entries)
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                combined.update(data)
        except json.JSONDecodeError as err:
            print(f"Warning: Could not parse {json_path}: {err}")
        except Exception as err:
            print(f"Warning: Could not load {json_path}: {err}")
    return combined

CITATIONS = load_citations()

MATH_BLOCK_PATTERN = re.compile(
    r'(\$\$.*?\$\$|\$.*?\$|\\\((?:.|\n)*?\\\)|\\\[(?:.|\n)*?\\\]|\\begin\{align\*\}(?:.|\n)*?\\end\{align\*\}|\\begin\{align\}(?:.|\n)*?\\end\{align\}|\\begin\{equation\*?\}(?:.|\n)*?\\end\{equation\*?\})',
    re.DOTALL,
)
SUBSCRIPT_TEXT_PATTERN = re.compile(r'(_\{)\\text\{([^{}]+)\}')
SUBSCRIPT_TEXT_SIMPLE_PATTERN = re.compile(r'_\\text\{([^{}]+)\}')
SUBSCRIPT_MATHSF_SIMPLE_PATTERN = re.compile(r'_\\mathsf\{([^{}]+)\}')
SUPERSCRIPT_TEXT_PATTERN = re.compile(r'(\^\{)\\text\{([^{}]+)\}')
SUPERSCRIPT_TEXT_SIMPLE_PATTERN = re.compile(r'\^\\text\{([^{}]+)\}')
SUPERSCRIPT_MATHSF_SIMPLE_PATTERN = re.compile(r'\^\\mathsf\{([^{}]+)\}')
TEXTSC_PATTERN = re.compile(r'\\textsc\{([^{}]+)\}')
ALGORITHM_PATTERN = re.compile(r'\\begin\{algorithm\}(?:\[(.*?)\])?(.*?)\\end\{algorithm\}', re.DOTALL)
ALGORITHM_COUNTER = {"count": 0}
ITEMIZE_PATTERN = re.compile(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', re.DOTALL)
CENTER_PATTERN = re.compile(r'\\begin\{center\}(.*?)\\end\{center\}', re.DOTALL)
HREF_PATTERN = re.compile(r'\\href\{([^{}]+)\}\{([^{}]+)\}')
MATH_PLACEHOLDER = "@@MATH{}@@"
MATH_PLACEHOLDER_PATTERN = re.compile(r'@@MATH(\d+)@@')

def create_blog_html(title, date, content, math=True, authors=None):
    """Create HTML blog post matching the existing format"""
    
    # KaTeX script if math is enabled (better \min rendering)
    katex_script = '''
    <!-- KaTeX CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css" integrity="sha384-GvrOXuhMATgEsSwCs4smul74iXGOixntILdUW9XmUC6+HX0sLNAK3q71HotJqlAn" crossorigin="anonymous">
    
    <!-- KaTeX JavaScript -->
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js" integrity="sha384-cpW21h6RZv/phavutF+AuVYrr+dA8xD9zs6FwLpaCct6O9ctzYFfFr4dgmgccOTx" crossorigin="anonymous"></script>
    
    <!-- KaTeX auto-render extension -->
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" integrity="sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05" crossorigin="anonymous"
        onload="renderMathInElement(document.body, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\\\[', right: '\\\\]', display: true},
                {left: '\\\\(', right: '\\\\)', display: false},
                {left: '\\\\begin{align*}', right: '\\\\end{align*}', display: true},
                {left: '\\\\begin{align}', right: '\\\\end{align}', display: true}
            ],
            ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
            ignoredClasses: ['no-katex'],
            throwOnError: false,
            strict: false
        });"></script>''' if math else ''
    
    pseudocode_assets = '''
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pseudocode@latest/build/pseudocode.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/pseudocode@latest/build/pseudocode.min.js"></script>
    '''

    pseudocode_init_script = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    if (window.pseudocode) {
        document.querySelectorAll('.pseudocode-script').forEach(function(el) {
            var container = document.createElement('div');
            container.className = 'pseudocode-container';
            el.parentNode.insertBefore(container, el);
            var code = el.textContent;
            el.remove();
            try {
                pseudocode.render(code, container, {lineNumber: true});
            } catch (err) {
                container.textContent = code;
            }
        });
    }
});
</script>
"""
    
    # Format authors text (inline with date)
    authors_text = ""
    if authors:
        if isinstance(authors, str):
            # Single author or comma-separated string
            author_list = [author.strip() for author in authors.split(',') if author.strip()]
        elif isinstance(authors, list):
            # List of authors
            author_list = [str(author).strip() for author in authors if str(author).strip()]
        else:
            author_list = [str(authors).strip()]
        
        if author_list:
            if len(author_list) == 1:
                authors_text = f'By {html.escape(author_list[0])} • '
            elif len(author_list) == 2:
                authors_text = f'By {html.escape(author_list[0])} and {html.escape(author_list[1])} • '
            else:
                formatted_authors = ', '.join(html.escape(author) for author in author_list[:-1])
                formatted_authors += f', and {html.escape(author_list[-1])}'
                authors_text = f'By {formatted_authors} • '
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Raymond Luo</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">{pseudocode_assets}{katex_script}
</head>
<body>
    <div class="container">
        <header>
            <h1>Raymond Luo</h1>
            <nav>
                <a href="index.html">About</a>
                <a href="research.html">Research</a>
                <a href="projects.html">Projects</a>
                <a href="blog.html">Blog</a>
                <a href="reading_list.html">Reading List</a>
            </nav>
        </header>

        <main>
            <section>
                <div class="blog-nav">
                    <a href="blog.html">← Back to Blog</a>
                </div>
                
                <article class="blog-post-full">
                    <h1>{title}</h1>
                    <p class="blog-meta">{authors_text}{date}</p>
                    
                    <div class="blog-content">
                        {content}
                    </div>
                </article>
            </section>
        </main>

        <footer>
            <div class="contact-buttons">
                <a href="mailto:rayluo@mit.edu" class="btn btn-email" title="Email">✉</a>
                <a href="https://www.linkedin.com/in/raymondlu0/" target="_blank" class="btn btn-linkedin" title="LinkedIn">in</a>
            </div>
        </footer>
    </div>
</body>
{pseudocode_init_script}
</html>'''
    
    return html_template

def parse_markdown_file(filepath):
    """Parse markdown file with YAML front matter"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract YAML front matter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            front_matter = parts[1].strip()
            markdown_content = parts[2].strip()
        else:
            front_matter = ""
            markdown_content = content
    else:
        front_matter = ""
        markdown_content = content
    
    # Parse front matter
    metadata = {}
    for line in front_matter.split('\n'):
        if ':' in line and not line.strip().startswith('#'):
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip().strip('"')
    
    return metadata, markdown_content

def short_author_name(author):
    """Return a short display name (typically last name)."""
    if not author:
        return ""
    clean = ' '.join(str(author).replace('\n', ' ').split())
    if ',' in clean:
        return html.escape(clean.split(',', 1)[0].strip())
    parts = clean.split(' ')
    return html.escape(parts[-1]) if parts else ""

def format_authors(authors):
    """Format author list for citation display."""
    if not authors:
        return ""
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(' and ') if a.strip()]
    names = [short_author_name(author) for author in authors if short_author_name(author)]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} et al."

def format_full_authors(authors):
    """Return full author names joined with commas and 'and'."""
    if not authors:
        return ""
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(' and ') if a.strip()]
    names = [html.escape(' '.join(author.split())) for author in authors if author.strip()]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"

def get_citation_entry(key):
    """Return normalized citation data for a key."""
    entry = CITATIONS.get(key, {})
    authors = format_authors(entry.get('authors') or entry.get('author'))
    year = entry.get('year') or entry.get('date')
    year_text = str(year).strip() if year else ""
    title = entry.get('title')
    label = html.escape(entry.get('label', key))
    url = entry.get('url') or entry.get('link')
    if not authors:
        authors = label
    return {
        'authors': authors,
        'year': year_text,
        'title': html.escape(title) if title else label,
        'url': url,
    }

def format_citation_html(keys, style_code=None):
    """Wrap formatted entries with the appropriate punctuation."""
    keys = [key.strip() for key in keys if key.strip()]
    if not keys:
        return ""
    entries = [get_citation_entry(key) for key in keys]
    parts = []
    for entry in entries:
        text = entry['authors']
        year = entry['year']
        if style_code == 't':  # \citet style
            if year:
                text = f"{text} ({year})"
        else:  # \cite, \citep
            if year:
                text = f"{text}, {year}"
        if entry['url']:
            text = f'<a href="{html.escape(entry["url"])}" target="_blank" rel="noopener">{text}</a>'
        parts.append(text)
    if style_code == 't':
        return f'<span class="citation">{"; ".join(parts)}</span>'
    return f'<span class="citation">({"; ".join(parts)})</span>'

def choose_bibliography_file(name):
    """Resolve bibliography file path from LaTeX command value."""
    candidates = [
        f"{name}.bib",
        f"{name}.tex",
        name,
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def format_reference_entry(entry):
    """Build HTML for a single bibliography entry."""
    if not entry:
        return ""
    merged = dict(entry)
    key = merged.get('key')
    if key and key in CITATIONS:
        source = CITATIONS[key]
        for k, v in source.items():
            if v and k not in merged:
                merged[k] = v
    authors = format_full_authors(merged.get('authors') or merged.get('author', []))
    year = merged.get('year') or merged.get('date')
    year_text = html.escape(str(year)) if year else ""
    title = merged.get('title') or merged.get('label') or key
    # Clean up LaTeX formatting in title
    if title:
        title = re.sub(r'\{([^{}]+)\}', r'\1', title)  # Remove single-level braces
    url = merged.get('url') or merged.get('link')
    archive = (merged.get('archive') or "").lower()
    venue = merged.get('journal') or merged.get('booktitle') or merged.get('publisher')
    if not venue and archive == 'arxiv':
        venue = 'Preprint'
    eprint = merged.get('eprint')
    title_html = html.escape(title)
    if url:
        title_html = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{title_html}</a>'
    parts = []
    if authors:
        parts.append(f"{authors}.")
    if year_text:
        parts.append(f"{year_text}.")
    if title_html:
        parts.append(f"{title_html}.")
    if venue:
        venue_html = f"<em>{html.escape(venue)}</em>"
        if archive == 'arxiv' and eprint:
            venue_html = f"{venue_html}, arXiv:{html.escape(eprint)}."
        else:
            venue_html = f"{venue_html}."
        parts.append(venue_html)
    elif archive == 'arxiv' and eprint:
        parts.append(f"arXiv:{html.escape(eprint)}.")
    return ' '.join(parts)

def render_bibliography(names_str):
    """Render bibliography entries for \\bibliography{} commands."""
    names = [name.strip() for name in names_str.split(',') if name.strip()]
    ordered_entries = []
    for name in names:
        path = choose_bibliography_file(name)
        if not path:
            continue
        _, entries = parse_bib_file(path, return_entries=True)
        ordered_entries.extend(entry for _, entry in entries)
    if not ordered_entries:
        return ""
    entries_html = '\n'.join(
        f'<p class="bibliography-entry"><span class="bibliography-index">[{idx}]</span><span class="bibliography-text">{format_reference_entry(entry)}</span></p>'
        for idx, entry in enumerate(ordered_entries, start=1)
    )
    return f'\n<div class="bibliography"><h2>References</h2>{entries_html}</div>\n'

CITE_PATTERN = re.compile(r'\\cite(?P<style>t|p)?\{(?P<keys>[^{}]+)\}')

def replace_citations(segment):
    """Replace LaTeX citation commands with HTML."""
    def repl(match):
        style_code = match.group('style')
        keys = match.group('keys').split(',')
        html_snippet = format_citation_html(keys, style_code)
        return html_snippet or match.group(0)
    return CITE_PATTERN.sub(repl, segment)

def render_figure(options, path, caption):
    attrs = [f'src="{html.escape(path)}"']
    style_parts = []
    alt_text = os.path.basename(path)
    if '.' in alt_text:
        alt_text = alt_text.rsplit('.', 1)[0]
    attrs.append(f'alt="{html.escape(alt_text)}"')

    def width_to_css(value):
        value = value.strip()
        textwidth_match = re.match(r'([\d.]+)\\textwidth', value)
        if textwidth_match:
            fraction = float(textwidth_match.group(1))
            return f'{fraction * 100:.0f}%'
        return value

    if options:
        for pair in options.split(','):
            if '=' not in pair:
                continue
            key, val = pair.split('=', 1)
            key = key.strip().lower()
            val = val.strip()
            if key == 'width':
                css_value = width_to_css(val)
                style_parts.append(f'width: {css_value}')
            elif key == 'height':
                style_parts.append(f'height: {val}')
            elif key == 'scale':
                try:
                    scale = float(val.strip())
                    if scale > 0:
                        percent = scale * 100
                        style_parts.append(f'width: {percent:.0f}%')
                        style_parts.append('height: auto')
                except ValueError:
                    continue

    if style_parts:
        attrs.append(f'style="{"; ".join(style_parts)}"')
    img_html = f'<img {" ".join(attrs)} />'
    if caption:
        caption_html = transform_text(caption.strip(), allow_figures=False)
        caption_html = f'<div class="image-caption">{caption_html}</div>'
        return f'<div class="image-with-caption">{img_html}{caption_html}</div>'
    return img_html

def replace_figures(segment):
    result = []
    i = 0
    token = '\\includegraphics'
    while i < len(segment):
        idx = segment.find(token, i)
        if idx == -1:
            result.append(segment[i:])
            break
        result.append(segment[i:idx])
        j = idx + len(token)
        options = ""
        if j < len(segment) and segment[j] == '[':
            options, j = extract_enclosed(segment, j, '[', ']')
            if options is None:
                # malformed; emit literal
                result.append(segment[idx:j+1])
                i = j + 1
                continue
        if j >= len(segment) or segment[j] != '{':
            result.append(token)
            i = j
            continue
        path, j = extract_enclosed(segment, j, '{', '}')
        if path is None:
            result.append(token)
            i = j
            continue
        k = j
        while k < len(segment) and segment[k].isspace():
            k += 1
        caption = None
        if segment.startswith('\\caption', k):
            cap_start = k + len('\\caption')
            if cap_start < len(segment) and segment[cap_start] == '{':
                caption, k = extract_enclosed(segment, cap_start, '{', '}')
        figure_html = render_figure(options or "", path.strip(), caption)
        result.append(figure_html)
        i = k
    return ''.join(result)

def render_algorithms(text):
    def repl(match):
        ALGORITHM_COUNTER["count"] += 1
        opts = match.group(1)
        body = match.group(2).strip()
        title_match = re.search(r'\\caption\{([^{}]+)\}', body)
        title = title_match.group(1).strip() if title_match else "Algorithm"
        body = re.sub(r'\\caption\{([^{}]+)\}', '', body, count=1).strip()
        header = "\\begin{algorithm}"
        if opts:
            header += f"[{opts}]"
        content = f"{header}\n\\caption{{Algorithm {ALGORITHM_COUNTER['count']} {title}}}\n{body}\n\\end{{algorithm}}"
        return f'\n<pre class="pseudocode-script">{html.escape(content)}</pre>\n'
    return ALGORITHM_PATTERN.sub(repl, text)

def render_center_environment(text):
    """Convert LaTeX center environment to HTML with centered content."""
    def repl(match):
        content = match.group(1).strip()
        
        # Remove HTML comments first
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        # Handle caption that applies to all images in the center environment (handle nested braces)
        caption = None
        caption_start = content.find('\\caption{')
        if caption_start != -1:
            brace_start = caption_start + len('\\caption')
            caption_content, _ = extract_enclosed(content, brace_start, '{', '}')
            if caption_content is not None:
                caption = caption_content.strip()
        
        # Remove the caption from content before processing figures
        if caption:
            content = re.sub(r'\\caption\{([^{}]+)\}', '', content).strip()
        
        # Process figures individually but without captions (since we have a global caption)
        result = []
        i = 0
        token = '\\includegraphics'
        while i < len(content):
            idx = content.find(token, i)
            if idx == -1:
                result.append(content[i:])
                break
            result.append(content[i:idx])
            j = idx + len(token)
            options = ""
            if j < len(content) and content[j] == '[':
                options, j = extract_enclosed(content, j, '[', ']')
                if options is None:
                    result.append(content[idx:j+1])
                    i = j + 1
                    continue
            if j >= len(content) or content[j] != '{':
                result.append(token)
                i = j
                continue
            path, j = extract_enclosed(content, j, '{', '}')
            if path is None:
                result.append(token)
                i = j
                continue
            
            # Render figure without caption (we'll add the global caption later)
            figure_html = render_figure(options or "", path.strip(), None)
            result.append(figure_html)
            i = j
        
        processed_content = ''.join(result)
        
        # Remove any remaining \caption commands from processed content (handle nested braces)
        while '\\caption{' in processed_content:
            start = processed_content.find('\\caption{')
            if start == -1:
                break
            brace_start = start + len('\\caption')
            caption_content, end_pos = extract_enclosed(processed_content, brace_start, '{', '}')
            if caption_content is not None:
                processed_content = processed_content[:start] + processed_content[end_pos:]
            else:
                break
        
        # Apply other text transformations (citations, etc.) to any remaining content
        processed_content = transform_text(processed_content, allow_figures=False)
        
        # If there's a caption, wrap everything with the caption
        if caption:
            caption_html = transform_text(caption, allow_figures=False)
            processed_content = f'{processed_content}<div class="image-caption">{caption_html}</div>'
        
        # Wrap in a centered div with inline display for images
        return f'\n<div class="center-environment">{processed_content}</div>\n'
    return CENTER_PATTERN.sub(repl, text)
def transform_text(segment, allow_figures=True):
    if not segment:
        return segment
    segment = HREF_PATTERN.sub(lambda m: f'<a href="{html.escape(m.group(1).strip())}" target="_blank" rel="noopener">{m.group(2).strip()}</a>', segment)
    def convert_itemize(match):
        items = [item.strip() for item in re.split(r'\\item', match.group(1)) if item.strip()]
        if not items:
            return ''
        return '\n\n' + '\n'.join(f"- {item}" for item in items) + '\n\n'
    segment = ITEMIZE_PATTERN.sub(convert_itemize, segment)
    # Handle LaTeX commands with proper nested brace support
    def handle_latex_command(segment, command, replacement_func):
        result = []
        i = 0
        token = f'\\{command}{{'
        while i < len(segment):
            idx = segment.find(token, i)
            if idx == -1:
                result.append(segment[i:])
                break
            result.append(segment[i:idx])
            brace_start = idx + len(token) - 1  # Position of opening brace
            content, end_pos = extract_enclosed(segment, brace_start, '{', '}')
            if content is not None:
                result.append(replacement_func(content))
                i = end_pos
            else:
                result.append(token)
                i = idx + len(token)
        return ''.join(result)
    
    # Apply LaTeX command replacements with proper brace handling
    segment = handle_latex_command(segment, 'textbf', lambda x: f'**{x}**')
    segment = handle_latex_command(segment, 'textit', lambda x: f'*{x}*')
    segment = handle_latex_command(segment, 'emph', lambda x: f'*{x}*')
    segment = handle_latex_command(segment, 'underline', lambda x: f'<u>{x}</u>')
    segment = handle_latex_command(segment, 'textsc', lambda x: x.upper())
    
    # Simple regex replacements for commands without nested braces
    simple_replacements = [
        (r'\\section\{([^{}]+)\}', r'\n## \1\n'),
        (r'\\subsection\{([^{}]+)\}', r'\n### \1\n'),
        (r'\\subsubsection\{([^{}]+)\}', r'\n#### \1\n'),
        (r'\\newline', r'<br>'),
    ]
    for pattern, repl in simple_replacements:
        segment = re.sub(pattern, repl, segment)
    if allow_figures:
        segment = replace_figures(segment)
    segment = replace_citations(segment)
    segment = BIBLIOGRAPHY_PATTERN.sub(lambda match: render_bibliography(match.group(1)), segment)
    segment = re.sub(r'(?<!-)--(?!-)', '&mdash;', segment)
    segment = re.sub(r"``([^`]+)''", r'"\1"', segment)
    return segment

def preprocess_latex_text(markdown_content):
    """Convert common LaTeX text macros to Markdown outside math blocks."""
    markdown_content = render_algorithms(markdown_content)
    markdown_content = render_center_environment(markdown_content)
    math_blocks = []

    def convert_math_block(match):
        block = match.group(0)
        block = TEXTSC_PATTERN.sub(lambda m: f'\\text{{{m.group(1).upper()}}}', block)
        block = SUBSCRIPT_TEXT_PATTERN.sub(lambda m: f"{m.group(1)}\\mathsf{{{m.group(2)}}}" + "}", block)
        block = SUBSCRIPT_TEXT_SIMPLE_PATTERN.sub(lambda m: f"_{{\\mathsf{{{m.group(1)}}}}}", block)
        block = SUBSCRIPT_MATHSF_SIMPLE_PATTERN.sub(lambda m: f"_{{\\mathsf{{{m.group(1)}}}}}", block)
        block = SUPERSCRIPT_TEXT_PATTERN.sub(lambda m: f"{m.group(1)}\\mathsf{{{m.group(2)}}}" + "}", block)
        block = SUPERSCRIPT_TEXT_SIMPLE_PATTERN.sub(lambda m: f"^{{\\mathsf{{{m.group(1)}}}}}", block)
        block = SUPERSCRIPT_MATHSF_SIMPLE_PATTERN.sub(lambda m: f"^{{\\mathsf{{{m.group(1)}}}}}", block)
        placeholder = MATH_PLACEHOLDER.format(len(math_blocks))
        math_blocks.append(block)
        return placeholder

    transformed = MATH_BLOCK_PATTERN.sub(convert_math_block, markdown_content)
    transformed = transform_text(transformed, allow_figures=True)
    return transformed, math_blocks

def restore_math_blocks(html_content, math_blocks):
    if not math_blocks:
        return html_content
    
    # First restore the math blocks
    def repl(match):
        idx = int(match.group(1))
        if 0 <= idx < len(math_blocks):
            return math_blocks[idx]
        return match.group(0)
    
    html_content = MATH_PLACEHOLDER_PATTERN.sub(repl, html_content)
    
    # Now clean up paragraph tags around display math
    # Remove paragraph tags that only contain display math
    html_content = re.sub(r'<p>\s*(\\begin\{[^}]+\}.*?\\end\{[^}]+\})\s*</p>', r'\1', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<p>\s*(\$\$.*?\$\$)\s*</p>', r'\1', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<p>\s*(\\\\?\[.*?\\\\?\])\s*</p>', r'\1', html_content, flags=re.DOTALL)
    
    # Handle math at the end of paragraphs
    html_content = re.sub(r'<p>([^<]*?)(\\begin\{[^}]+\}.*?\\end\{[^}]+\})', r'<p>\1</p>\2', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<p>([^<]*?)(\$\$.*?\$\$)', r'<p>\1</p>\2', html_content, flags=re.DOTALL)
    
    # Handle math at the start of paragraphs  
    html_content = re.sub(r'(\\begin\{[^}]+\}.*?\\end\{[^}]+\})([^<]*?)</p>', r'\1<p>\2</p>', html_content, flags=re.DOTALL)
    html_content = re.sub(r'(\$\$.*?\$\$)([^<]*?)</p>', r'\1<p>\2</p>', html_content, flags=re.DOTALL)
    
    # Clean up empty paragraphs and extra whitespace
    html_content = re.sub(r'<p>\s*</p>', '', html_content)
    html_content = re.sub(r'</p>\s*<p>', '</p>\n<p>', html_content)
    
    return html_content

def convert_markdown_to_html(markdown_content):
    """Convert markdown to HTML with math support"""
    # Configure markdown with math support
    md = markdown.Markdown(extensions=['extra', 'codehilite'])
    html_content = md.convert(markdown_content)
    return html_content

def create_blog_post_from_markdown(markdown_file):
    """Convert a markdown file to an HTML blog post"""
    metadata, markdown_content = parse_markdown_file(markdown_file)
    markdown_content, math_blocks = preprocess_latex_text(markdown_content)
    
    title = metadata.get('title', 'Untitled Post')
    date = metadata.get('date', datetime.now().strftime('%B %d, %Y'))
    math = metadata.get('math', 'true').lower() == 'true'
    authors = metadata.get('authors') or metadata.get('author')
    
    # Convert markdown to HTML
    html_content = convert_markdown_to_html(markdown_content)
    html_content = restore_math_blocks(html_content, math_blocks)
    
    # Create full HTML page
    full_html = create_blog_html(title, date, html_content, math, authors)
    
    # Generate filename from title only
    slug = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip().replace(' ', '-').lower()
    filename = f"blog-post-{slug}.html"
    
    return filename, full_html

def update_blog_index(title, date, filename, excerpt):
    """Update blog.html to include the new post"""
    try:
        with open('blog.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_post_html = f'''                <div class="blog-post">
                    <h3><a href="{filename}">{title}</a></h3>
                    <p class="blog-date">{date}</p>
                    <p>{excerpt}</p>
                    <p><a href="{filename}">Read more</a></p>
                </div>
                
'''
        
        # Insert after the opening <section> tag
        section_pattern = r'(<section>\s*)'
        updated_content = re.sub(
            section_pattern,
            lambda match: f"{match.group(1)}{new_post_html}",
            content,
            count=1,
        )
        
        with open('blog.html', 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Updated blog.html to include {title}")
        
    except Exception as e:
        print(f"Warning: Could not update blog.html: {e}")

def main():
    parser = argparse.ArgumentParser(description='Convert markdown blog post to HTML')
    parser.add_argument('markdown_file', help='Path to markdown file')
    parser.add_argument('--update-index', action='store_true', help='Update blog.html index')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.markdown_file):
        print(f"Error: File {args.markdown_file} not found")
        return
    
    try:
        filename, html_content = create_blog_post_from_markdown(args.markdown_file)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Created {filename}")
        
        if args.update_index:
            # Extract metadata for index
            metadata, markdown_content = parse_markdown_file(args.markdown_file)
            title = metadata.get('title', 'Untitled Post')
            date = metadata.get('date', datetime.now().strftime('%B %d, %Y'))
            
            # Create excerpt from first paragraph (clean up markdown)
            lines = markdown_content.split('\n')
            excerpt = next((line for line in lines if line.strip() and not line.startswith('#')), "")
            # Clean up markdown formatting for excerpt
            excerpt = re.sub(r'\*\*(.*?)\*\*', r'\1', excerpt)  # Remove bold
            excerpt = re.sub(r'\*(.*?)\*', r'\1', excerpt)      # Remove italic
            excerpt = excerpt[:150]
            
            update_blog_index(title, date, filename, excerpt)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 
