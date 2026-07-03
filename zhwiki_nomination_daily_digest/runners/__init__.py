"""Bot runners of nomination daily digests."""

from enum import StrEnum

from pywikibot import Site, Page, logging
from pywikibot.exceptions import Error


class DailyDigestSendMode(StrEnum):
    """Sending mode of the bot."""

    DRY_RUN = "dry_run"
    DIRECT = "direct"
    MMS = "mms"


def send_daily_digest(
    site: Site,
    subject: str,
    content: str,
    target_title: str,
    send_mode: DailyDigestSendMode,
    summary: str
):
    if send_mode not in DailyDigestSendMode:
        raise ValueError

    if send_mode == DailyDigestSendMode.MMS:
        logging.info(
            f"Sending newsletter via MassMessage to list {target_title}...")
        token = site.get_tokens(['csrf']).get('csrf')
        request = site.simple_request(
            action='massmessage',
            spamlist=target_title,
            subject=subject,
            message=content,
            token=token,
        )
        request.submit()
        logging.info("Newsletter sent via MassMessage.")
        return

    # direct or dry_run

    logging.info(f"Fetching list of send targets from {target_title}...")
    target_page = Page(site, target_title)
    target_list = []

    for target in target_page.linkedPages():
        namespace = target.namespace()

        if namespace == 4 or namespace % 2 == 1:
            logging.info(f"Get  {target.title()}")
            target_list.append(target)
        else:
            logging.info(f"Skip {target.title()}")

    if send_mode == DailyDigestSendMode.DRY_RUN:
        logging.info("Dry run mode: not sending newsletters.")
    elif send_mode == DailyDigestSendMode.DIRECT:
        logging.info("Direct send mode: sending newsletters to each target...")
        for target in target_list:
            logging.info(f"Sending newsletter to {target.title()}...")
            try:
                site.editpage(
                    page=target,
                    summary=summary,
                    bot=True,
                    section="new",
                    sectiontitle=subject,
                    text=content,
                )
            except Error as e:
                logging.error(f"Error sending newsletter: {e}")
