"""The DYKC Daily Digest newsletter generator and sender bot."""

import pickle
from typing import Mapping

import yaml
from pywikibot import Site, Page, logging

from ..parsers import dykc


def run_bot(site: Site, config: Mapping) -> int:
    old_votes_path = config.get('old_votes_path', './old_votes')
    old_votes = None
    try:
        with open(old_votes_path, 'rb') as f:
            old_votes = pickle.load(f)
    except FileNotFoundError:
        logging.warning(
            f"Old votes file {old_votes_path} not found. Assuming this is the first run.")

    dykc_title = config.get('dykc_title', 'Wikipedia:新条目推荐/候选')
    dykc_page = Page(site, dykc_title)
    new_votes = dykc.get_active_votes_from_page(dykc_page)

    if old_votes is not None:
        diff_report = dykc.generate_diff_report(old_votes, new_votes, site)

        if not diff_report.has_changes:
            logging.info("No changes since last send, quitting.")
            return 0

        newsletter_config = config.get('newsletter', {})
        if newsletter_config.get('enabled', False):
            try:
                # pylint: disable=import-outside-toplevel
                from ..newsletters import dykc as ndykc
            except ImportError:
                logging.warning("Failed to import on-wiki newsletter module.")
            else:
                logging.info("Sending on-wiki newsletter...")
                ndykc.send_newsletter_by_diff_report(
                    site, diff_report, newsletter_config)
        else:
            logging.info("Skipping on-wiki newsletter.")

        telegram_config = config.get('telegram', {})
        if telegram_config.get('enabled', False):
            try:
                # pylint: disable=import-outside-toplevel
                from ..telegram import dykc as tdykc
            except ImportError:
                logging.warning("Failed to import Telegram module.")
            else:
                logging.info("Sending Telegram messages...")
                tdykc.send_newsletter_by_diff_report(
                    diff_report, telegram_config)
        else:
            logging.info("Skipping on-wiki newsletter.")

    # Save new votes to file for next run
    with open(old_votes_path, 'wb') as f:
        pickle.dump(new_votes, f)
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

    return run_bot(site, config)


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else './config.yaml'
    sys.exit(main(config_path))
