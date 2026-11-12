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

## Output

`--format markdown` (default) is the nested list an IA session starts from:

```markdown
## Structure

- Home `/` [keep]
- The workshop `/workshop/` [keep]
  - The team `/workshop/team/` [keep]
```

`--format csv` is the inventory proper: one row per destination, carrying both views and the
empty columns for the traffic join.

| Column | Holds |
|---|---|
| `path`, `title`, `kind` | What it is. `kind` is page, taxonomy archive, search, post, archive |
| `template`, `status`, `modified` | What WordPress knows about it |
| `tree_depth`, `tree_parent` | Where it sits in the page tree |
| `in_menus`, `menu_depth`, `menu_parent`, `menu_label` | Where it sits in the navigation, and what it is called there |
| `sessions_12mo`, `entrances_12mo`, `impressions_12mo`, `clicks_12mo` | Empty. The stage 2 join |
| `disposition`, `reason` | Empty. The stage 3 decision |

A row with `tree_depth` 0 and `menu_depth` 1 is a top-level page the menu presents as a
child. That is not an error in either place; it is the finding.

`--format json` is the same data for anything else that needs it.

## Requires

Python 3.6+, standard library only. WP-CLI only for `--wp`.
