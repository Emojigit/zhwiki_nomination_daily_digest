"""Command-line utilities of the DYKC sender."""

import pickle
import yaml
from pywikibot import Site, logging

from ..parsers import dykc
from . import util_run


def init_by_revid(argv: list[str]) -> int:
    if len(argv) <= 2:
        logging.error(
            "Invalid usage. Usage: python -m zhwiki_nominatin_daily_digest.utils.dykc init_by_revid <revid> [<config>]")
        return 1

    try:
        revid = int(argv[2])
    except ValueError:
        logging.error(
            "Invalid usage. Usage: python -m zhwiki_nominatin_daily_digest.utils.dykc init_by_revid <revid> [<config>]")
        return 2

    config_file_path = argv[3] if len(argv) > 3 else './config.yaml'
    with open(config_file_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    site = Site()
    new_votes = dykc.get_active_votes_from_page_revision(site, revid)

    with open(config['old_votes_path'], 'wb') as f:
        pickle.dump(new_votes, f)
        logging.info(f"Saved new votes to {config['old_votes_path']}.")


if __name__ == "__main__":
    import sys
    sys.exit(util_run(sys.argv, {
        'init_by_revid': init_by_revid,
    }))
