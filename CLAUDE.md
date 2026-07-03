# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A pywikibot-based bot that generates a daily digest of activity on the Chinese Wikipedia
**Did You Know Candidate** (新條目評選 / `WP:DYKC`) page (`Wikipedia:新条目推荐/候选`) and
posts a Wikitext newsletter to subscribed user talk pages (or via MassMessage).

The bot compares today's parsed vote counts against the snapshot saved on the previous
run (TSV file `old_votes.txt`), produces a diff, renders it as Wikitext, and delivers
it according to `send_mode` in `config.yaml`.

## Layout

```
zhwiki_nomination_daily_digest/
├── parsers/dykc.py        # HTML parsing, vote diff logic, talk-page archive check
├── newsletters/dykc.py    # Wikitext rendering of diff report → newsletter body
└── runners/
    ├── __init__.py        # DailyDigestSendMode enum (DRY_RUN | DIRECT | MMS)
    └── dykc.py            # main(): loads config, calls run_bot()
```

Root files (user-edited, gitignored secrets):
- `config.yaml` — runtime config (`old_votes_path`, `send_mode`, optional `dykc_title`,
  `target_title`, `summary`).
- `user-config.py` — pywikibot family/site config (mylang=`zh`, family=`wikipedia`).
- `user-password.py` — `BotPassword(...)` tuple imported by `user-config.py`.
- `old_votes.txt` — TSV snapshot of last-run vote counts (`title\tsupport\toppose\tproblematic`).
- `throttle.ctrl` — pywikibot throttle file (write-truncate to control rate).
- `apicache/` — pywikibot on-disk API response cache (gitignored).

## How the Pipeline Works

`runners/dykc.py:main()` →
1. Load `config.yaml`. Construct `Site()` (reads `user-config.py` + `user-password.py`).
2. `run_bot(...)` →
   1. If `old_votes.txt` exists, parse it via `parsers.dykc.import_votes_from_file`.
   2. Fetch the DYKC page parsed HTML via `Page.get_parsed_page(force=...)` and parse
      with `parsers.dykc.get_active_votes` (walks DOM bottom-up, counting
      `zhwpVoteSupport` / `zhwpVoteOppose` / `zhwpDYKwq` until a `dykarticle` element
      is hit; `<s>/<strike>/<del>` and `.zhwpVotevoid` are stripped first).
   3. If a previous snapshot exists, build a `DYKCDiffReport` via
      `parsers.dykc.generate_diff_report`. For each removed entry, it toggles to the
      article's talk page (via `PreloadingGenerator`) and inspects the most recent
      `DYKVoteCount/archive` template to determine pass/fail.
   4. Render Wikitext with `newsletters.dykc.generate_newsletter_content` (Wikitext
      strings are defined as module-level constants in that file).
   5. Deliver per `send_mode`:
      - `MMS` — POST `action=massmessage` to the `target_title` page's links.
      - `DIRECT` — for each link on `target_title` page where namespace is 4 (project)
        or odd (talk), `site.editpage(section="new", bot=True, ...)`.
      - `DRY_RUN` — log only.
   6. Always overwrite `old_votes.txt` with the freshly parsed vote counts.

The `target_title` page itself is treated as a subscription list: every linked page
matching a project or talk namespace becomes a delivery target.

## Run / Develop

Python 3.14 venv is at `.venv/`. Activate it before running:

```bash
source .venv/bin/activate
python -m zhwiki_nomination_daily_digest.runners.dykc
```

No third-party install step is scripted; pywikibot and BeautifulSoup4 must be
available in the venv (they are already installed under `.venv/lib/`).

There is no test suite, linter, formatter, or build step configured. To iterate on a
single module, run the bot end-to-end with `send_mode: dry_run` (the default in
`config.yaml`) and inspect the `Newsletter content:` log line plus the rewritten
`old_votes.txt`. Clear `throttle.ctrl` (it's empty/truncated) if you want to bypass
pywikibot's read-throttling between manual runs.

## Conventions Specific To This Codebase

- Bot password is a `BotPassword` constructor call, not a plain string — keep this
  format; pywikibot's `login()` expects it.
- Vote counts are walked **bottom-up** in `get_active_votes` because nested
  `<div class="dykarticle">` blocks interleave with their parent vote tallies;
  the order matters and is intentional.
- Newsletter Wikitext is composed from raw string concatenation in
  `newsletters/dykc.py`; icon markup (`Codex icon ...`, `Yes check.svg`,
  `X mark.svg`) and CSS color vars (`--color-content-added/removed`) are hardcoded
  inline. Preserve `~~~~` at the footer (MediaWiki signature).
- All user-facing strings in `newsletters/dykc.py` and the default
  `target_title`/`dykc_title`/`summary` in `runners/dykc.py` are in **Traditional
  Chinese** (繁體中文), matching the bot owner `1F616EMO-bot`. Keep new copy in the
  same script style unless intentionally changing the target audience.
- `throttle.ctrl` is intentionally checked in as an empty file; pywikibot
  truncates it after writes — do not delete it.
