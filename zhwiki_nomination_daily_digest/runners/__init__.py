"""Bot runners of nomination daily digests."""

from enum import StrEnum


class DailyDigestSendMode(StrEnum):
    """Sending mode of the bot."""

    DRY_RUN = "dry_run"
    DIRECT = "direct"
    MMS = "mms"
