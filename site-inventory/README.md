# site-inventory

Lists every page of a site, with its parentage, as the starting document for an
information architecture review. Stage 1 of the IA workflow: facts, not judgement.

## Sources

Three, in order of how much they can be trusted:

| Flag | Source | Parentage |
|---|---|---|
| `--wp PATH` | WP-CLI against an install | True, from `post_parent` |
| `--url URL` | `/wp-json/wp/v2/`, falling back to the sitemap | True, while the REST API answers |
| `--sitemap SRC` | An XML sitemap, by URL or local file | **Inferred from path depth. A guess.** |

Inferred hierarchy is wrong wherever a site's URLs do not mirror its page tree, which is
common. The Markdown output says so in a trailing line; keep that line until someone has
checked the tree.

## Use

```bash
# A local install
site-inventory.py --wp /path/to/public_html --title "Example Site"

# Behind DDEV, Vagrant or SSH
site-inventory.py --wp . --wp-cmd "ddev wp"
site-inventory.py --wp . --wp-cmd "vagrant ssh -- wp"

# Live site, no shell access
site-inventory.py --url https://example.test/

# A sitemap you already have
site-inventory.py --sitemap ./sitemap.xml
```

Useful flags: `--post-types page,post`, `--include-drafts`, `--templates`
(one WP-CLI call per page, so it is off by default), `--status ''` to leave the
`[keep]` tag off every line, `-o FILE`.

## Output

`--format markdown` (default) is the nested list an IA session starts from:

```markdown
## Structure

- Home `/` [keep]
- The workshop `/workshop/` [keep]
  - The team `/workshop/team/` [keep]
```

`--format csv` is one row per page, with empty columns for the traffic join that
comes next: `sessions_12mo`, `entrances_12mo`, `impressions_12mo`, `clicks_12mo`,
`disposition`, `reason`. Fill those from GA4 and Search Console, decide a
disposition per row, and the statuses in the Markdown follow from the evidence
rather than from opinion.

`--format json` is the same data for anything else that needs it.

## Requires

Python 3.6+, standard library only. WP-CLI only for `--wp`.
