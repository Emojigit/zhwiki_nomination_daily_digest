"""The DYKC Daily Digest newsletter generator and sender bot."""

from datetime import datetime, timezone
from pywikibot import Site, Page, logging
from pywikibot.exceptions import Error as PWBError
import yaml

from ..parsers import dykc
from ..newsletters import dykc as ndykc
from . import DailyDigestSendMode


def run_bot(
    old_votes_path: str,
    site: Site,
    dykc_title: str = 'Wikipedia:新条目推荐/候选',
    target_title: str = 'User:1F616EMO/條目評選每日簡報/新條目評選',
    send_mode: DailyDigestSendMode = DailyDigestSendMode.DRY_RUN,
    summary: str = '發送新條目評選每日簡報'
):
    old_votes = None
    try:
        with open(old_votes_path, 'r', encoding='utf-8') as f:
            old_votes = dykc.import_votes_from_file(f)
    except FileNotFoundError:
        logging.warning(
            f"Old votes file {old_votes_path} not found. Assuming this is the first run.")

    dykc_page = Page(site, dykc_title)
    new_votes = dykc.get_active_votes_from_page(dykc_page)

    if old_votes is not None:
        diff_report = dykc.generate_diff_report(old_votes, new_votes, site)
        newsletter_content = ndykc.generate_newsletter_content(diff_report)

        if newsletter_content is None:
            logging.info("No changes since last send, quitting.")
            return 0

        now = datetime.now(timezone.utc)
        newsletter_title = f"新條目評選每日簡報（{now.year}年{now.month}月{now.day}日）"

        logging.info(f"Newsletter title: {newsletter_title}")
        logging.info("Newsletter content:\n" + newsletter_content)

        if send_mode == DailyDigestSendMode.MMS:
            logging.info(
                f"Sending newsletter via MassMessage to list {target_title}...")
            token = site.get_tokens(['csrf']).get('csrf')
            request = site.simple_request(
                action='massmessage',
                spamlist=target_title,
                subject=newsletter_title,
                message=newsletter_content,
                token=token,
            )
            request.submit()
            logging.info("Newsletter sent via MassMessage.")
        else:
            # Both DIRECT and DRY_RUN needs to fetch a list of send targets from the given page.
            logging.info(
                f"Fetching list of send targets from {target_title}...")
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
                logging.info(
                    "Direct send mode: sending newsletters to each target...")
                for target in target_list:
                    logging.info(f"Sending newsletter to {target.title()}...")
                    try:
                        site.editpage(
                            page=target,
                            summary=summary,
                            bot=True,
                            section="new",
                            sectiontitle=newsletter_title,
                            text=newsletter_content,
                        )
                    except PWBError as e:
                        logging.error(f"Error sending newsletter: {e}")

    # Save new votes to file for next run
    with open(old_votes_path, 'w', encoding='utf-8') as f:
        dykc.export_votes_to_file(new_votes, f)
        logging.info(f"Saved new votes to {old_votes_path}.")


def main(config_file_path: str = './config.yaml') -> int:
    """Run the DYKC Daily Digest bot with the given configuration file.

    Parameters
    ----------
    config_file_path : str, optional
        Path to the YAML configuration file, by default './config.yaml'
    """
    with open(config_file_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Configured in user-config.py, not in config.yaml
    site = Site()

    run_bot(
        old_votes_path=config['old_votes_path'],
        site=site,
        dykc_title=config.get('dykc_title', 'Wikipedia:新条目推荐/候选'),
        target_title=config.get(
            'target_title', 'User:1F616EMO/條目評選每日簡報/新條目評選'),
        send_mode=DailyDigestSendMode(config.get(
            'send_mode', DailyDigestSendMode.DRY_RUN)),
        summary=config.get('summary', '發送新條目評選每日簡報')
    )

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
