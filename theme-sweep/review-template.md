# WordPress.org theme review - template

There was no template before 2026-10-30. This one records the house format the
KopaNews and Ink Slip reviews settled on, plus the version pin.

## Where the files go

Review output does not live in the WordPress install: that tree is disposable and
unversioned. Notes, sweeps and Trac comments go to the reviews folder set by
`THEME_REVIEW_REPORTS`, flat, named `<slug>-<version>[-<kind>]`. The project's own
`CLAUDE.md` names the folder. The submitted zips stay in `review-zips/` in the
install, and this template stays beside the sweep that reads it.

## Rules

**Establish the theme type before anything else.** Classic or block decides what
every later check means. A classic theme declares wide support with
add_theme_support( 'align-wide' ) and a block theme puts it in theme.json, so a
block-shaped test run against a classic theme returns a false negative and reads
like a finding. Same for patterns, style variations, templates and block styles.
Write classic or block at the top of the notes and state, for each check, which
shape it assumes.

**No opinion until every item has been reviewed, one at a time.** This holds for
a partial review too: partial means fewer items, not items held to a lower
standard. An item is reviewed when you have opened the file, read the code
around it, and read the rule on the handbook page. Until then it is a candidate,
not a finding, and it does not go in a comment, a report or a reply.

The mechanical sweep produces candidates by design and says so at the top of
every report. Passing one on unopened is not a shortcut, it is skipping the
review. Three of the four items in the first Fixyno pass came off the sweep
unopened and all three dissolved on inspection: the TGMPA config was compliant
and its plugin hosted on wordpress.org, `yourwebsite.com` was a form placeholder
attribute, and the tags had evidence the block-shaped test could not see.

**Nothing is approved until every line and every requirement has a verdict.**
Not a grep list, not a pattern set: before approval is proposed, the whole of
each non-vendored file has been read and every requirement on the handbook
pages carries a recorded verdict. Greps catch what is already known to be worth
catching, so they are a first pass over a file and never the review of it.

This is the approval gate, not a change to the order of work. The tiers under
"Order the checks by cost" stand: cheap checks first, two required items still
end a pass, and a partial review still rejects on what it has found and says
"+ possibly more issues". What it forbids is proposing approval off a pass that
stopped early. By the time a theme is approved, everything the cheap tiers
deferred has been gone back over and settled.

**A verdict on everything is not a write-up of everything.** The gate above is
internal: every requirement carries a verdict in the notes before approval is
proposed. What reaches the ticket is the required items, plus whichever
recommendations are worth the author's time. The handbook asks for no more: it
defines a recommended item as one that does not affect the outcome of the
review, has the reviewer check the required items while noting any
recommendations, and says only that the review is added to the ticket, with
extra information encouraged. It sets no content requirement for a comment.
Checked on the handbook review page, 2026-11-15, which is the only authority on
it, so it is one source and not corroborated.

Fixyno is the counter-example: nine recommendations published across the 1.0.7
and 1.0.8 rounds, none of which could change the outcome, in the same passes
that missed three required items. Every recommendation published is a paragraph
written, a reply read and a round-trip the author owes nothing on.

What approval requires:

- A file ledger in the notes: every file in the zip, with the line ranges read
  and a verdict. Vendored code (TGMPA) and generated builds (`99_tw.css`) are
  diffed against upstream or against the bundled source, and the ledger says
  that is what was done rather than leaving them out.
- A hook and function inventory: every `add_action`, `add_filter` and function
  declaration in the theme, each with a one-line verdict. An entry in that
  inventory is what surfaces a hook nobody thought to grep for.
- The requirement list is built by reading the handbook pages at review time,
  and every requirement gets a verdict, including the ones no code read can
  settle. An item on "Still needs a human" without a recorded verdict is an
  unreviewed item, not a note.

Written 2026-11-15, after a key reviewer raised three items on Fixyno
Appliance Repair 1.0.9 that were all in the 1.0.8 this review approved: a
custom lazy-load content filter at `functions.php:1273-1404` and site-wide
response headers at `:1430-1455`, both plugin territory or disallowed, and
both unflagged across three passes. The lazy-load filter sits 58 lines below a
function the 1.0.7 review dissected. The third item, the mobile menu's focus
trap, sat on this template's own "Still needs a human" list through all three
passes and never got a verdict.

