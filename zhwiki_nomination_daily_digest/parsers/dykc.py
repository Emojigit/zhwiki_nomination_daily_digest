"""Parse contents of Did You Know (DYK) nomiation pages and discussion pages."""

from datetime import datetime
from collections import OrderedDict
from dataclasses import dataclass
from pywikibot import Site, Page
from pywikibot.pagegenerators import PreloadingGenerator
from pywikibot.textlib import extract_templates_and_params
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class DYKVoteCount:
    """Vote counts of a DYKC entry."""

    vote_support: int
    vote_oppose: int
    vote_problematic: int

    def __sub__(self, other: "DYKVoteCount") -> "DYKVoteCount":
        if not isinstance(other, DYKVoteCount):
            return NotImplemented
        return DYKVoteCount(
            vote_support=self.vote_support - other.vote_support,
            vote_oppose=self.vote_oppose - other.vote_oppose,
            vote_problematic=self.vote_problematic - other.vote_problematic,
        )

    def is_zero(self) -> bool:
        return self.vote_support == 0 and self.vote_oppose == 0 and self.vote_problematic == 0


@dataclass(frozen=True)
class DYKEntry:
    """Metadata of a DYKC entry. Data collected from DYKEntry templates."""

    entry_hash: str
    entry_article: str
    entry_question: str
    entry_image: str
    entry_type: str
    entry_author: str
    entry_nominator: str
    entry_timestamp: datetime
    entry_votes: DYKVoteCount


def get_active_votes(dykc_page_content: str, dykc_page_templates: list[tuple[str, OrderedDict[str, str]]]) -> OrderedDict[str, DYKEntry]:
    """Parse the HTML of a DYKC nomination and voting page, returns the entries.

    Parameters
    ----------
    dykc_page_content : str
        Raw HTML of the voting page obtained via action=parse

    Returns
    -------
    OrderedDict[str, DYKEntry]
        Dictionary of article titles to DYKC entries and vote counts.
    """
    soup = BeautifulSoup(dykc_page_content, 'html.parser')

    for invalid_tag in soup.find_all(['s', 'strike', 'del']):
        invalid_tag.decompose()

    for void_element in soup.find_all(class_='zhwpVotevoid'):
        void_element.decompose()

    all_elements = soup.find_all(True)

    vote_support = 0
    vote_oppose = 0
    vote_problematic = 0
    entry_votes: dict[str, DYKVoteCount] = {}

    for element in reversed(all_elements):
        classes = element.get('class', [])

        if 'zhwpVoteSupport' in classes:
            vote_support += 1
        elif 'zhwpVoteOppose' in classes:
            vote_oppose += 1
        elif 'zhwpDYKwq' in classes:
            vote_problematic += 1
        elif 'dykentry_hash' in classes:
            entry_hash = element.get_text().strip()
            entry_votes[entry_hash] = DYKVoteCount(
                vote_support=vote_support,
                vote_oppose=vote_oppose,
                vote_problematic=vote_problematic,
            )

            vote_support = 0
            vote_oppose = 0
            vote_problematic = 0

    entries: OrderedDict[str, DYKEntry] = OrderedDict()

    for data in dykc_page_templates:
        if data[0] != "DYKEntry":
            continue

        params = data[1]
        entry_hash = params.get('hash')
        if entry_hash not in entry_votes:
            continue

        entry_article = params.get('article', '').replace('_', ' ')

        entries[entry_article] = DYKEntry(
            entry_hash=entry_hash,
            entry_article=entry_article,
            entry_author=params.get('author', ''),
            entry_question=params.get('question', ''),
            entry_image=params.get('image', ''),
            entry_type=params.get('type', ''),
            entry_nominator=params.get('nominator', ''),
            entry_timestamp=datetime.utcfromtimestamp(
                int(params.get('timestamp', 0))),
            entry_votes=entry_votes[entry_hash]
        )

    return entries


def get_active_votes_from_page(page: Page, force: bool = False) -> OrderedDict[str, DYKEntry]:
    """Parse a DYKC nomination and voting page, returns the entries.

    Parameters
    ----------
    page : pywikibot.Page
        Page object of the voting page
    force : bool, optional
        Whether to force a refresh of the page content, by default False

    Returns
    -------
    OrderedDict[str, DYKEntry]
        Dictionary of article titles to DYKC entries and vote counts.
    """

    content = page.get_parsed_page(force=force)
    templates = page.raw_extracted_templates
    return get_active_votes(content, templates)


