"""Telegram senders of the daily digest."""

from typing import Mapping, Optional

from telebot import TeleBot
from telebot.types import MessageEntity, LinkPreviewOptions
from telegraph import Telegraph

from pywikibot import logging


def _tag(
    tag: str,
    children: str | dict | list[str | dict],
    href: Optional[str] = None,
    src: Optional[str] = None
) -> dict:
    attrs = None
    if href is not None or src is not None:
        attrs = {
            'href': href,
            'src': src
        }

    if isinstance(children, str) or isinstance(children, dict):
        children = [children]

    return {
        'tag': tag,
        'children': children,
        'attrs': attrs,
    }


def publish_telegraph_page(title: str, content: str | list, config: Mapping) -> str:
    telegraph_config = config.get('telegraph', {})
    access_token_path = telegraph_config.get(
        'access_token_path', './telegraph_token.txt')

    access_token = None
    try:
        with open(access_token_path, 'r', encoding='utf-8') as f:
            access_token = f.read().strip()
    except FileNotFoundError:
        pass

    telegraph = Telegraph(access_token)

    if access_token is None or access_token == '':
        if not telegraph_config.get('auto_create_account', False):
            raise RuntimeError(
                "Configuration file not found while auto_create_account is False")

        author_short_name = telegraph_config.get('author_short_name', '每日評選簡報')
        author_name = telegraph_config.get('author_name', '中文維基百科每日評選簡報')
        author_url = telegraph_config.get('author_url', None)

        ca_response = telegraph.create_account(
            author_short_name, author_name, author_url, True)

        logging.info("Successfully registered account, writing token")
        with open(access_token_path, 'w', encoding='utf-8') as f:
            f.write(ca_response['access_token'])

    response = telegraph.create_page(title, content)

    return response['url']


def send_telegram_messages(
    message: str,
    config: dict,
    common_params: dict = {}
):
    bot_token = config.get('bot_token')
    if bot_token is None:
        raise ValueError('bot_token not supplied!')

    bot = TeleBot(bot_token)

    common_params['text'] = message

    chats_config: dict[int, dict] = config.get('chats', {})
    for chat_id, chat_config in chats_config.items():
        if not chat_config.get('enabled', False):
            continue

        logging.info(f"Sending message to chat {chat_id}")

        assert isinstance(chat_id, int), f"Invalid type for chat_id: {chat_id}"

        this_params = {
            'chat_id': chat_id,
            'message_thread_id': chat_config.get('thread_id'),
            'disable_notification': chat_config.get('disable_notification', False),
        }

        union_params = common_params | this_params

        bot.send_message(**union_params)