## Where a handbook sentence is narrower than it reads

Section 9 says "only one type of line ending is used", which reads theme-wide.
The team's enforcement is per file: Theme Check's
`checks/class-line-endings-check.php` raises its REQUIRED error only when a
`\r\n` and a bare `[^\r]\n` both appear in the *same* file, for `.php`, `.css`,
`.txt` and `.js`. A theme whose files are each internally consistent passes, and
uploads. Found on FWP Sobremesa 0.2.0, where one bundled OFL text is CRLF among
LF files: drafted as the one required item, and it was not one.

Before making a required item of a rule whose harm is mechanical - an upload
that fails, a pack that will not build - check whether the mechanism actually
fires, and whether the harm has already not happened. Read the check in
`wp-content/plugins/theme-check/checks/`; it is the operative text, and its
message usually quotes the same rationale as the handbook. Say in the comment
which of the two lists the item is on and why, so the author can see the
reasoning rather than take the verdict on trust.

## Block validation, and how to run it without clicking

A block theme's hand-written markup can disagree with what the block's own `save`
function would write, and the editor then shows "This block contains unexpected
or invalid content" with an "Attempt recovery" button. Nothing catches this
outside the editor: Theme Check has no block-validation check, and the delimiter
parse a sweep does proves only that the comments balance.

It does not need clicking through templates. Signed in as an admin, in a Site
Editor tab, the editor's own validator will do it:

- `wp.apiFetch({path:'/wp/v2/templates?per_page=100'})` and the same for
  `/wp/v2/template-parts`. Check each one reports `source: theme` and
  `has_theme_file: true`, or you are validating a copy saved in the database
  rather than the theme's files.
- `wp.blocks.parse(content.raw)` and walk `innerBlocks`, collecting every block
  with `isValid === false` and its `validationIssues`.
- For the expected markup, `wp.blocks.getSaveContent(type, attributes, [])` on
  the block in question. Never write the expected markup from memory.
- Patterns are validated this way too: the REST content for a template resolves
  `wp:pattern` blocks into their markup, so a template that is clean in the file
  can report invalid blocks that belong to a pattern.

**The team treats it as blocking, whatever the handbook says.** Section 11 of the
required items says only that block templates must be complete and that blocks
may not have missing or incorrect closing tags, which is narrower than invalid
content - so the handbook is not the operative text here and the search box is.
Of the fourteen tickets whose text carries the phrase "unexpected or invalid
content", the four read in full all put it in the list the author has to fix,
once as an explicit required item alongside the front-end symptom, once as a
numbered item among licensing and screenshot failures, once as a line in a fix
list, and once as a condition the reviewer set "before I finish" on a ticket that
was then approved. None of them calls it optional.

That last one is worth the warning. Its comment opens "I found nothing that
blocks approval so far", and read quickly that looks like a reviewer classing
invalid blocks as a recommendation. Read on and the same comment asks the author
to open every template, part and pattern and make sure no block shows the
warning. A sentence saying nothing is wrong yet is not a verdict on the items
listed under it.

Measure the front end anyway, because it belongs in the comment either way: the
author needs to know which of the eight edits changes what a visitor sees. A
missing `has-background` or `has-text-color` next to an intact inline `style`
usually changes nothing; a declared border width that never reached the markup
does, and renders at the block style's default instead.

**What "Attempt recovery" does, since an author will ask.** Tested on a block
theme whose patterns had the wrong markup: recovering and saving writes a new
`wp_template` post holding the whole template, with every `wp:pattern` reference
replaced by that pattern's content and its `get_theme_file_uri()` paths written
out as plain URLs. The site then uses its own copy, so later fixes in the theme's
pattern files never reach it. Say this in the comment - it is the reason the
author cannot tell users to recover instead.

