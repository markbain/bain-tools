#!/usr/bin/env python3
"""site-inventory - list every page of a site, with its parentage, as the
starting document for an information architecture review.

Run it against PRODUCTION. Only the live site has an accurate structure; a
local copy is a snapshot of whenever it was pulled, and clients edit live.

Three sources, in order of how much they can be trusted:

  --wp PATH       WP-CLI against a local install. True parentage from
                  post_parent, real titles, optional page templates. Use
                  --wp-cmd for a site behind DDEV, Vagrant or SSH.
  --url URL       The REST API at /wp-json/wp/v2/. True parentage.
                  Falls back to the XML sitemap when the API is closed.
  --sitemap SRC   An XML sitemap, by URL or local file. Hierarchy is
                  INFERRED from path depth, which is a guess, not a fact.

Output is a nested Markdown list by default, ready to paste into an IA
session; --format csv gives one row per page for joining traffic data to.
"""

import argparse
import csv
import html
import io
import json
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

UA = "site-inventory/1.0"
TIMEOUT = 20


# ---------------------------------------------------------------- helpers

def die(msg):
    sys.stderr.write("site-inventory: %s\n" % msg)
    raise SystemExit(1)


def warn(msg):
    sys.stderr.write("site-inventory: %s\n" % msg)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(), dict(r.headers)


def read_source(src):
    """A URL or a local path, returned as bytes."""
    if src.startswith("http://") or src.startswith("https://"):
        return fetch(src)[0]
    with open(src, "rb") as fh:
        return fh.read()


def path_of(url):
    p = urlparse(url).path or "/"
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1 and not p.endswith("/") and "." not in p.rsplit("/", 1)[-1]:
        p += "/"
    return p


def title_from_path(path):
    seg = [s for s in path.strip("/").split("/") if s]
    if not seg:
        return "Home"
    return seg[-1].replace("-", " ").replace("_", " ").strip().capitalize()


# ------------------------------------------------------------------ model

class Page(object):
    def __init__(self, pid, title, path, parent=None, template="",
                 status="publish", modified="", source=""):
        self.id = pid
        self.title = title
        self.path = path
        self.parent = parent
        self.template = template
        self.status = status
        self.modified = modified
        self.source = source
        self.children = []
        self.depth = 0
        self.kind = "page"
        self.menus = []        # [(menu name, depth in that menu, parent label)]


def tree_from_parents(pages):
    """Pages carrying a real parent id."""
    by_id = {p.id: p for p in pages}
    roots = []
    for p in pages:
        parent = by_id.get(p.parent) if p.parent else None
        if parent is not None and parent is not p:
            parent.children.append(p)
        else:
            roots.append(p)
    return roots


def tree_from_paths(pages):
    """No parentage available: infer it from the URL path. A guess."""
    by_path = {p.path: p for p in pages}
    roots = []
    for p in pages:
        seg = [s for s in p.path.strip("/").split("/") if s]
        parent = None
        while len(seg) > 1:
            seg = seg[:-1]
            cand = "/" + "/".join(seg) + "/"
            if cand in by_path and by_path[cand] is not p:
                parent = by_path[cand]
                break
        if parent is not None:
            parent.children.append(p)
        else:
            roots.append(p)
    return roots


def order(roots, depth=0):
    """Depth-first, home first, then alphabetical by path."""
    out = []
    for p in sorted(roots, key=lambda x: (x.path != "/", x.path)):
        p.depth = depth
        out.append(p)
        out.extend(order(p.children, depth + 1))
    return out


# ---------------------------------------------------------------- sources

