#!/usr/bin/env python3
"""Mechanical sweep for a WordPress.org theme review.

Gathers the deterministic facts a reviewer needs: fetches and installs the
submitted zip, resets the test content, runs Theme Check, crawls the templates
with WP_DEBUG on, and greps for the things that commonly fail a review.

It reports facts and flags candidates. It does not decide what is a finding -
that stays with the reviewer.

Usage:
    theme-sweep.py fetch <slug> <version>   download + install the zip
    theme-sweep.py check <slug>             activate, crawl, sweep, write report
    theme-sweep.py run <slug> <version>     fetch, reset, then check
    theme-sweep.py reset                    restore the baseline snapshot
    theme-sweep.py baseline                 take the baseline snapshot

Run it from the DDEV theme-review project root, or pass --project.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ZIP_URL = "https://downloads.wordpress.org/theme/{slug}.{version}.zip?nostats=1"
SNAPSHOT = "baseline-unittest"

# Paths crawled with WP_DEBUG on, relative to the site root.
CRAWL_PATHS = [
    "/",
    "/sample-page/",
    "/template-sticky/",
    "/category/6-1/",
    "/?s=test",
    "/no-such-page-404/",
    "/?author=1",
]

# Google Fonts is the one remote exception the required items allow.
REMOTE_ALLOWED = {"fonts.googleapis.com", "fonts.gstatic.com"}
REMOTE_PATTERN = re.compile(r"https?://([a-z0-9.-]+\.[a-z]{2,})", re.I)

# (label, regex, why a human should look)
GREPS = [
    ("destructive-delete",
     re.compile(r"wp_delete_post\s*\([^)]*,\s*true", re.I),
     "force delete - destroys content with no trash"),
    ("destructive-term",
     re.compile(r"wp_delete_term\s*\(", re.I),
     "deletes taxonomy terms"),
    ("admin-menu",
     re.compile(r"add_(theme|menu|submenu|options|management)_page\s*\(", re.I),
     "admin page - demo imports and onboarding are not allowed here"),
    ("admin-notice",
     re.compile(r"add_action\s*\(\s*['\"]admin_notices['\"]", re.I),
     "admin notice - check it is not an onboarding prompt"),
    ("after-switch-theme",
     re.compile(r"add_action\s*\(\s*['\"]after_switch_theme['\"]", re.I),
     "activation hook - often drives an onboarding flow"),
    ("remote-fetch",
     re.compile(r"(wp_remote_get|wp_remote_post|curl_exec|file_get_contents)\s*\(", re.I),
     "check the target is a local bundled file, not a remote call"),
    ("superglobal",
     re.compile(r"\$_(GET|POST|REQUEST)\s*\[", re.I),
     "superglobal read - confirm a nonce check covers it"),
]


def run(cmd, cwd=None, check=False):
    """Run a command, returning (rc, stdout, stderr)."""
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"command failed: {cmd}\n{p.stderr.strip()}")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def wp(project, args):
    """Run a wp-cli command inside DDEV, returning stdout or ''."""
    rc, out, _ = run(["ddev", "wp"] + args, cwd=project)
    return out if rc == 0 else ""


def site_url(project):
    return wp(project, ["option", "get", "home"]) or f"https://{project.name}.ddev.site"


# --------------------------------------------------------------------------
# static inspection
# --------------------------------------------------------------------------

def parse_header(style_css):
    """Pull the style.css theme header into a dict."""
    block = style_css.read_text(encoding="utf-8", errors="replace").split("*/", 1)[0]
    header = {}
    for line in block.splitlines():
        m = re.match(r"\s*([A-Za-z][A-Za-z ]*?)\s*:\s*(.+?)\s*$", line)
        if m:
            header[m.group(1).strip().lower()] = m.group(2).strip()
    return header


def theme_shape(theme_dir):
    """Classic or block, and what the theme actually ships."""
    def names(sub, ext):
        d = theme_dir / sub
        return sorted(p.name for p in d.glob(ext)) if d.is_dir() else []

    shape = {
        "block": (theme_dir / "templates").is_dir(),
        "templates": names("templates", "*.html"),
        "parts": names("parts", "*.html"),
        "patterns": names("patterns", "*.php"),
        "styles": names("styles", "*.json"),
        "theme_json": None,
        "page_templates": [],
    }
    tj = theme_dir / "theme.json"
    if tj.is_file():
        try:
            shape["theme_json"] = json.loads(tj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            shape["theme_json"] = {"_parse_error": str(e)}
    for php in theme_dir.rglob("*.php"):
        head = php.read_text(encoding="utf-8", errors="replace")[:1500]
        if re.search(r"Template Name\s*:", head):
            shape["page_templates"].append(str(php.relative_to(theme_dir)))
    return shape


def tag_evidence(theme_dir, header, shape):
    """For each declared tag, say what in the theme backs it up."""
    php = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                    for p in theme_dir.rglob("*.php"))
    supports = set(re.findall(r"add_theme_support\s*\(\s*['\"]([a-z0-9-]+)['\"]", php))
    has_nav = bool(re.search(r"register_nav_menus?\s*\(", php))
    tj = shape.get("theme_json") or {}
    settings = tj.get("settings", {}) if isinstance(tj, dict) else {}
    layout = settings.get("layout", {}) or {}
    palette = (settings.get("color", {}) or {}).get("palette", []) or []
    nav_block = any("wp:navigation" in p.read_text(encoding="utf-8", errors="replace")
                    for p in list(theme_dir.rglob("*.html")) + list(theme_dir.rglob("*.php")))

    checks = {
        "full-width-template": (bool(shape["page_templates"]),
                                f"page templates: {shape['page_templates'] or 'NONE'}"),
        "custom-menu": (has_nav or nav_block,
                        f"register_nav_menus={has_nav}, wp:navigation={nav_block}"),
        "featured-images": ("post-thumbnails" in supports, "add_theme_support"),
        # add_theme_support only proves the control exists. Whether anything
        # renders the uploaded logo is the Custom logo section below.
        "custom-logo": ("custom-logo" in supports,
                        "add_theme_support - see Custom logo for whether it renders"),
        "custom-header": ("custom-header" in supports, "add_theme_support"),
        "custom-background": ("custom-background" in supports, "add_theme_support"),
        "block-patterns": (bool(shape["patterns"]), f"{len(shape['patterns'])} patterns"),
        "style-variations": (bool(shape["styles"]), f"{len(shape['styles'])} variations"),
        "full-site-editing": (shape["block"], f"templates/={shape['block']}"),
        # A classic theme declares wide support with add_theme_support( 'align-wide' );
        # only a block theme puts it in theme.json.
        "wide-blocks": ("align-wide" in supports or bool(layout.get("wideSize")),
                        f"align-wide support={'align-wide' in supports}, "
                        f"layout.wideSize={layout.get('wideSize')}"),
        "block-styles": (bool(re.search(r"register_block_style\s*\(", php)),
                         "register_block_style"),
        "editor-style": (bool(re.search(r"add_editor_style\s*\(", php)), "add_editor_style"),
        "custom-colors": (bool(palette), f"{len(palette)} palette entries"),
        "translation-ready": (bool(re.search(r"load_theme_textdomain\s*\(", php))
                              or bool(header.get("text domain")),
                              "text domain / load_theme_textdomain"),
    }

    rows = []
    for tag in [t.strip() for t in header.get("tags", "").split(",") if t.strip()]:
        if tag in checks:
            ok, why = checks[tag]
            rows.append((tag, "OK" if ok else "NO EVIDENCE", why))
        else:
            rows.append((tag, "manual", "subject or layout tag - judge by hand"))
    return rows


SCRIPT_BLOCK = re.compile(r"<script\b.*?</script\s*>", re.S | re.I)


def prefix_report(theme_dir, header):
    """Declared PHP functions, and whether each carries a plausible prefix.

    Inline <script> blocks are stripped first: a JS `function foo()` sitting in a
    PHP file is not in the PHP public namespace and must not be reported as one.
    """
    slug_bits = {b for b in re.split(r"[-_]",
                 (header.get("text domain") or theme_dir.name).lower()) if b}
    funcs = []
    for php in theme_dir.rglob("*.php"):
        text = SCRIPT_BLOCK.sub("", php.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M):
            funcs.append((m.group(1), str(php.relative_to(theme_dir))))
    unprefixed, offslug = [], []
    for name, where in funcs:
        prefix = name.split("_")[0].lower()
        if "_" not in name or len(prefix) < 4:
            unprefixed.append((name, where))
        elif not any(b in name.lower() for b in slug_bits):
            offslug.append((name, where))
    return funcs, unprefixed, offslug


def text_domains(theme_dir):
    pat = re.compile(r"(?:__|_e|_x|_n|esc_html__|esc_attr__|esc_html_e|esc_attr_e)\s*\("
                     r"[^,]+,\s*['\"]([a-z0-9-]+)['\"]", re.I)
    found = {}
    for f in list(theme_dir.rglob("*.php")) + list(theme_dir.rglob("*.html")):
        for d in pat.findall(f.read_text(encoding="utf-8", errors="replace")):
            found[d] = found.get(d, 0) + 1
    return found


def remote_hosts(theme_dir):
    skip = (".w3.org", ".gnu.org", "wordpress.org", "schemas.wp.org")
    hosts = {}
    for ext in ("*.php", "*.html", "*.css", "*.js"):
        for f in theme_dir.rglob(ext):
            if f.name == "style.css" and f.parent == theme_dir:
                continue  # header URIs are expected
            for host in REMOTE_PATTERN.findall(f.read_text(encoding="utf-8", errors="replace")):
                host = host.lower()
                if host.endswith(skip):
                    continue
                hosts.setdefault(host, set()).add(str(f.relative_to(theme_dir)))
    return hosts


def grep_hits(theme_dir):
    hits = []
    for php in theme_dir.rglob("*.php"):
        lines = php.read_text(encoding="utf-8", errors="replace").splitlines()
        for label, pattern, note in GREPS:
            for i, line in enumerate(lines, 1):
                if pattern.search(line):
                    hits.append((label, f"{php.relative_to(theme_dir)}:{i}",
                                 line.strip()[:120], note))
    return hits


def licence_mentions(theme_dir):
    readme = theme_dir / "readme.txt"
    if not readme.is_file():
        return ["readme.txt MISSING"]
    text = readme.read_text(encoding="utf-8", errors="replace")
    notes = []
    if re.search(r"pexels", text, re.I):
        notes.append(
            f"Pexels referenced ({len(re.findall(r'CC0', text, re.I))} CC0 mentions). "
            "Only CC0 is accepted. Check each photo's License link: "
            "/creative-commons-images/ is CC0, /license/ is not.")
    for site in ("unsplash", "freepik", "shutterstock", "envato", "pixabay"):
        if re.search(site, text, re.I):
            notes.append(f"{site} referenced - check it against the accepted list")
    if not re.search(r"(copyright|licen[cs]e)", text, re.I):
        notes.append("no copyright or licence section found in readme.txt")
    return notes or ["no stock-image sources flagged"]


def screenshot_info(theme_dir):
    shots = [theme_dir / n for n in ("screenshot.png", "screenshot.jpg", "screenshot.jpeg")]
    present = [s for s in shots if s.is_file()]
    if not present:
        return "screenshot MISSING (looked for .png, .jpg, .jpeg)"
    if len(present) > 1:
        return ("more than one screenshot file: "
                + ", ".join(s.name for s in present) + " - only one should ship")
    shot = present[0]
    rc, out, _ = run(["file", "-b", str(shot)])
    note = out if rc == 0 else "unknown"
    warn = ""
    # file(1) reports a JPEG's DPI as "density 72x72" before the real dimensions,
    # so drop that before looking for the size.
    sizes = re.findall(r"(\d+)\s*x\s*(\d+)", re.sub(r"density\s+\d+x\d+", "", note))
    if sizes:
        w, h = max(((int(a), int(b)) for a, b in sizes), key=lambda d: d[0] * d[1])
        if w > 1200 or h > 900:
            warn = "  <-- OVER the 1200x900 limit"
        elif round(w / h, 3) != round(4 / 3, 3):
            warn = "  <-- not 4:3"
    return (f"{note}, {shot.stat().st_size:,} bytes{warn}"
            "  (contents still need a human look)")


def minified_sources(theme_dir):
    """Every minified file, and whether its unminified original ships with it.

    Required items: "When minified scripts or files are used, the original files
    must also be included in the theme folder." Two ways a theme misses it - a
    .min file with no original, and a file that is minified without saying so in
    its name.
    """
    missing, paired, unnamed = [], [], []

    for f in list(theme_dir.rglob("*.min.css")) + list(theme_dir.rglob("*.min.js")):
        rel = f.relative_to(theme_dir)
        want = f.name.replace(".min.", ".")
        sibling = f.with_name(want)
        if sibling.is_file():
            paired.append((str(rel), str(sibling.relative_to(theme_dir))))
            continue
        elsewhere = [p for p in theme_dir.rglob(want) if p != sibling]
        if elsewhere:
            paired.append((str(rel), str(elsewhere[0].relative_to(theme_dir))))
        else:
            missing.append(str(rel))

    for ext in ("*.css", "*.js"):
        for f in theme_dir.rglob(ext):
            if ".min." in f.name:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            if len(text) < 2048:
                continue
            lines = text.splitlines() or [text]
            if sum(len(ln) for ln in lines) / len(lines) > 500:
                unnamed.append((str(f.relative_to(theme_dir)), len(lines)))

    return missing, paired, unnamed

# --------------------------------------------------------------------------
# live checks
# --------------------------------------------------------------------------

def crawl(project, slug):
    """Activate the theme, hit each path, return (results, debug_log_text)."""
    debug_log = project / "wp-content" / "debug.log"
    debug_log.unlink(missing_ok=True)
    wp(project, ["theme", "activate", slug])
    base = site_url(project).rstrip("/")
    results = []
    for path in CRAWL_PATHS:
        _, out, _ = run(["curl", "-ks", "-o", "/dev/null", "-w", "%{http_code}", base + path])
        results.append((out or "ERR", path))
    log = debug_log.read_text(encoding="utf-8", errors="replace") if debug_log.is_file() else ""
    return results, log


def theme_check(project, slug):
    _, out, err = run(["ddev", "wp", "theme-check", "run", slug], cwd=project)
    return out or err or "(no output - is the theme-check plugin active?)"


LOGO_CALLS = (
    ("the_custom_logo", re.compile(r"\bthe_custom_logo\s*\(")),
    ("get_custom_logo", re.compile(r"\bget_custom_logo\s*\(")),
    ("custom_logo theme mod", re.compile(r"get_theme_mod\s*\(\s*['\"]custom_logo['\"]")),
)

LOGO_STEM = "sweep-logo-test"


def _write_test_png(path, width=600, height=200):
    """A distinctively named PNG, generated here so the tool needs no fixture."""
    import struct
    import zlib

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    row = bytes([255, 0, 160]) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b""))


def custom_logo_test(project, slug, theme_dir, header):
    """Does an uploaded custom logo actually render, and does the site name?

    `add_theme_support( 'custom-logo' )` and the `custom-logo` tag say the
    Customizer control exists; neither says anything renders. This uploads a
    logo, sets the theme mod and looks for it in the front-page markup, because
    a theme can declare the support, pass Theme Check, carry the tag and still
    print a hardcoded image from its own directory on every install.

    Mutates the site: imports an attachment and sets a theme mod, then removes
    both. `theme-sweep.py reset` restores the baseline if anything is left over.
    """
    php = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in theme_dir.rglob("*.php"))
    calls = [name for name, pat in LOGO_CALLS if pat.search(php)]
    supported = bool(re.search(
        r"add_theme_support\s*\(\s*['\"]custom-logo['\"]", php))
    tagged = "custom-logo" in [t.strip() for t in header.get("tags", "").split(",")]

    result = {
        "declared": supported,
        "tagged": tagged,
        "calls": calls,
        "ran": False,
        "uploaded_hits": None,
        "theme_image_hits": [],
        "title_in_body": None,
        "notes": [],
    }

    if not (supported or tagged):
        result["notes"].append(
            "no custom-logo support and no custom-logo tag - render test skipped")
        return result

    tmp = project / "review-zips"
    tmp.mkdir(exist_ok=True)
    png = tmp / f"{LOGO_STEM}.png"
    _write_test_png(png)

    attachment = ""
    try:
        attachment = wp(project, ["media", "import",
                                  f"review-zips/{png.name}", "--porcelain"]).strip()
        if not attachment.isdigit():
            result["notes"].append(
                f"could not import the test image, render test skipped "
                f"(wp media import said: {attachment or 'nothing'!r})")
            return result

        wp(project, ["theme", "activate", slug])
        wp(project, ["theme", "mod", "set", "custom_logo", attachment])

        base = site_url(project).rstrip("/")
        _, html, _ = run(["curl", "-ks", base + "/"])
        result["ran"] = True
        result["uploaded_hits"] = html.count(LOGO_STEM)

        # What it printed instead: any image referenced out of the theme folder.
        for src in set(re.findall(
                r"/wp-content/themes/" + re.escape(slug)
                + r"/([^\"'\s>]+\.(?:png|jpe?g|svg|webp|avif|gif))", html, re.I)):
            result["theme_image_hits"].append((src, html.count(src)))
        result["theme_image_hits"].sort(key=lambda r: -r[1])

        # The other half of Site Identity: is the site's own name printed at all?
        # Counted in visible text only - a theme that uses the site name as the
        # logo's alt attribute scores a hit per image otherwise, which says
        # nothing about whether a visitor can read the site's name.
        # Matched on word boundaries: the unit-test data carries an author
        # called "Theme Reviewer", so a site titled "Theme Review" scores nine
        # substring hits that have nothing to do with the theme.
        name = wp(project, ["option", "get", "blogname"]).strip()
        if name:
            body = html.split("</head>", 1)[-1]
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", body))
            word = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
            result["title_in_body"] = (name, len(word.findall(text)),
                                       len(word.findall(body)))
    finally:
        wp(project, ["theme", "mod", "remove", "custom_logo"])
        if attachment.isdigit():
            wp(project, ["post", "delete", attachment, "--force"])
        png.unlink(missing_ok=True)

    return result


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_fetch(project, slug, version):
    zips = project / "review-zips"
    zips.mkdir(exist_ok=True)
    target = zips / f"{slug}.{version}.zip"
    url = ZIP_URL.format(slug=slug, version=version)
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, target)
    print(f"saved {target} ({target.stat().st_size:,} bytes)")

    dest = project / "wp-content" / "themes" / slug
    if dest.exists():
        shutil.rmtree(dest)
    staging = zips / f".extract-{slug}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(target) as z:
        z.extractall(staging)
    inner = staging / slug
    shutil.move(str(inner if inner.is_dir() else staging), str(dest))
    shutil.rmtree(staging, ignore_errors=True)
    print(f"installed {dest}")


def cmd_baseline(project):
    run(["ddev", "snapshot", "--name", SNAPSHOT], cwd=project, check=True)
    print(f"snapshot '{SNAPSHOT}' taken")


def cmd_reset(project):
    run(["ddev", "snapshot", "restore", SNAPSHOT], cwd=project, check=True)
    print(f"restored '{SNAPSHOT}'")


def cmd_check(project, slug):
    theme_dir = project / "wp-content" / "themes" / slug
    if not theme_dir.is_dir():
        sys.exit(f"theme not installed: {theme_dir}")

    header = parse_header(theme_dir / "style.css")
    shape = theme_shape(theme_dir)
    version = header.get("version", "0.0.0")
    funcs, unprefixed, offslug = prefix_report(theme_dir, header)
    domains = text_domains(theme_dir)
    hosts = remote_hosts(theme_dir)
    hits = grep_hits(theme_dir)
    crawl_results, debug_log = crawl(project, slug)
    tc = theme_check(project, slug)
    logo = custom_logo_test(project, slug, theme_dir, header)

    out = [
        f"# {header.get('theme name', slug)} {version} - mechanical sweep",
        "",
        f"Generated: {date.today().isoformat()} by theme-sweep.py",
        f"Theme: `{slug}`, {'block (FSE)' if shape['block'] else 'classic'}",
        "",
        "Facts and candidates only. Deciding what is a finding is the reviewer's job.",
        "",
        "## Header",
        "",
    ]
    for k in ("requires at least", "tested up to", "requires php", "version",
              "license", "text domain"):
        if k in header:
            out.append(f"- {k}: `{header[k]}`")

    kind = "block (FSE)" if shape["block"] else "classic"
    out += ["", "## Tags vs features", "",
            f"This is a **{kind}** theme. Read every row against that: the same "
            "feature is declared differently in each, so a NO EVIDENCE here means "
            "the test below found nothing, not that the feature is absent. Open "
            "the file before calling any row a finding.", "",
            "| Tag | Evidence | Detail |", "|---|---|---|"]
    for tag, verdict, why in tag_evidence(theme_dir, header, shape):
        out.append(f"| `{tag}` | {verdict} | {why} |")

    out += ["", "## Custom logo", "",
            "A logo was uploaded and set as the `custom_logo` theme mod, then the "
            "front page was fetched. `add_theme_support` and the tag only prove the "
            "Customizer control exists; this is whether anything renders what the "
            "user puts in it.", ""]
    out.append(f"- `add_theme_support( 'custom-logo' )`: {'yes' if logo['declared'] else 'NO'}")
    out.append(f"- `custom-logo` in the tags: {'yes' if logo['tagged'] else 'no'}")
    out.append("- renders it: " + (", ".join(f"`{c}`" for c in logo["calls"])
                                   if logo["calls"] else
                                   "**NO CALL FOUND** - no `the_custom_logo()`, "
                                   "`get_custom_logo()` or `custom_logo` theme mod "
                                   "read anywhere in the theme"))
    for note in logo["notes"]:
        out.append(f"- {note}")
    if logo["ran"]:
        found = logo["uploaded_hits"]
        out.append(f"- uploaded logo in the front-page markup: **{found} occurrence(s)**"
                   + ("" if found else "  <-- the uploaded file does not appear at all"))
        if logo["theme_image_hits"]:
            out.append("- images printed from the theme's own folder instead:")
            out += [f"  - `{src}` x{n}" for src, n in logo["theme_image_hits"][:6]]
        if logo["title_in_body"]:
            name, visible, anywhere = logo["title_in_body"]
            out.append(f"- site title `{name}` in visible front-page text: "
                       f"{visible} occurrence(s), and {anywhere} in the markup "
                       "including attributes"
                       + ("" if visible else "  <-- the site's own name is never "
                                             "shown to a visitor"))

    out += ["", "## Theme Check", "", "```", tc, "```", "", "## Crawl with WP_DEBUG", ""]
    for code, path in crawl_results:
        out.append(f"- `{code}` {path}")
    out += ["", "**debug.log:**"]
    if debug_log.strip():
        counts = {}
        for m in re.finditer(r"PHP (Notice|Warning|Deprecated|Fatal error):\s*(.+?)(?: in /|$)",
                             debug_log):
            key = f"{m.group(1)}: {m.group(2)[:90]}"
            counts[key] = counts.get(key, 0) + 1
        out.append("")
        if counts:
            for key, n in sorted(counts.items(), key=lambda x: -x[1]):
                out.append(f"- {n}x {key}")
        else:
            out.append("no notices, warnings or deprecations - the log holds only "
                       "these lines, which are not the theme's:")
            out += [f"  - `{ln.strip()}`" for ln in debug_log.splitlines()[:6] if ln.strip()]
    else:
        out.append("")
        out.append("empty - no notices, warnings or deprecations on the crawled paths")

    out += ["", "## Prefixing", "", f"- {len(funcs)} function declarations"]
    if unprefixed:
        out.append("- **no prefix, or shorter than four letters** "
                   "(candidate breach - confirm it is PHP, not inline JS):")
        out += [f"  - `{n}` in {w}" for n, w in unprefixed]
    else:
        out.append("- all functions carry a prefix of four or more letters")
    if offslug:
        out.append(f"- {len(offslug)} prefixed, but not with the theme slug. Either "
                   "leftover naming from a rename, or a prefix generic enough that it "
                   "is not unique - the required items ask for a unique one:")
        out += [f"  - `{n}` in {w}" for n, w in offslug[:8]]

    out += ["", "## Text domain", ""]
    if len(domains) == 1 and header.get("text domain") in domains:
        out.append(f"- consistent: `{list(domains)[0]}` ({sum(domains.values())} uses)")
    else:
        out.append(f"- declared `{header.get('text domain')}`, found in code: {domains}")

    out += ["", "## Remote hosts referenced", ""]
    if hosts:
        for host, files in sorted(hosts.items()):
            flag = "" if host in REMOTE_ALLOWED else "  <-- not the Google Fonts exception"
            out.append(f"- `{host}`{flag} - {', '.join(sorted(files)[:3])}")
    else:
        out.append("- none")

    out += ["", "## Patterns worth a look", ""]
    if hits:
        for label, where, line, note in hits[:40]:
            out.append(f"- **{label}** `{where}` - {note}")
            out.append(f"  - `{line}`")
    else:
        out.append("- nothing matched")

    out += ["", "## Minified files vs their sources", ""]
    missing, paired, unnamed = minified_sources(theme_dir)
    if missing:
        out.append("- **minified with no original in the theme** (candidate breach - "
                   "the required items ask for the original file alongside it):")
        out += [f"  - `{m}`" for m in missing]
    if unnamed:
        out.append("- **minified but not named `.min`**, so the pairing above cannot "
                   "see it - confirm by opening it:")
        out += [f"  - `{m}` ({n} lines)" for m, n in unnamed]
    if paired:
        out.append(f"- {len(paired)} minified file(s) paired with an original:")
        out += [f"  - `{m}` -> `{s}`" for m, s in paired[:8]]
    if not (missing or unnamed or paired):
        out.append("- no minified files found")

    out += ["", "## Bundled resources", ""]
    out += [f"- {n}" for n in licence_mentions(theme_dir)]
    out += ["", f"- screenshot: {screenshot_info(theme_dir)}"]

    out += ["", "## Still needs a human", "",
            "- Open the site and look at it. Rendering catches what greps cannot.",
            "- A long site title and a long post title at narrow widths.",
            "- Keyboard focus order, and any modal's focus trap.",
            "- The screenshot against what the theme actually renders.",
            "- Every bundled image's licence, one at a time.",
            ""]

    reports = project / "reviews"
    reports.mkdir(exist_ok=True)
    path = reports / f"{slug}-{version}-sweep.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"written {path}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="DDEV theme-review project root")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch"); f.add_argument("slug"); f.add_argument("version")
    c = sub.add_parser("check"); c.add_argument("slug")
    r = sub.add_parser("run"); r.add_argument("slug"); r.add_argument("version")
    sub.add_parser("reset")
    sub.add_parser("baseline")

    args = ap.parse_args()
    project = Path(args.project).resolve()
    if not (project / "wp-content").is_dir():
        sys.exit(f"not a WordPress root: {project}")

    if args.cmd == "fetch":
        cmd_fetch(project, args.slug, args.version)
    elif args.cmd == "check":
        cmd_check(project, args.slug)
    elif args.cmd == "run":
        cmd_fetch(project, args.slug, args.version)
        cmd_reset(project)
        cmd_check(project, args.slug)
    elif args.cmd == "reset":
        cmd_reset(project)
    elif args.cmd == "baseline":
        cmd_baseline(project)


if __name__ == "__main__":
    main()