Recovery is also per block, and saving fixes nothing on its own. A block that
fails validation is serialized from its original content, so every block the user
did not click is stored exactly as the theme shipped it and is still invalid. The
one recovered block is rewritten from its attributes, completely, which is why a
value held in the block comment's JSON - a border width, say - comes back.

**Prove a count before reporting it.** The paragraph above replaced one that said
recovery silently dropped an attribute, with a mechanism invented to explain it.
It had not: the regex carried a `%%` from a `printf` format string and could not
match, and a second count was a substring of a longer class name. A zero needs
the pattern proved against something that should match, and a number close to the
expected one needs its matches printed rather than totalled. Use literal string
matching where the thing being counted is a literal string.

**The fix is edits in place, not a round trip through the editor.** Patterns are
PHP: their markup carries `get_theme_file_uri()` and `esc_html_e()` calls.
Pasting a pattern into the editor, letting it recover the blocks and copying the
markup back returns fixed URLs and one language's strings in place of those
calls, so it trades a validation error for a worse one. Say so in the comment,
because it is the obvious thing for an author to try.

## Phone width

The browser extension's `resize_window` reports success and leaves the viewport
where it was, so phone width cannot be measured through it. Headless Chromium
over the DevTools protocol can: launch it with `--remote-debugging-port`, read
the page target's `webSocketDebuggerUrl` from `/json`, then `Page.navigate`,
`Emulation.setDeviceMetricsOverride` and `Page.captureScreenshot`.
`Input.dispatchKeyEvent` sends real Tab, Enter and Escape, which is what gets you
focus order and `:focus-visible`. **Use `cdp/cdp_check.py`**: it takes a base URL,
the theme slug, a width and a list of paths, asserts both the theme and the
viewport on every page, and runs the overflow and keyboard checks together. It
picks its selectors by trying a block-theme pair, a classic pair and a loose
fallback, and prints which pair it used. `cdp_shot.py`, `cdp_keyboard.py` and
`cdp_viewport.py` beside it are superseded worked examples of the raw calls, each
with its defects named in its docstring.

**Set `mobile: false` in the override, and read `innerWidth` back on every run.**
With `mobile: true` Chromium applies a virtual viewport that shrinks to fit the
content, so it returns the width you asked for while the page fits and a wider
one as soon as something overflows. Measured on one theme at 390, the only
variable being the length of the site title:

| Title | `mobile` | `innerWidth` | `scrollWidth` | Elements past the edge |
|---|---|---|---|---|
| short | true | 390 | 390 | 0 |
| long | true | **690** | **690** | **0** |
| long | false | 390 | 689 | 13 |

The second row is the trap, and it is worse than wrong widths: the viewport grew
until the overflow fitted inside it, so `scrollWidth` equals `innerWidth` and no
element is past the edge. A 299px overflow reports as a clean pass. The only
thing that tells you is `innerWidth` coming back 690 when you asked for 390,
which is why the script refuses to report a measurement it did not get the
viewport for.

It also means `mobile: true` fails in exactly the case you are testing for and
passes in every other, so a run that looks right proves nothing about the next
one. Two sessions reached opposite conclusions about this the same morning, each
from its own correct readings, because one theme overflowed and the other did
not.

**Make the loop end on a condition, and print which one.** A keyboard pass that
stops after a fixed number of presses reports a pass when it runs out early:
sixteen presses missed three of Travelight's nineteen links, and a count of four
of Sobremesa's five became "every link" in a draft comment. Neither of us caught
our own. Tab until a condition is met - focus leaves the nav, or focus comes
round to an element already visited - keep a runaway guard, and print which of
the three ended the run. A run that ends on the guard is the one to distrust. **When a budget does expire, print what happened, not what it means.** The same
script gave up after six Tab presses looking for the menu toggle and printed
"toggle not reached by Tab" - a finished accessibility finding, in the same shape
as a real one, produced by a loop that stopped early. "Opener never took focus in
60 Tab presses" says the same thing without concluding anything, and a reviewer
reading it goes and looks. This is the candidates-are-not-findings rule wearing
different clothes: a tool that reports a conclusion has made the judgement the
reviewer is supposed to make.