def get_active_votes_from_page_revision(site: Site, revision: int) -> OrderedDict[str, DYKEntry]:
    """Parse a DYKC nomination and voting page at a specific revision, returns the entries.

    Parameters
    ----------
    revision : int
        Revision to parse

    Returns
    -------
    OrderedDict[str, DYKEntry]
        Dictionary of article titles to DYKC entries and vote counts.
    """

    req = site.simple_request(
        action='parse',
        oldid=revision,
        prop=[
            'text',
            'wikitext',
        ],
    )
    data = req.submit()

    try:
        content = data['parse']['text']['*']
        wikitext = data['parse']['wikitext']['*']
    except KeyError as e:
        raise KeyError(f'API parse response lacks {e} key') from e

    templates = extract_templates_and_params(wikitext, True, True)
    return get_active_votes(content, templates)


def get_vote_differences(old_votes: OrderedDict[str, DYKEntry], new_votes: OrderedDict[str, DYKEntry]) -> dict[str, DYKVoteCount]:
    """Calculate the differences between two sets of vote data.

    Parameters
    ----------
    old_votes : list[DYKEntry]
        List of entries from the previous state.
    new_votes : dict[str, DYKVoteCount]
        List of entries from the current state.

    Returns
    -------
    dict[str, DYKVoteCount]
        Dictionary of page titles to entry metadata and vote count differences.
    """
    differences: dict[str, DYKVoteCount] = {}
    for article, entry in new_votes.items():
        if article not in old_votes:
            continue
        diff = entry.entry_votes - old_votes[article].entry_votes
        if not diff.is_zero():
            differences[article] = diff
    return differences


def get_removed_entries(old_votes: OrderedDict[str, DYKEntry], new_votes: OrderedDict[str, DYKEntry]) -> list[str]:
    """Get the list of entries that were present in old_votes but not in new_votes.

    Parameters
    ----------
    old_votes : OrderedDict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the previous state.
    new_votes : OrderedDict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the current state.

    Returns
    -------
    list[str]
        List of page titles that were removed.
    """
    removed_entries = []
    for title in old_votes.keys():
        if title not in new_votes:
            removed_entries.append(title)
    return removed_entries


def get_added_entries(old_votes: OrderedDict[str, DYKEntry], new_votes: OrderedDict[str, DYKEntry]) -> OrderedDict[str, DYKEntry]:
    """Get the list of entries that were present in new_votes but not in old_votes.

    Parameters
    ----------
    old_votes : OrderedDict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the previous state.
    new_votes : OrderedDict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the current state.

    Returns
    -------
    OrderedDict[str, DYKEntry]
        List of page titles that were added.
    """
    added_entries = OrderedDict()
    for title, entry in new_votes.items():
        if title not in old_votes:
            added_entries[title] = entry
    return added_entries


def get_ended_vote_status_from_talkpage(page: Page) -> bool:
    """Check in an archived DYK voting entry whether the previoud vote have passed.

    Parameters
    ----------
    page : Page
        Page object of the archive page

    Returns
    -------
    bool
        Whether the most recent nomination have passed.False may mean not passed
        or nomination not found.
    """

    templates = page.raw_extracted_templates
    dykarchive = None

    # In case the article have been improved multiple times and got nominated
    # more than once, assume the latest is what we're looking for.
    for template in reversed(templates):
        if template[0] == 'DYKEntry/archive':
            dykarchive = template
            break

    if dykarchive is None:
        return False

    return dykarchive[1].get('result') == '^'


@dataclass
class DYKCDiffReport:
    """Report of differeneces between DYKC vote counts."""

    old_votes: OrderedDict[str, DYKEntry]
    new_votes: OrderedDict[str, DYKEntry]
    removed_entries: dict[str, bool]
    vote_differences: OrderedDict[str, DYKVoteCount]
    new_entries: OrderedDict[str, DYKEntry]


def generate_diff_report(old_votes: OrderedDict[str, DYKEntry], new_votes: OrderedDict[str, DYKEntry], site: Site) -> DYKCDiffReport:
    """Generate a report of differences between DYKC vote counts.

    Parameters
    ----------
    old_votes : OrderedDict[str, DYKEntry]
        Data of old vote.
    new_votes : OrderedDict[str, DYKEntry]
        Data of new vote.

    Returns
    -------
    DYKCDiffReport
        The report of differeneces for a newsletter.
    """

    removed_entries_list = get_removed_entries(old_votes, new_votes)
    removed_entries_pagesgen = zip(
        removed_entries_list,
        PreloadingGenerator(Page(site, title).toggleTalkPage()
                            for title in removed_entries_list)
    )
    removed_entries = {
        title: get_ended_vote_status_from_talkpage(talkpage)
        for title, talkpage in removed_entries_pagesgen}

    vote_differences = get_vote_differences(old_votes, new_votes)
    new_entries = get_added_entries(old_votes, new_votes)

    return DYKCDiffReport(
        old_votes=old_votes,
        new_votes=new_votes,
        removed_entries=removed_entries,
        vote_differences=vote_differences,
        new_entries=new_entries,
    )
