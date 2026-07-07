"""Code for generating daily digest newsletters."""

from datetime import datetime, timezone
from typing import Mapping

from pywikibot import Site, logging

from ..parsers.dykc import DYKEntry, DYKVoteCount, DYKCDiffReport
from . import DailyDigestSendMode, send_daily_digest

DELTA_COLOR_POSITIVE = 'var(--color-content-added,#006400)'
DELTA_COLOR_NEGATIVE = 'var(--color-content-removed,#8b0000)'

DYKC_LINK_ICON = "[[File:Codex icon arrowNext.svg|15px|link=WP:DYKC#{pagename}|alt=前往評選頁面|class=skin-invert notpageimage]]"

REMOVED_ROW = "* {icon}&nbsp;[[{pagename}]]：{result}"
REMOVED_ICON_PASSED = "[[File:Yes check.svg|15px|link=Talk:{pagename}#新条目推荐讨论|alt=通過|class=notpageimage]]"
REMOVED_ICON_FAILED = "[[File:X mark.svg|15px|link=Talk:{pagename}#未通过的新条目推荐讨论|alt=不通過|class=notpageimage]]"
REMOVED_RESULT_PASSED = r'<span style="color:var(--color-content-added,#006400);font-weight:bold">通-{}-過</span>'
REMOVED_RESULT_FAILED = r'<span style="color:var(--color-content-removed,#8b0000);font-weight:bold">不通-{}-過</span>'

HEADING_NEW_ENTRY = "\n[[File:Codex icon bellOutline.svg|20px|link=|alt=新增條目|class=skin-invert notpageimage]]&nbsp;'''新增條目：'''共有{num}個新條目提交評選："
HEADING_CHANGES_ENTRY = "\n[[File:Codex icon add.svg|20px|link=|alt=票數變化|class=skin-invert notpageimage]]&nbsp;'''票數變化：'''共有{num}個新條目有票數變化："
HEADING_ENDED_ENTRY = "\n[[File:Codex icon checkAll.svg|20px|link=|alt=完成評選|class=skin-invert notpageimage]]&nbsp;'''完成評選：'''共有{num}個新條目評選已完結："


def generate_votes_display(entry: DYKVoteCount) -> str:
    return f"({entry.vote_support}/{entry.vote_oppose}/{entry.vote_problematic})"


def generate_delta_number_display(delta: int, color_invert: bool = False) -> str:
    if delta > 0:
        color = DELTA_COLOR_NEGATIVE if color_invert else DELTA_COLOR_POSITIVE
        return f'<span style="color:{color};font-weight:bold">+{delta}</span>'
    elif delta < 0:
        color = DELTA_COLOR_POSITIVE if color_invert else DELTA_COLOR_NEGATIVE
        return f'<span style="color:{color};font-weight:bold">{delta}</span>'
    else:
        return '0'


def generate_votes_delta_display(delta: DYKVoteCount) -> str:
    vote_support = generate_delta_number_display(delta.vote_support)
    vote_oppose = generate_delta_number_display(delta.vote_oppose, True)
    vote_problematic = generate_delta_number_display(
        delta.vote_problematic, True)
    net_change = generate_delta_number_display(
        delta.vote_support - delta.vote_oppose)
    return f"({vote_support}/{vote_oppose}/{vote_problematic}) [{net_change}]"


def generate_new_entry_notes(entry: DYKEntry) -> str:
    author = entry.entry_author
    nominator = entry.entry_nominator
    if author == nominator:
        nomin_string = f"提名/作者：[[User:{author}|{author}]]"
    elif author == '':
        nomin_string = f"提名：[[User:{nominator}|{nominator}]]；非一人主編"
    else:
        nomin_string = f"提名：[[User:{nominator}|{nominator}]]；作者：[[User:{author}|{author}]]"

    return f"<small>（{nomin_string}；類別：{entry.entry_type}）</small>"


def generate_newsletter_content(diff_report: DYKCDiffReport) -> str:
    """Generate a newsletter ready for posting onto talk pages.

    Parameters
    ----------
    diff_report: DYKCDiffReport
        The report of vote differeneces.

    Returns
    -------
    str
        The report in Wikitext.
    """

    rows = []
    rows.append('自上次簡報以來，以下是[[WP:DYKC|新條目評選]]的變化：')

    # New entries
    rows.append(HEADING_NEW_ENTRY.format(num=len(diff_report.new_entries)))
    for title, entry in diff_report.new_entries.items():
        linkicon = DYKC_LINK_ICON.format(pagename=title)
        votes_display = generate_votes_display(entry.entry_votes)
        entry_notes = generate_new_entry_notes(entry)
        rows.append(
            f"* {linkicon}&nbsp;[[{title}]]：{votes_display}{entry_notes}")

    # Vote Differences
    rows.append(HEADING_CHANGES_ENTRY.format(
        num=len(diff_report.vote_differences)))
    for title, delta in diff_report.vote_differences.items():
        entry = diff_report.new_votes.get(title)
        entry_votes = entry.entry_votes

        linkicon = DYKC_LINK_ICON.format(pagename=title)
        votes_display = generate_votes_display(entry_votes)
        votes_delta_display = generate_votes_delta_display(delta)
        rows.append(
            f"* {linkicon}&nbsp;[[{title}]]：{votes_display} {votes_delta_display}")

    # Removed entries
    rows.append(HEADING_ENDED_ENTRY.format(
        num=len(diff_report.removed_entries)))
    for title, passed in diff_report.removed_entries.items():
        icon = (REMOVED_ICON_PASSED if passed else REMOVED_ICON_FAILED).format(
            pagename=title)
        result = REMOVED_RESULT_PASSED if passed else REMOVED_RESULT_FAILED
        row = REMOVED_ROW.format(icon=icon, pagename=title, result=result)
        rows.append(row)

    return '\n'.join(rows)


def send_newsletter_by_diff_report(site: Site, diff_report: DYKCDiffReport, config: Mapping):
    target_title = config.get('target_title')
    send_mode = config.get('send_mode', DailyDigestSendMode.DIRECT)
    summary = config.get('summary', '發送新條目評選每日簡報')

    if target_title is None:
        raise ValueError("Invalid target_title")
    if send_mode not in DailyDigestSendMode:
        raise ValueError(f"Invalid send_mode: {send_mode}")

    newsletter_content = generate_newsletter_content(diff_report)

    footer = config.get('footer', '~~~~~').strip()
    newsletter_content += "\n\n" + footer

    now = datetime.now(timezone.utc)
    newsletter_title = f"新條目評選每日簡報（{now.year}年{now.month}月{now.day}日）"

    logging.info(f"Newsletter title: {newsletter_title}")
    logging.info("Newsletter content:\n" + newsletter_content)

    send_daily_digest(site, newsletter_title,
                      newsletter_content, target_title, send_mode, summary)