The
cycling case is not an edge case: an overlay menu that traps focus correctly will
never let focus leave the nav, so "stop when focus leaves" alone runs to the
guard and once reported "200 of 5" as a pass.

**Assert the active theme on every page you measure, not once per run.** One
review install serving two reviews at the same time is one `wp theme activate`
away from a result that belongs to the other theme, and the switch can land
between two halves of the same script. The tell is a selector finding nothing -
"links in nav: 0", "no title el" - which reads like a finding and is not one.
Print the active theme alongside `innerWidth` in every measurement, and throw
away anything whose theme is not the one under review. Agreeing who holds the
install is not enough: both sessions here did that, in writing, and it still
happened twice in one morning.

**Test the long site title.** A theme can be clean at 390 on every template with
the default title and still overflow by 300px once the site title is long, if the
header is a flex row with `"flexWrap":"nowrap"`. The unit test data's titles are
there for this.

**Horizontal overflow is a recommendation unless the keyboard breaks.** The only
small-screen sentence in the required items is in section 3: "All controls usable
with the mouse must be usable with the keyboard, regardless of device and screen
size. Including but not limited to responsive versions for small screens, mobile
and other touch screen devices." So the question is never whether the layout
looks wrong at 390, it is whether anything became unreachable. A control that
scrolls into view when it is tabbed to is reachable. Test it rather than assume
it, in both directions: a menu panel that collapses to a strip is still a pass if
every link in it takes focus and Escape returns focus to the toggle.

Snap Chromium traps: it cannot write into `/tmp` or any dotted directory in
`$HOME`, so screenshot into a plain folder; it fails silently when its stdout is
a pipe; and it rewrites `PATH` for the rest of the shell command, so use absolute
paths after it.

## Reading a ticket at all

themes.trac.wordpress.org sits behind a JS browser check: curl and WebFetch both
get a bare nginx 403, and `?format=csv` returns the "Checking your browser"
interstitial. Open the ticket in the browser and read the page there. Trac's
notification mail in Gmail (label: WordPress Themes) carries the status, owner
and every comment, so it answers most questions without a browser - but it is a
record of what changed, not of the current state, so confirm the live version and
status on the page before writing a comment against them.

A ticket already at `approved` offers only "leave as approved" in its Modify
Ticket box. There is no action to put it back to `reviewing`, so the instruction
below to do that is available only while the ticket is still open. On an approved
ticket the levers are a comment saying plainly that the new version has not been
reviewed, and mail to themes@wordpress.org.

## The nudge, and the boilerplate for it

A ticket is only closeable for silence once the author has been **asked for an
update**. From https://make.wordpress.org/themes/handbook/review/working-with-trac/,
under the conditions for resolving as not-approved:

> You have asked the author to submit an update, but the author has not replied
> within 7 days.

The review comment is what asks for the update, so the seven days runs from the
review. The nudge is the warning inside that week: post it five days after the
review, with two of the seven left to run, and say how many are left. Put the
nudge in the Asana task with a due date when the review goes out, so it is not
remembered or forgotten by accident.

Post it as it stands. There is nothing to fill in: a nudge records no findings,
so it needs no file, no item and no name.

```
Hi,

I reviewed this theme five days ago and have not heard back. Are you still
working on it? A one-line reply keeps the ticket open for as long as you
need.

If I do not hear from you within two days - seven days from the review - I
will have to close it as not-approved, and you would have to submit again.

The ticket stays at `reviewing` until then.
```

Four things it has to do, and nothing else. Ask a question, so the author knows
a reply is wanted. Say when, and that the two days are the remainder of the
handbook's seven, so the deadline is checkable against the date on the review
comment rather than arbitrary. Name the consequence in the author's terms - a
new submission - without quantifying the queue, which is where it would tip into
a threat. And say what the status is now.

**It does not pin the version, and that is the one place it departs from the
rule above.** It can, because a nudge only exists while nothing has been
uploaded: an author who uploads has answered, and the nudge is not sent. So
there is one version in play and the ticket's own history says which. Every
other comment pins it.

