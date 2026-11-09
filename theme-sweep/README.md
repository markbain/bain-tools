# theme-sweep

Mechanical sweep for a WordPress.org theme review. Does the deterministic half of a
review so the reviewer spends their time on judgement instead of greps.

It reports **facts and candidates**. It never decides what is a finding.

## What it does

- Downloads the submitted zip from wordpress.org and installs it into the test site
- Restores a known-good content baseline between reviews, via a DDEV snapshot
- Activates the theme and crawls seven templates with `WP_DEBUG` on, then reports
  whatever landed in `debug.log`
- Runs Theme Check
- Parses the `style.css` header and checks every declared tag against something real
  in the theme (classic `add_theme_support` / `register_nav_menus`, or block
  `templates/`, `styles/`, `patterns/`, `theme.json`)
- Flags functions in the public namespace with no prefix, or a prefix that does not
  match the theme slug
- Checks text domain consistency across PHP and HTML
- Lists every remote host the theme references, flagging anything that is not the
  Google Fonts exception
- Pairs every `.min.css` / `.min.js` with its unminified original, and flags a file
  that is minified without saying so in its name. The required items ask for the
  original alongside the minified one, and a licence credit in the readme is not
  the same thing - a bundled Bootstrap can be credited correctly and still be
  missing its source
- Greps for destructive deletes, admin menus, onboarding notices, remote fetches and
  unguarded superglobals
- Reads `readme.txt` for stock-image sources, and reports the screenshot's dimensions
  against the 1200x900 / 4:3 limits
- Uploads a logo, sets it as the `custom_logo` theme mod and looks for it in the
  front-page markup. `add_theme_support( 'custom-logo' )` and the `custom-logo` tag
  only prove the Site Identity control exists; a theme can declare both, pass Theme
  Check, carry the tag and still print a hardcoded image from its own folder on every
  install. The report also says whether the site's own name reaches visible text, or
  only an `alt` attribute

It writes `reviews/<slug>-<version>-sweep.md` in the project.

## What it does not do

Rendering, beyond the two things above. Every review still needs a person to open the
site and look at it. The
report ends with the list of what only a human catches: long titles at narrow widths,
keyboard focus order and modal focus traps, the screenshot against the real render,
and each bundled image's licence.

A sweep that finds nothing is not a pass.

## The review template

`review-template.md` is the house format the reports feed into: the rules that
decide how deep a review goes and which Trac status it closes at, the shape of the
internal notes, and the Trac comment skeletons. It is symlinked into the review
project's `reviews/` folder, so edit it here and the working copy follows.

The sweep is the mechanical half; the template is the judgement half. Neither is
much use without the other.

## Requirements

A DDEV WordPress project with the theme unit test data imported, and the `theme-check`
plugin active. `WP_DEBUG` and `WP_DEBUG_LOG` need to be on - DDEV sets `WP_DEBUG` for
you, so only `WP_DEBUG_LOG` has to go in `wp-config.php`.

## Usage

Run from the project root, or pass `--project`.

```bash
# one-time, with the unit test data imported and a default theme active
theme-sweep.py baseline

# review a theme end to end
theme-sweep.py run kopanews 1.0.1

# or step by step
theme-sweep.py fetch kopanews 1.0.1
theme-sweep.py reset
theme-sweep.py check kopanews

# put the content back after a theme has chewed on it
theme-sweep.py reset
```

`reset` matters more than it looks. Some themes ship an importer that force-deletes
every post and attachment on the site, so one click can cost you the unit test data.

`check` now writes to the site as well as reading it: the custom-logo test imports an
attachment and sets a theme mod. It removes both afterwards, including on failure, but
`reset` is there if a run is interrupted partway.

## Licence checks

The Pexels note in the report reflects the current site, not the handbook's wording.
The handbook tells you to click a "free to use" link that Pexels has since renamed.
The photo page now shows "Free" next to a "License" heading; follow it.
`/creative-commons-images/` is CC0 and usable, `/license/` is the Pexels License and
is not. Only CC0, CC BY 4.0 and CC-BY-SA 4.0 are accepted for images.
