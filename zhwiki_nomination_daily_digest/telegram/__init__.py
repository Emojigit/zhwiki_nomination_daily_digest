"""Telegram senders of the daily digest."""

from enum import StrEnum

from telebot import TeleBot
from telebot.types import MessageEntity, LinkPreviewOptions

from pywikibot import logging


def send_daily_digest(message: str, parse_mode: str, config: dict):
    bot_token = config.get('bot_token')
    if bot_token is None:
        raise ValueError('bot_token not supplied!')

    bot = TeleBot(bot_token)

    common_params = {
        'text': message,
        'parse_mode': parse_mode,
        'link_preview_options': LinkPreviewOptions(is_disabled=True),
    }

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
