#!/usr/bin/env python3
"""site-inventory - list every page of a site, with its parentage, as the
starting document for an information architecture review.

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
import io
import json
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
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
                title=row["post_title"] or row["post_name"],
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
                    title=(row.get("title") or {}).get("rendered") or row["slug"],
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
        if status_tag:
            bits.append("[%s]" % status_tag)
        out.write(" ".join(bits) + "\n")
    if not trusted_parents:
        out.write("\nHierarchy inferred from URL path depth, not from the site's "
                  "own parentage. Check it before relying on it.\n")
    return out.getvalue()


def render_csv(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["path", "title", "depth", "template", "status", "modified",
                "type", "sessions_12mo", "entrances_12mo", "impressions_12mo",
                "clicks_12mo", "disposition", "reason"])
    for p in rows:
        w.writerow([p.path, p.title, p.depth, p.template, p.status, p.modified,
                    p.source, "", "", "", "", "", ""])
    return out.getvalue()


def render_json(rows):
    return json.dumps([{
        "path": p.path, "title": p.title, "depth": p.depth,
        "template": p.template, "status": p.status, "modified": p.modified,
        "type": p.source,
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

    roots = tree_from_parents(pages) if trusted else tree_from_paths(pages)
    rows = order(roots)

    if args.format == "markdown":
        text = render_markdown(rows, args.title, trusted, args.status.strip())
    elif args.format == "csv":
        text = render_csv(rows)
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