**The handbook rule is not quoted here**, though the review comment quotes every
rule it applies. A nudge applies no rule - it asks a question and states a date.
If the author disputes the close when it comes, that is the comment to quote
https://make.wordpress.org/themes/handbook/review/working-with-trac/ in.

**If it goes out late, change both numbers.** "Five days ago" and "within two
days" are the house rhythm written out. On day six the author can check them
against the date on the review comment, so correct both by hand or do not send
it that day.

## Always say what the status is now

Every comment ends by naming the status the ticket is being left in, with the
version. Usually that is `reviewing`: the ticket stays open, stays assigned to
you, and the author keeps their place in the queue. Say that last part too - an
author who has had a theme closed before does not know it from "please upload a
new version", and the queue is the thing they are actually afraid of.

Mark's rule, 2026-11-10, after three comments went out with the required items
clear and the status never stated at all. An approval says it as plainly:
"Approving <theme> <version>", or "Leaving the status at `approved`" when the
version moved underneath an approval already given.

## The version pin

Open every Trac comment with the exact version it applies to, and do it again in
the line that sets the status.

The themetracbot rewrites the ticket summary on every upload. #294720 was titled
"KopaNews - 1.0.1" when the review started and reads "KopaNews - 1.0.4" now, so
the title is no record of what anyone passed. The comment is the only durable
one. On #294720 the author uploaded 1.0.3 and 1.0.4 into the window between
`approved` and a key reviewer setting live, and the theme went live on a version
nobody had reviewed. Naming the version would have made that visible to the key
reviewer at a glance.

While a ticket sits at `approved`, a themetracbot comment is the signal to act.
The comment carries a changeset link between consecutive versions, so pull both
zips and diff them. If the change is substantive, set the status back to
`reviewing` and say why, so nobody sets live on something unread. If it is what
you asked for, say so in a comment, and the key reviewer inherits your reading.

## How deep to go

Default to a partial review. Work the mechanical sweep, name the required items
it surfaces, and say "+ possibly more issues". It is the only honest shape for a
first look, and it does not pretend to a completeness you have not reached.

The exception is a theme you intend to approve. The handbook only lets you
approve once it passes all the requirements, so a partial review can reject but
can never approve. A theme that has already had one or more quick looks needs a
full pass before it can go anywhere. KopaNews 1.0.1 was that case and the full
pass is what got it live.

So: quick look first time, full pass when you mean to approve it. Say in the
comment which one the author is getting.

## Order the checks by cost, and stop at two required items

Mark's rule, 2026-11-10. Work the cheap, deterministic checks first and move
towards the expensive ones only while the theme is still passing:

1. Header, required files, licences and the resources list, prefixing, text
   domain, tags, screenshot dimensions, banned files, line endings, remote hosts,
   options, Theme Check, the WP_DEBUG crawl.
2. Scripted structural checks: `wp:` delimiter balance across every template,
   part and pattern; a `<main>` in every template; local font sources; `@media
   print` if the readme claims a print stylesheet; `msgfmt` on any catalogue;
   image dimensions and metadata.
3. Rendering, measured keyboard focus, the Site Editor's own block validation,
   per-template network requests, the screenshot against the real render. This
   tier is slow and some of it needs Mark signed in, so it is the last resort.

**Two required items end the pass.** Stop there and post a partial review rather
than spending the expensive tier on a theme that is going back to its author
anyway. Recommended items never stop a pass and never block approval, however
many there are. Only a theme still at zero or one required item after tiers 1 and
2 is worth tier 3 - and tier 3 is what a full pass needs, so only that theme can
be approved.

A cheap check that earns its place: a block theme whose `front-page.html` has no
`<main>` gets no skip link at all, because core's
`_block_template_add_skip_link()` returns early when it finds no `MAIN` tag. It
is a grep, and it is a required accessibility item.

## The sweep's rows can be false positives too