def from_wp(path, post_types, statuses, want_templates, wp_cmd):
    fields = "ID,post_title,post_name,post_parent,post_status,post_modified,url"
    base = shlex.split(wp_cmd)
    path_arg = [] if path in (".", "") else ["--path=" + path]
    pages = []
    for ptype in post_types:
        cmd = base + ["post", "list"] + path_arg + [
               "--post_type=" + ptype,
               "--post_status=" + ",".join(statuses),
               "--posts_per_page=-1",
               "--fields=" + fields, "--format=json"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except FileNotFoundError:
            die("%s not found on PATH" % base[0])
        if out.returncode != 0:
            die("wp-cli failed for post_type %s:\n%s" % (ptype, out.stderr.strip()))
        for row in json.loads(out.stdout or "[]"):
            pages.append(Page(
                pid=int(row["ID"]),
                title=html.unescape(row["post_title"] or row["post_name"]),
                path=path_of(row.get("url") or "/" + row["post_name"] + "/"),
                parent=int(row["post_parent"]) or None,
                status=row["post_status"],
                modified=(row.get("post_modified") or "")[:10],
                source=ptype,
            ))

    if want_templates:
        for p in pages:
            cmd = base + ["post", "meta", "get", str(p.id),
                          "_wp_page_template"] + path_arg
            r = subprocess.run(cmd, capture_output=True, text=True)
            val = r.stdout.strip() if r.returncode == 0 else ""
            p.template = "" if val in ("", "default") else val

    return pages, True


def from_rest(base, post_types, statuses):
    pages = []
    for ptype in post_types:
        endpoint = {"page": "pages", "post": "posts"}.get(ptype, ptype)
        page_no, got_any = 1, False
        while True:
            url = urljoin(base, "/wp-json/wp/v2/%s?per_page=100&page=%d"
                                "&_fields=id,parent,slug,link,title,status,modified,template"
                          % (endpoint, page_no))
            try:
                body, _ = fetch(url)
            except urllib.error.HTTPError as e:
                if e.code == 400 and page_no > 1:
                    break          # ran off the end of the pagination
                if page_no == 1:
                    return None, False
                break
            except urllib.error.URLError as e:
                die("could not reach %s (%s)" % (url, e))
            rows = json.loads(body.decode("utf-8"))
            if not rows:
                break
            got_any = True
            for row in rows:
                if statuses and row.get("status") not in statuses:
                    continue
                pages.append(Page(
                    pid=int(row["id"]),
                    title=html.unescape(
                        (row.get("title") or {}).get("rendered") or row["slug"]),
                    path=path_of(row.get("link") or "/" + row["slug"] + "/"),
                    parent=int(row.get("parent") or 0) or None,
                    template=row.get("template") or "",
                    status=row.get("status", "publish"),
                    modified=(row.get("modified") or "")[:10],
                    source=ptype,
                ))
            if len(rows) < 100:
                break
            page_no += 1
        if not got_any and page_no == 1 and not pages:
            return None, False
    return pages, True


def sitemap_urls(src, seen=None):
    """Follow a sitemap or sitemap index and return every <loc>."""
    seen = seen if seen is not None else set()
    if src in seen:
        return []
    seen.add(src)
    try:
        body = read_source(src)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        warn("could not read %s (%s)" % (src, e))
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        die("%s is not valid XML (%s)" % (src, e))

    tag = root.tag.rsplit("}", 1)[-1]
    locs = [el.text.strip() for el in root.iter()
            if el.tag.rsplit("}", 1)[-1] == "loc" and el.text]
    if tag == "sitemapindex":
        out = []
        for loc in locs:
            out.extend(sitemap_urls(loc, seen))
        return out
    return locs


def from_sitemap(src):
    urls = sitemap_urls(src)
    if not urls:
        die("no URLs found in %s" % src)
    pages, seen = [], set()
    for i, u in enumerate(sorted(set(urls))):
        p = path_of(u)
        if p in seen:
            continue
        seen.add(p)
        pages.append(Page(pid=i + 1, title=title_from_path(p), path=p,
                          source="sitemap"))
    return pages, False



# -------------------------------------------------------------- navigation
#
# A menu is not the page tree. WordPress menu items carry their own
# _menu_item_menu_item_parent, so a menu can nest two pages that have no
# parent-child relationship at all, and can leave out pages that do. The two
# have to be read separately or the IA is built on a guess.
#
# The REST menu endpoints (/wp/v2/menus, /wp/v2/menu-items) need an
# authenticated user with edit_theme_options, so they answer 401 on a site you
# are only visiting. That leaves the rendered HTML, which has the advantage of
# being what a visitor actually sees, and wp-cli, which is authoritative.


class MenuScraper(HTMLParser):
    """Pulls navigation out of a rendered page, by what it looks like rather
    than by what built it.

    WordPress's own wp_nav_menu gives each menu a <ul id="menu-{slug}">, but
    plenty of sites do not use it: a mega-menu plugin, a page builder or hand
    written markup will all produce navigation with no such id. So any list of
    links inside <nav>, <header> or <footer> counts, whatever its classes.

    This reads the front end deliberately. The front end is the structure the
    client and their visitors actually experience; the database is what the
    site is made of. Where the two disagree, that disagreement is the finding.
    """

    LANDMARKS = ("nav", "header", "footer")

    def __init__(self):
        HTMLParser.__init__(self)
        self.menus = []          # [(name, [(depth, label, href), ...])]
        self.landmarks = []      # open <nav>/<header>/<footer> descriptors
        self.menu_name_hint = None
        self.items = []
        self.ul_depth = None     # None when not inside a captured list
        self.in_a = False
        self.label = []
        self.pending = None

    # -- helpers

    @staticmethod
    def _describe(tag, a):
        bits = a.get("id") or ""
        if not bits:
            cls = (a.get("class") or "").split()
            bits = cls[0] if cls else ""
        return (bits or tag)

    def _is_menu_list(self, a):
        mid = a.get("id") or ""
        cls = (a.get("class") or "").split()
        return mid.startswith("menu-") or any("menu" in c for c in cls) \
            or any("nav" in c for c in cls)

    # -- parsing

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.LANDMARKS:
            self.landmarks.append(self._describe(tag, a))
            return

        if tag == "ul":
            if self.ul_depth is None:
                if self._is_menu_list(a) or self.landmarks:
                    self.menu_name_hint = (a.get("id") or "").strip() \
                        or (self.landmarks[-1] if self.landmarks else "") \
                        or (a.get("class") or "")
                    self.items = []
                    self.ul_depth = 0
            else:
                self.ul_depth += 1

        elif tag == "a" and self.ul_depth is not None:
            self.in_a = True
            self.label = []
            self.pending = (self.ul_depth, a.get("href") or "")

    def handle_data(self, data):
        if self.in_a:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag in self.LANDMARKS:
            if self.landmarks:
                self.landmarks.pop()
            return

        if tag == "a" and self.in_a:
            self.in_a = False
            depth, href = self.pending
            label = " ".join("".join(self.label).split())
            if label and href and not href.startswith("#"):
                self.items.append((depth, label, href))

        elif tag == "ul" and self.ul_depth is not None:
            if self.ul_depth == 0:
                if self.items:
                    self.menus.append((self.menu_name_hint, self.items))
                self.items, self.ul_depth, self.menu_name_hint = [], None, None
            else:
                self.ul_depth -= 1


def menu_name(menu_id):
    name = re.sub(r"^(menu-|nav-|main-)", "", menu_id or "menu")
    name = re.sub(r"-\d+$", "", name)
    return name.replace("-", " ").strip().title() or "Menu"


def normalise_href(href, site):
    """Same-host absolute URLs become paths; everything else is left alone."""
    if href.startswith(("http://", "https://")):
        host = urlparse(site).netloc
        parts = urlparse(href)
        if host and parts.netloc != host:
            return href
        tail = parts.path or "/"
        if parts.query:
            return tail + "?" + parts.query
        return path_of(tail)
    return href


def menus_from_html(url):
    body = read_source(url)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    sc = MenuScraper()
    sc.feed(text)

    out, seen = [], set()
    for mid, items in sc.menus:
        key = tuple(sorted(set(i[2] for i in items)))
        if key in seen or len(items) < 2:
            continue   # the same menu rendered twice, mobile and desktop
        host = urlparse(url).netloc
        if host and all(i[2].startswith(("http://", "https://")) and
                        urlparse(i[2]).netloc != host for i in items):
            continue   # a list of outbound links, not navigation
        seen.add(key)
        out.append((menu_name(mid),
                    [(d, l, normalise_href(h, url)) for d, l, h in items]))
    return out


def menus_from_wp(path, wp_cmd):
    base = shlex.split(wp_cmd)
    path_arg = [] if path in (".", "") else ["--path=" + path]

    r = subprocess.run(base + ["menu", "list", "--format=json"] + path_arg,
                       capture_output=True, text=True)
    if r.returncode != 0:
        die("wp menu list failed:\n%s" % r.stderr.strip())

    out = []
    for menu in json.loads(r.stdout or "[]"):
        slug = menu.get("slug") or menu.get("term_id")
        ri = subprocess.run(base + ["menu", "item", "list", str(slug),
                                    "--format=json"] + path_arg,
                            capture_output=True, text=True)
        if ri.returncode != 0:
            warn("could not list items for menu %s" % slug)
            continue
        rows = json.loads(ri.stdout or "[]")
        by_id = {str(x.get("db_id")): x for x in rows}

        def depth_of(row, guard=0):
            parent = str(row.get("menu_item_parent") or "0")
            if parent in ("0", "", "None") or guard > 10:
                return 0
            up = by_id.get(parent)
            return 0 if up is None else depth_of(up, guard + 1) + 1

        items = [(depth_of(x), x.get("title") or "",
                  normalise_href(x.get("url") or "", x.get("url") or ""))
                 for x in rows]
        out.append((menu.get("name") or menu_name(str(slug)), items))
    return out


BODY_CLASS = re.compile(r'<body[^>]*class="([^"]*)"', re.I)


def classify(url):
    """What kind of thing renders at a URL.

    A menu points at destinations, not at post types. A taxonomy archive is
    not a page to WordPress and is entirely a page to the client, who put it
    in the menu. So the inventory names what renders rather than leaving the
    destination out.
    """
    try:
        body, _ = fetch(url)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return "unreachable"
    try:
        text = body.decode("utf-8", "replace")
    except Exception:
        return "unknown"
    m = BODY_CLASS.search(text)
    classes = (m.group(1) if m else "").split()

    if any(c.startswith("search") for c in classes):
        return "search"
    for c in classes:
        if c.startswith("tax-"):
            return "taxonomy archive"
        if c.startswith("term-"):
            return "taxonomy archive"
    if "category" in classes or any(c.startswith("category-") for c in classes):
        return "category archive"
    if "archive" in classes:
        return "archive"
    for c in classes:
        if c.startswith("single-") and c != "single-format-standard":
            return c.replace("single-", "") + " entry"
    if "single" in classes:
        return "post"
    if "page" in classes or any(c.startswith("page-id-") for c in classes):
        return "page"
    if "home" in classes or "blog" in classes:
        return "posts archive"
    return "unknown"


def add_menu_destinations(pages, menus, site, probe=True):
    """Menu targets the page query never saw, added as destinations.

    Placed under the deepest page whose path is a prefix of theirs, which is
    where a visitor would put them.
    """
    known = {p.path for p in pages}
    by_path = {p.path: p for p in pages}
    added = []
    next_id = max([p.id for p in pages] or [0]) + 1

    for _, items in menus:
        for _depth, label, href in items:
            if not href.startswith("/"):
                continue
            path = path_of(href) if "?" not in href else href
            if path in known:
                continue
            known.add(path)
            kind = classify(urljoin(site, href)) if (probe and site) else "not a page"
            parent = None
            seg = [x for x in path.strip("/").split("/") if x]
            while len(seg) > 1:
                seg = seg[:-1]
                cand = "/" + "/".join(seg) + "/"
                if cand in by_path:
                    parent = by_path[cand]
                    break
            node = Page(pid=next_id, title=label, path=path,
                        parent=parent.id if parent else None,
                        template="", status="menu", source=kind)
            node.kind = kind
            next_id += 1
            pages.append(node)
            by_path[path] = node
            added.append(node)
    return added


def tag_menu_membership(pages, menus):
    """Record, on each destination, which menus hold it and where.

    The inventory is the flat list. The page tree and the menus are two views
    over it, and a destination can sit at a different depth in each.
    """
    by_path = {p.path: p for p in pages}
    for name, items in menus:
        stack = []
        for depth, label, href in items:
            while stack and stack[-1][0] >= depth:
                stack.pop()
            parent_label = stack[-1][1] if stack else ""
            stack.append((depth, label))
            target = by_path.get(href) or by_path.get(path_of(href)
                                                      if href.startswith("/") else href)
            if target is not None:
                target.menus.append((name, depth, parent_label, label))


def render_navigation(menus, site=""):
    """The ## Navigation half of the IA source document."""
    if not menus:
        return ""
    host = urlparse(site).netloc if site else ""
    buf = ["", "## Navigation", ""]
    for name, items in menus:
        buf.append("### %s" % name)
        for depth, label, href in items:
            target = href
            if href.startswith("http"):
                parts = urlparse(href)
                target = path_of(href) if (not host or parts.netloc == host) else href
            buf.append("%s- %s -> `%s`" % ("  " * depth, label, target))
        buf.append("")
    return "\n".join(buf)

# ----------------------------------------------------------------- output

def render_markdown(rows, title, trusted_parents, status_tag):
    out = io.StringIO()
    if title:
        out.write("# %s\n\n" % title)
    out.write("## Structure\n\n")
    for p in rows:
        bits = ["%s- %s `%s`" % ("  " * p.depth, p.title, p.path)]
        if p.template:
            bits.append("{%s}" % p.template)
        elif p.kind != "page":
            bits.append("{%s}" % p.kind)
        if status_tag:
            bits.append("[%s]" % status_tag)
        out.write(" ".join(bits) + "\n")
    if not trusted_parents:
        out.write("\nHierarchy inferred from URL path depth, not from the site's "
                  "own parentage. Check it before relying on it.\n")
    return out.getvalue()


def render_csv(rows, by_id=None):
    """One row per destination. The inventory itself: structure and navigation
    are both views over this, so each row carries its place in each."""
    by_id = by_id or {}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["path", "title", "kind", "template", "status", "modified",
                "tree_depth", "tree_parent", "in_menus", "menu_depth",
                "menu_parent", "menu_label",
                "sessions_12mo", "entrances_12mo", "impressions_12mo",
                "clicks_12mo", "disposition", "reason"])
    for p in rows:
        parent = by_id.get(p.parent)
        first = p.menus[0] if p.menus else None
        w.writerow([
            p.path, p.title, p.kind, p.template, p.status, p.modified,
            p.depth, parent.path if parent else "",
            "; ".join(sorted({m[0] for m in p.menus})),
            first[1] if first else "",
            first[2] if first else "",
            first[3] if first else "",
            "", "", "", "", "", ""])
    return out.getvalue()


