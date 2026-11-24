# site-inventory

Lists every destination on a site as the starting document for an information architecture
review. Stage 1 of the IA workflow: facts, not judgement.

**The inventory is a flat list; structure and navigation are views over it.** One row per
destination, each carrying where it sits in the page tree *and* where it sits in each menu.
Those two disagree often, and making either one the spine of the inventory hides that.

**A destination is anything the site goes to**, not only a WordPress page. A taxonomy archive
is not a page to WordPress and is entirely a page to the client, who put it in the menu. So a
menu target the page query never saw is added to the inventory, classified by what actually
renders at it, rather than reported as an anomaly.

Take the inventory from **production**. Only the live site has an accurate structure: a
local copy is a snapshot of whenever it was pulled, and clients add, rename and delete pages
without telling anyone. An IA review built on a stale tree looks authoritative and is wrong.

## Sources

Three, in order of how much they can be trusted:

| Flag | Source | Parentage |
|---|---|---|
| `--wp PATH` | WP-CLI against an install, production over SSH for preference | True, from `post_parent` |
| `--url URL` | `/wp-json/wp/v2/`, falling back to the sitemap | True, while the REST API answers |
| `--sitemap SRC` | An XML sitemap, by URL or local file | **Inferred from path depth. A guess.** |

Inferred hierarchy is wrong wherever a site's URLs do not mirror its page tree, which is
common. The Markdown output says so in a trailing line; keep that line until someone has
checked the tree.

## Use

```bash
# Production, no shell access. The usual case.
site-inventory.py --url https://example.test/ --title "Example Site"

# Production over SSH, when the REST API is closed
site-inventory.py --wp . --wp-cmd "wp ssh --host=prod"

# A sitemap you already have
site-inventory.py --sitemap ./sitemap.xml

# A local install. Fine for testing the tool, wrong for an IA review:
# a local copy drifts from the live structure.
site-inventory.py --wp . --wp-cmd "ddev wp"
```

Useful flags: `--post-types page,post`, `--include-drafts`, `--templates`
(one WP-CLI call per page, so it is off by default), `--status ''` to leave the
`[keep]` tag off every line, `-o FILE`.

## Navigation

`--menus` also reads the site's navigation. A menu is **not** the page tree: WordPress menu
items carry their own `_menu_item_menu_item_parent`, so a menu can nest two pages that have
no parent-child relationship, and can leave out pages that do. The two are separate facts and
the tool keeps them in separate sections.

The REST menu endpoints need an authenticated user with `edit_theme_options`, so they answer
401 on a site you are only visiting. That leaves two routes:

- **The rendered front end** (default). Any list of links inside `<nav>`, `<header>` or
  `<footer>` counts, whatever its classes, because plenty of sites do not use `wp_nav_menu`
  at all: a mega-menu plugin, a page builder or hand written markup produce navigation with
  no `menu-` id on it. Duplicate renderings of one menu, mobile and desktop, are collapsed.
- **`wp menu list`** when the source is `--wp`. Authoritative, and it sees menus that are
  registered but not displayed.

Prefer the front end. It is the structure the client and their visitors actually experience,
and the database is what the site is made of. **Where the two disagree, that disagreement is
the finding** — a menu nesting four top-level pages under About Us tells you what the client
believes the structure is, whatever `post_parent` says.

`--menus-from URL` reads the menus from a different page, since footer menus sometimes only
appear deeper in a site. It accepts a local HTML file too.

## Content audit

`--content` fetches every destination and records what it is made of: HTTP status, word
count, the H1 and how many there are, the title tag, meta description length, images and how
many lack alt text, and how many internal links point at it. Four workers, so a 90
destination site takes a couple of minutes.

This is the **scriptable half** of a content audit. The other half, what is *missing*, cannot
be read off the site at all: a site audit tells you what is weak, never what is absent. Gaps
come from the client's goals and audiences, the journeys the site must support, Search
Console queries with demand and no page to answer them, and competitor sites.

Two cautions when reading `words`. It excludes `script`, `style`, `nav`, `header`, `footer`
and `aside`, but a theme that builds its furniture out of plain divs still gets counted, so
look for the **floor**: if thirty pages all land within a few words of each other, that
number is the template and those pages are empty. And `links_in` counts links found in the
crawled set only, so a page linked only from a post, a widget or a PDF reads as an orphan
here.

## Triage

The inventory goes to the client, and every row in it costs them a decision. So two kinds of
row are dealt with before it leaves the studio.

**Archives WordPress generates are removed by default**: tag, category, author, date, custom
taxonomy, search, feeds and pagination. With `--sitemap` (or the `--url` fallback to it) each
sub-sitemap is classified by fetching its last URL, so a site whose sitemap lists every tag
does not hand the client hundreds of tag archives. An archive a menu links to is kept and
marked `check`, because the client put it there. `--keep-generated` turns this off.

**Rows the studio already knows about** come from a per-project rules file, `--rules FILE`:

```text
# action  path glob            reason the client reads
drop      /login/              membership plugin, removed
drop      /people[0-9]/        test page
check     /video-library/      a listing of one tag's posts, not content
```

`drop` removes the row; `check` keeps it, highlighted with the reason. The first matching rule
wins. Globs are `fnmatch` against the inventory path. The rules file names a client's pages,
so it lives in the client's folder, never in this repo.

Removed rows go to `--excluded FILE` as CSV, with `disposition` set to `drop` and the reason,
because a removed page still needs a redirect. Without `--excluded` they are listed on stderr.

## Output

`--format markdown` (default) is the nested list an IA session starts from:

```markdown
# Example Studio

## Structure

- Home `/` [keep]
- The workshop `/workshop/` [keep]
  - The team `/workshop/team/` [keep]
- Video library `/video-library/` [keep]
  Check: a listing of one tag's posts, not content

## Navigation

### Main
- The workshop -> `/workshop/`
  - The team -> `/workshop/team/`
```

It is the source document the claude.ai Information Architecture project charts, in the format
its instructions set out (`bain-studio/studio/ia/project-instructions.md`). A row triage marks
`check` carries its reason as a note, the indented line with no bullet, so the status stays one
of keep, new, merge or drop. `## Navigation` appears with `--menus`, one `###` list per menu,
nested as the menu nests. When the hierarchy had to be inferred from URL paths, a warning line
sits between the title and `## Structure`, outside the document's sections.

`--format csv` is the inventory proper: one row per destination, carrying both views and the
empty columns for the traffic join.

| Column | Holds |
|---|---|
| `path`, `title`, `kind` | What it is. `kind` is page, taxonomy archive, search, post, archive |
| `template`, `status`, `modified` | What WordPress knows about it |
| `tree_depth`, `tree_parent` | Where it sits in the page tree |
| `in_menus`, `menu_depth`, `menu_parent`, `menu_label` | Where it sits in the navigation, and what it is called there |
| `sessions_12mo`, `entrances_12mo`, `impressions_12mo`, `clicks_12mo` | Empty. The stage 2 join |
| `triage`, `triage_reason` | `check` and why, for a row the client should confirm. See Triage |
| `disposition`, `reason` | Empty. The stage 3 decision. `drop` in the `--excluded` file |

A row with `tree_depth` 0 and `menu_depth` 1 is a top-level page the menu presents as a
child. That is not an error in either place; it is the finding.

`--format json` is the same data for anything else that needs it.

## Requires

Python 3.6+, standard library only. WP-CLI only for `--wp`.
