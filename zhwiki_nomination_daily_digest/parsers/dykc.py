"""Parse contents of Did You Know (DYK) nomiation pages and discussion pages."""

from io import TextIOWrapper
from dataclasses import dataclass
from pywikibot import Site, Page
from pywikibot.pagegenerators import PreloadingGenerator
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class DYKEntry:
    """Vote counts of a DYKC entry."""

    vote_support: int
    vote_oppose: int
    vote_problematic: int

    def __sub__(self, other: "DYKEntry") -> "DYKEntry":
        if not isinstance(other, DYKEntry):
            return NotImplemented
        return DYKEntry(
            vote_support=self.vote_support - other.vote_support,
            vote_oppose=self.vote_oppose - other.vote_oppose,
            vote_problematic=self.vote_problematic - other.vote_problematic,
        )

    def is_zero(self) -> bool:
        return self.vote_support == 0 and self.vote_oppose == 0 and self.vote_problematic == 0


def get_active_votes(dykc_page_content: str) -> dict[str, DYKEntry]:
    """Parse the HTML of a DYKC nomination and voting page, returns the entries.

    Parameters
    ----------
    dykc_page_content : str
        Raw HTML of the voting page obtained via action=parse

    Returns
    -------
    dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts.
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
    entries: dict[str, DYKEntry] = {}

    for element in reversed(all_elements):
        classes = element.get('class', [])

        if 'zhwpVoteSupport' in classes:
            vote_support += 1
        elif 'zhwpVoteOppose' in classes:
            vote_oppose += 1
        elif 'zhwpDYKwq' in classes:
            vote_problematic += 1
        elif 'dykarticle' in classes:
            article_title = element.get_text().strip().replace(' ', '_')
            entries[article_title] = DYKEntry(
                vote_support=vote_support,
                vote_oppose=vote_oppose,
                vote_problematic=vote_problematic,
            )

            vote_support = 0
            vote_oppose = 0
            vote_problematic = 0

    return entries


def get_active_votes_from_page(page: Page, force: bool = False) -> dict[str, DYKEntry]:
    """Parse the HTML of a DYKC nomination and voting page, returns the entries.

    Parameters
    ----------
    page : pywikibot.Page
        Page object of the voting page
    force : bool, optional
        Whether to force a refresh of the page content, by default False

    Returns
    -------
    dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts.
    """

    content = page.get_parsed_page(force=force)
    return get_active_votes(content)


def export_votes_to_file(vote_data: dict[str, DYKEntry], fd: TextIOWrapper):
    """Export the vote data to a file.

    Parameters
    ----------
    vote_data : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts.
    fd : TextIOWrapper
        File descriptor to write the data to.
    """
    for title, entry in vote_data.items():
        fd.write(
            f"{title}\t{entry.vote_support}\t{entry.vote_oppose}\t{entry.vote_problematic}\n")


def get_vote_differences(old_votes: dict[str, DYKEntry], new_votes: dict[str, DYKEntry]) -> dict[str, DYKEntry]:
    """Calculate the differences between two sets of vote data.

    Parameters
    ----------
    old_votes : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the previous state.
    new_votes : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the current state.

    Returns
    -------
    dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote count differences.
    """
    differences: dict[str, DYKEntry] = {}
    for title, new_entry in new_votes.items():
        old_entry = old_votes.get(title)
        if old_entry is not None:
            diff_entry = new_entry - old_entry
            if not diff_entry.is_zero():
                differences[title] = diff_entry
    return differences


def get_removed_entries(old_votes: dict[str, DYKEntry], new_votes: dict[str, DYKEntry]) -> list[str]:
    """Get the list of entries that were present in old_votes but not in new_votes.

    Parameters
    ----------
    old_votes : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the previous state.
    new_votes : dict[str, DYKEntry]
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


def get_added_entries(old_votes: dict[str, DYKEntry], new_votes: dict[str, DYKEntry]) -> dict[str, DYKEntry]:
    """Get the list of entries that were present in new_votes but not in old_votes.

    Parameters
    ----------
    old_votes : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the previous state.
    new_votes : dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts from the current state.

    Returns
    -------
    dict[str, DYKEntry]
        List of page titles that were added.
    """
    added_entries = {}
    for title, entry in new_votes.items():
        if title not in old_votes:
            added_entries[title] = entry
    return added_entries


def import_votes_from_file(fd: TextIOWrapper) -> dict[str, DYKEntry]:
    """Import the vote data from a file.

    Parameters
    ----------
    fd : TextIOWrapper
        File descriptor to read the data from.

    Returns
    -------
    dict[str, DYKEntry]
        Dictionary of page titles to entry metadata and vote counts.
    """
    vote_data: dict[str, DYKEntry] = {}
    for line in fd:
        sline = line.strip()
        if sline == '':
            continue

        title, support, oppose, problematic = sline.split('\t')
        vote_data[title] = DYKEntry(
            vote_support=int(support),
            vote_oppose=int(oppose),
            vote_problematic=int(problematic),
        )
    return vote_data


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

    new_votes: dict[str, DYKEntry]
    removed_entries: dict[str, bool]
    vote_differences: dict[str, DYKEntry]
    new_entries: dict[str, DYKEntry]


def generate_diff_report(old_votes: dict[str, DYKEntry], new_votes: dict[str, DYKEntry], site: Site) -> DYKCDiffReport:
    """Generate a report of differences between DYKC vote counts.

    Parameters
    ----------
    old_votes : dict[str, DYKEntry]
        Data of old vote.
    new_votes : dict[str, DYKEntry]
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
        new_votes=new_votes,
        removed_entries=removed_entries,
        vote_differences=vote_differences,
        new_entries=new_entries,
    )