def render_json(rows):
    return json.dumps([{
        "path": p.path, "title": p.title, "depth": p.depth,
        "template": p.template, "status": p.status, "modified": p.modified,
        "kind": p.kind,
        "menus": [{"menu": m[0], "depth": m[1], "parent": m[2], "label": m[3]}
                  for m in p.menus],
    } for p in rows], indent=2) + "\n"


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        prog="site-inventory",
        description="List every page of a site, with its parentage, as the "
                    "starting document for an IA review.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--wp", metavar="PATH",
                     help="WP-CLI against a local install, or '.' when --wp-cmd "
                          "already knows where the site is")
    src.add_argument("--url", metavar="URL", help="REST API, falling back to the sitemap")
    src.add_argument("--sitemap", metavar="SRC", help="an XML sitemap, by URL or file")

    ap.add_argument("--wp-cmd", default="wp", metavar="CMD",
                    help="how to reach WP-CLI: 'wp' (default), 'ddev wp', "
                         "'vagrant ssh -- wp', 'wp ssh --host=prod'")
    ap.add_argument("--post-types", default="page",
                    help="comma separated, WP sources only (default: page)")
    ap.add_argument("--include-drafts", action="store_true",
                    help="also list draft and private pages")
    ap.add_argument("--templates", action="store_true",
                    help="look up each page template (--wp only, one call per page)")
    ap.add_argument("--menus", action="store_true",
                    help="also read the navigation menus. A menu nests items "
                         "independently of the page tree, so this is a separate "
                         "fact from the structure, not a view of it.")
    ap.add_argument("--menus-from", metavar="URL",
                    help="page to read the rendered menus from (default: the "
                         "site root). Footer menus sometimes only appear deeper.")
    ap.add_argument("--no-destinations", action="store_true",
                    help="do not add menu targets that are not pages. They are "
                         "added by default: a taxonomy archive in the menu is "
                         "not a page to WordPress and is entirely a page to the "
                         "client, who put it there.")
    ap.add_argument("--status", default="keep", metavar="TAG",
                    help="status tag on every line, or '' for none (default: keep)")
    ap.add_argument("--title", default="", help="document title for the Markdown output")
    ap.add_argument("--format", default="markdown",
                    choices=["markdown", "csv", "json"])
    ap.add_argument("-o", "--out", metavar="FILE", help="write here instead of stdout")
    args = ap.parse_args()

    post_types = [t.strip() for t in args.post_types.split(",") if t.strip()]
    statuses = ["publish"] + (["draft", "private"] if args.include_drafts else [])

    if args.wp:
        pages, trusted = from_wp(args.wp, post_types, statuses, args.templates,
                                 args.wp_cmd)
    elif args.url:
        pages, trusted = from_rest(args.url, post_types, statuses)
        if pages is None:
            warn("REST API unavailable, falling back to the sitemap")
            pages, trusted = from_sitemap(urljoin(args.url, "/sitemap.xml"))
    else:
        pages, trusted = from_sitemap(args.sitemap)

    if not pages:
        die("no pages found")

    menus = []
    if args.menus:
        if args.wp:
            menus = menus_from_wp(args.wp, args.wp_cmd)
        else:
            src = args.menus_from or args.url or ""
            if not src:
                die("--menus needs --url or --menus-from, or --wp")
            try:
                menus = menus_from_html(src)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                die("could not read %s (%s)" % (src, e))
        if not menus:
            warn("no menus found")
        elif not args.no_destinations:
            extra = add_menu_destinations(pages, menus, args.url or "",
                                          probe=bool(args.url))
            if extra:
                warn("%d menu destinations added that the page query did not "
                     "see" % len(extra))
        tag_menu_membership(pages, menus)

    roots = tree_from_parents(pages) if trusted else tree_from_paths(pages)
    rows = order(roots)

    if args.format == "markdown":
        text = render_markdown(rows, args.title, trusted, args.status.strip())
        if menus:
            text += render_navigation(menus, args.url or "")
    elif args.format == "csv":
        text = render_csv(rows, {p.id: p for p in pages})
    else:
        text = render_json(rows)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        warn("%d pages written to %s" % (len(rows), args.out))
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