The warning above is about NO EVIDENCE rows that are not findings. The reverse
also happens: `translation-ready` is reported OK when the style.css Text Domain
header is merely present, because the test ORs on that header. An OK row is a
candidate as much as a NO EVIDENCE row is - open the thing the tag's own
definition in the Theme Tag List names.

## Choosing the status - be kind to the author

**Changed 2026-11-05. The earlier version of this file told you to close a
partial review as not-approved. That was wrong, and it was wrong against the
handbook, not merely unkind.**

**Default to `reviewing`.** Assign the ticket to yourself, post the required
items, and let the author fix them. From
https://make.wordpress.org/themes/handbook/get-involved/onboarding-for-new-reviewers/how-to-write-and-save-the-review/,
on the status options:

> Review - Assign the ticket to yourself (the logged in user), and let the author
> continue working on improvements.

**Close not-approved only in the three cases the handbook names.** From
https://make.wordpress.org/themes/handbook/review/working-with-trac/, under "The
Actions available to new reviewers are: Resolve as not-approved - Only select
this if:"

> You have completed the review and there are 3 or more distinct errors.
> The author asks you to close it.
> You have asked the author to submit an update, but the author has not replied
> within 7 days.

Both quotes were read in the pages' own DOM, not through a summariser.

Read those three conditions closely, because the first one is narrower than it
looks. It needs a **completed** review *and* 3 or more distinct errors. A partial
review is by definition not completed, so a quick look that turns up two or three
items does not satisfy it. The honest options after a partial review are
`reviewing` or leaving it as `new`.

**Non-response is the usual reason to close.** Seven days after you have asked
for an update, with nothing back, close it. That is the handbook's own clock and
it does not need a judgement call. Before you do, check the ticket for a reply
you missed and the author for a reason to wait - a named date, a holiday, an
upload that landed without a comment.

**Why this way round.** Closing a theme bounces the author to the back of a
~180-ticket, two-week queue, and on a first look it does it for items they have
had no chance to fix. The queue-depth argument that produced the old rule is
real, but it is an argument for reviewing fewer themes properly, not for
rejecting responsive authors faster. A theme that is being actively fixed is the
cheapest kind of ticket to carry.

**What `reviewing` commits you to.** The re-review is yours. Say so in the
comment, then do it when the next version lands - and make that one the full
pass, because the theme has had its quick look and a partial review can never
approve. Do not hold a ticket open you are not going to come back to; leaving it
as `new` for another reviewer is kinder than that.

## A comment is not the audit trail

Mark's rule, 2026-11-10, on the Sobremesa partial review, which went out at 6,126
characters and should have been 3,500. A reviewer has not got time to write down
everything they did or everything that is wrong, and an author has not got time to
read it. Detail earns its place in a comment only when the author needs it to act.

Per item, the author needs four things: what the code does and where, the rule it
breaches quoted with its URL, and what would resolve it. That is all.

Leave out of the comment: how the finding was reached, what was measured and what
the numbers were, which core function proves it and at what line, how many
independent checks agreed, which handbook sections were read and found to carry no
rule, and the reasoning behind calling something recommended rather than required -
one clause for that is enough. A recommended item is usually two sentences.

**It is instruction, not copy, and the author's first language is probably not
English.** The theme directory is international, so use the ordinary word rather
than the better one, and keep a sentence clear rather than dense: "the Install
button will fail" beats "hands the user a URL that cannot resolve".

**The rule is don't show off. It is not about length, and idiom is fine.** Mark
settled both on 2026-11-10, in that order. Long sentences are not the problem and
figurative language is not the problem; the problem is the sentence that stops to
admire the finding - "most of what usually goes wrong here is right", "would put
it beyond question", "this is only about where the CSS lives". Cutting every
idiom instead produced prose that read like a machine ("I checked the rendered
page to confirm this", "You can fix this in one of two ways", twice in one
comment), which is the same fault from the other side. Write it the way you would
say it to the author, and cut the part where you are enjoying it.

**Praise is not an exemption.** The habit comes back as a compliment the moment
the checks pass: "no external request on any template, a real print stylesheet,
12:1 contrast in all six schemes, a screenshot that matches the render" is the
same list of what was checked, worn as flattery, and Mark cut it on sight. One
plain sentence - "It is a good block theme" - does the whole job. What the theme
got right goes in the notes.

