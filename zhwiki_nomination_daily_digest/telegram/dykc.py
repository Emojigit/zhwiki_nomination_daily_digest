"""Telegram sender of the DYKC Daily Digest."""

from functools import cache
from time import sleep
from datetime import datetime, timezone
from typing import Mapping, Callable

from pywikibot import Site, Page, User, logging
from pywikibot.exceptions import APIError

from ..parsers.dykc import DYKEntry, DYKVoteCount, DYKCDiffReport
from . import send_daily_digest

UNORDERED_LIST_MARKER = '• '
PLAIN_LIST_MARKER = " • "

DYKC_SHORT_LINK = 'https://w.wiki/5JDL'

HEADING_NEW_ENTRY = "\n<b>新增條目：</b>共有 {num} 個新條目提交評選："
HEADING_CHANGES_ENTRY = "\n<b>票數變化：</b>共有 {num} 個新條目有票數變化："
HEADING_ENDED_ENTRY = "\n<b>完成評選：</b>共有 {num} 個新條目評選已完結："

ADDED_ROW = UNORDERED_LIST_MARKER + \
    "<a href=\"{pagelink}\">{pagename}</a>：{votes_display}{entry_notes}"
CHANGED_ROW = UNORDERED_LIST_MARKER + \
    "<a href=\"{pagelink}\">{pagename}</a>：{votes_display} {votes_delta_display}"

REMOVED_ROW = UNORDERED_LIST_MARKER + \
    "<a href=\"{pagelink}\">{pagename}</a>：{result}"
REMOVED_RESULT_PASSED = "通過"
REMOVED_RESULT_FAILED = "不通過"


def generate_votes_display(entry: DYKVoteCount) -> str:
    return f"({entry.vote_support}/{entry.vote_oppose}/{entry.vote_problematic})"


def generate_delta_number_display(delta: int) -> str:
    if delta > 0:
        return f'<b>+{delta}</b>'
    elif delta < 0:
        return f'<b>{delta}</b>'
    else:
        return '0'


def generate_votes_delta_display(delta: DYKVoteCount) -> str:
    vote_support = generate_delta_number_display(delta.vote_support)
    vote_oppose = generate_delta_number_display(delta.vote_oppose)
    vote_problematic = generate_delta_number_display(delta.vote_problematic)
    net_change = generate_delta_number_display(
        delta.vote_support - delta.vote_oppose)
    return f"({vote_support}/{vote_oppose}/{vote_problematic}) [{net_change}]"


def generate_new_entry_notes(entry: DYKEntry) -> str:
    author = entry.entry_author
    nominator = entry.entry_nominator

    author_link = "https://zh.wikipedia.org/wiki/User:" + author
    nominator_link = "https://zh.wikipedia.org/wiki/User:" + nominator

    if author == nominator:
        nomin_string = f"提名/作者：<a href=\"{author_link}\">{author}</a>"
    elif author == '':
        nomin_string = f"提名：<a href=\"{nominator_link}\">{nominator}</a>；非一人主編"
    else:
        nomin_string = f"提名：<a href=\"{nominator_link}\">{nominator}</a>；作者：<a href=\"{author_link}\">{author}</a>"

    return f"（{nomin_string}；類別：{entry.entry_type}）"


def generate_message_content(diff_report: DYKCDiffReport) -> str:
    rows: list[str] = []

    now = datetime.now(timezone.utc)
    rows.append(f"<b>新條目評選每日簡報（{now.year}年{now.month}月{now.day}日）</b>")
    rows.append(f"自上次簡報以來，以下是<a href=\"{DYKC_SHORT_LINK}\">新條目評選</a>的變化：")

    # New entries
    rows.append(HEADING_NEW_ENTRY.format(num=len(diff_report.new_entries)))
    for title, entry in diff_report.new_entries.items():
        votes_display = generate_votes_display(entry.entry_votes)
        entry_notes = generate_new_entry_notes(entry)
        rows.append(ADDED_ROW.format(
            pagelink=DYKC_SHORT_LINK + '#' + title,
            pagename=title,
            votes_display=votes_display,
            entry_notes=entry_notes
        ))

    # Vote Differences
    rows.append(HEADING_CHANGES_ENTRY.format(
        num=len(diff_report.vote_differences)))
    for title, delta in diff_report.vote_differences.items():
        entry = diff_report.new_votes.get(title)
        entry_votes = entry.entry_votes

        votes_display = generate_votes_display(entry_votes)
        votes_delta_display = generate_votes_delta_display(delta)
        rows.append(CHANGED_ROW.format(
            pagelink=DYKC_SHORT_LINK + '#' + title,
            pagename=title,
            votes_display=votes_display,
            votes_delta_display=votes_delta_display
        ))

    # Removed entries
    rows.append(HEADING_ENDED_ENTRY.format(
        num=len(diff_report.removed_entries)))
    for title, passed in diff_report.removed_entries.items():
        result = REMOVED_RESULT_PASSED if passed else REMOVED_RESULT_FAILED
        rows.append(REMOVED_ROW.format(
            pagelink=DYKC_SHORT_LINK + '#' + title,
            pagename=title,
            result=result
        ))

    rows.append("\n" + PLAIN_LIST_MARKER.join([
        '<a href="https://github.com/Emojigit/zhwiki_nomination_daily_digest/">原始碼</a>',
        '<a href="https://zh.wikipedia.org/wiki/User_talk:1F616EMO">錯誤回報</a>'
    ]))

    print(rows)
    return "\n".join(rows)


def send_newsletter_by_diff_report(diff_report: DYKCDiffReport, config: Mapping):
    message_content = generate_message_content(diff_report)

    send_daily_digest(message_content, 'HTML', config)
