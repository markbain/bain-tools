# WordPress.org theme review - template

There was no template before 2026-10-30. This one records the house format the
KopaNews and Ink Slip reviews settled on, plus the version pin.

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

## Internal notes - reviews/<slug>-<version>.md

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

## Trac comment - reviews/<slug>-<version>-<kind>.txt

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