Quote the rule, with its URL, on every required item: that is what the author has
to argue with. On a recommended item a paraphrase is enough - "section 13 asks
that upselling not be obtrusive" - because nothing is blocked by it, and quoting
all of them puts back most of what this rule cuts. Mark confirmed that split on
2026-11-10.

All of it still goes in the internal notes, where the format below asks for it:
the notes are the audit trail and the comment is the instruction. Keeping the two
apart is the point of writing both.

## Internal notes - <reports>/<slug>-<version>.md

```
# <Theme> <version> - review notes

Ticket #<id>. Reviewer markcbain. Reviewed <YYYY-MM-DD> on WordPress <ver> /
PHP <ver>, WP_DEBUG on, theme unit test data imported.

## Verdict

<Required count, recommended count, and the recommendation.>

## The <n> previous items

<One numbered entry per item from the last review, each marked resolved or not,
with the evidence that settles it. Verify claims instead of taking them on
trust, and say how many of a set you checked individually.>

## <Any judgement call, and which way it went>

<State the rule you considered hanging it on and why it does or does not apply.
Record the alternative reading and what the substitute item would be, so the
decision can be revisited without redoing the work.>

## <Any path exercised>

<New code that has never run gets run. Snapshot first, numbers before and after,
restore afterwards.>

## Tags

| Tag | Evidence |
|---|---|

## Other checks

<Theme Check, the crawl and debug.log, rendering at 1920 and 390, sanitize
callbacks, the single-option rule, credit links, anything carried over from the
previous version that you are deliberately not raising now.>

## Not done

<What you did not check, and why. An honest gap beats an implied pass.>

## Outcome

<Status set, date, what the comment said.>
```

## Trac comment - <reports>/<slug>-<version>-<kind>.txt

WikiFormatting. `== Heading ==`, `'''bold'''`, ` * ` bullets, no hard wrapping.

Every code token goes in backticks - function names, file paths and file:line references, theme mod and option names, CSS selectors and classes, attribute snippets, header fields, media queries. Trac renders a backtick span as inline monospace, the same as `{{{...}}}`. This is not cosmetic: on 1.0.6 the double underscores in an unwrapped `__()` were read as underline markup and swallowed, so the posted comment told the author to wrap their strings in `()`. Anything with a double underscore in it - a gettext call, a BEM class like `block__element` - is wrong without the backticks, and wrapping the lot is easier than remembering which tokens are at risk.

```
Hi @<author>,

I have reviewed <Theme> <version> on WordPress <ver> / PHP <ver> with `WP_DEBUG`
on and the theme unit test data imported. <What passed, in one sentence.> There
are <n> required items.

== Required ==

'''1. <One-line statement of the defect>'''

<What the code does, at file:line. The rule it breaches, quoted, with the
handbook URL. What would resolve it.>

== Recommended ==

'''<n>. <One-line statement>'''

<Same shape, shorter.>

Items 1 to <n> are required. Please upload a fixed version when you have one and
I will re-review.

Thanks for your work on this.
```

Approval:

```
Hi @<author>,

Approving <version>. All <n> required items from the <prev> review are resolved.
Good job!

<One paragraph of what you re-checked and found.>

Nothing blocks approval. I have <n> suggestions, none of them required.

== Recommended ==

...

Thanks for your work on this.
```

## Before you set approved

- Every required item from the last review closed on evidence, not on the
  author's word.
- Any new code path actually run, against a snapshot.
- Theme Check, the WP_DEBUG crawl, and the site opened and looked at.
- Every claim in the comment matches what you did. If you checked two of
  thirty-five, the comment says two.
- The version named in the first line.
- No rule cited that you have not read on the handbook page itself. The
  "no more than 150 chars" line, for instance, sits in the readme.txt example
  and is not a numbered requirement.

## After you set approved

- Watch for a themetracbot comment. Diff anything that lands and comment on it.
- Write the Outcome section of the notes.
