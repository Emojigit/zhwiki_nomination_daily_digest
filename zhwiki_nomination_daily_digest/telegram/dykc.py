"""Telegram sender of the DYKC Daily Digest."""

from typing import Mapping
from datetime import datetime, timezone

from telebot.types import LinkPreviewOptions

from ..parsers.dykc import DYKEntry, DYKVoteCount, DYKCDiffReport
from . import _tag, publish_telegraph_page, send_telegram_messages

DYKC_LINK = r'https://zh.wikipedia.org/wiki/Wikipedia:%E6%96%B0%E6%9D%A1%E7%9B%AE%E6%8E%A8%E8%8D%90/%E5%80%99%E9%80%89'
TELEGRAM_MESSAGE_FORMAT = "<b>{title}</b>\n\n自上次簡報以來，有 {new} 個新條目提交評選、{diff} 個新條目有票數變化、{end} 個新條目評選已完結。"


def generate_votes_display(entry: DYKVoteCount) -> str:
    return f"({entry.vote_support}/{entry.vote_oppose}/{entry.vote_problematic})"


def generate_delta_number_display(delta: int) -> str | dict:
    if delta > 0:
        return _tag('b', f"+{delta}")
    elif delta < 0:
        return _tag('b', str(delta))
    else:
        return '0'


def generate_votes_delta_display(delta: DYKVoteCount) -> list:
    return [
        '(',
        generate_delta_number_display(delta.vote_support),
        '/',
        generate_delta_number_display(delta.vote_oppose),
        '/',
        generate_delta_number_display(delta.vote_problematic),
        ') [',
        generate_delta_number_display(delta.vote_support - delta.vote_oppose),
        ']',
    ]


def generate_new_entry_notes(entry: DYKEntry) -> dict:
    author = entry.entry_author
    nominator = entry.entry_nominator

    author_link = "https://zh.wikipedia.org/wiki/User:" + author
    nominator_link = "https://zh.wikipedia.org/wiki/User:" + nominator

    entry_type = entry.entry_type

    nodes = []

    if author == nominator:
        nodes.append('（提名/作者：')
        nodes.append(_tag('a', author, href=author_link))
        nodes.append(f'；類別：{entry_type}）')
    elif author == '':
        nodes.append('（提名：')
        nodes.append(_tag('a', nominator, href=nominator_link))
        nodes.append(f'；非一人主編；類別：{entry_type}）')
    else:
        nodes.append('（提名')
        nodes.append(_tag('a', nominator, href=nominator_link))
        nodes.append('；作者：')
        nodes.append(_tag('a', author, href=author_link))
        nodes.append(f'；類別：{entry_type}）')

    return nodes


def generate_new_entry_line(entry: DYKEntry) -> list:
    votes_display = generate_votes_display(entry.entry_votes)
    entry_notes = generate_new_entry_notes(entry)

    nodes = []
    nodes.append(_tag(
        'a',
        _tag('b', entry.entry_article),
        href=DYKC_LINK + '#' + entry.entry_article
    ))
    nodes.append('：' + votes_display)
    nodes.extend(entry_notes)

    return nodes


def generate_vote_diff_line(entry: DYKEntry, diff: DYKVoteCount) -> list:
    votes_display = generate_votes_display(entry.entry_votes)
    votes_delta_display = generate_votes_delta_display(diff)

    nodes = []
    nodes.append(_tag(
        'a',
        _tag('b', entry.entry_article),
        href=DYKC_LINK + '#' + entry.entry_article
    ))
    nodes.append('：' + votes_display + ' ')
    nodes.extend(votes_delta_display)

    return nodes


def generate_vote_ended_line(title: str, passed: bool) -> list:
    result = '通過' if passed else '不通過'
    fragment = "#新条目推荐讨论" if passed else "#未通过的新条目推荐讨论"

    return [
        _tag(
            'a',
            _tag('b', title),
            href='https://zh.wikipedia.org/wiki/Talk:' + title + fragment
        ),
        '：' + result
    ]


def generate_telegraph_content(diff_report: DYKCDiffReport) -> list:
    """Generate a newsletter ready for posting onto talk pages.

    Parameters
    ----------
    diff_report: DYKCDiffReport
        The report of vote differeneces.

    Returns
    -------
    list
        List of Nodes for Telegraph
    """

    nodes = []
    nodes.append(_tag('p', [
        '自上次簡報以來，以下是',
        _tag('a', '新條目評選', href=DYKC_LINK),
        '的變化：',
    ]))

    # New entries
    nodes.append(_tag('p', [
        _tag('b', '新增條目：'),
        f'共有 {len(diff_report.new_entries)} 個新條目提交評選：',
    ]))
    nodes.append(_tag(
        'ul',
        [
            _tag('li', generate_new_entry_line(entry))
            for entry in diff_report.new_entries.values()
        ]
    ))

    # Vote Differences
    nodes.append(_tag('p', [
        _tag('b', '票數變化：'),
        f'共有 {len(diff_report.vote_differences)} 個新條目有票數變化：',
    ]))
    nodes.append(_tag(
        'ul',
        [
            _tag('li', generate_vote_diff_line(
                diff_report.new_votes.get(title),
                diff
            ))
            for title, diff in diff_report.vote_differences.items()
        ]
    ))

    # Removed entries
    nodes.append(_tag('p', [
        _tag('b', '完成評選：'),
        f'共有 {len(diff_report.removed_entries)} 個新條目評選已完結：',
    ]))
    nodes.append(_tag(
        'ul',
        [
            _tag('li', generate_vote_ended_line(title, passed))
            for title, passed in diff_report.removed_entries.items()
        ]
    ))

    return nodes


def send_newsletter_by_diff_report(diff_report: DYKCDiffReport, config: Mapping):
    telegraph_content = generate_telegraph_content(diff_report)

    now = datetime.now(timezone.utc)
    title = f"新條目評選每日簡報（{now.year}年{now.month}月{now.day}日）"

    telegraph_url = publish_telegraph_page(title, telegraph_content, config)

    telegram_message = TELEGRAM_MESSAGE_FORMAT.format(
        title=title,
        new=len(diff_report.new_entries),
        diff=len(diff_report.vote_differences),
        end=len(diff_report.removed_entries)
    )

    send_telegram_messages(telegram_message, config, {
        'parse_mode': 'HTML',
        'link_preview_options': LinkPreviewOptions(url=telegraph_url, prefer_small_media=True)
    })
