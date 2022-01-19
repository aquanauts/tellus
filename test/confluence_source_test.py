from unittest.mock import MagicMock

from atlassian import Confluence
from requests import RequestException

from tellus.tellus_sources.confluence_helper import (
    retrieve_valid_confluence_usernames,
    CONFLUENCE_HUMAN_USERS,
)
from tellus.sources import Sourcer
from tellus.tellus_sources.confluence_source import ConfluenceSource
from test.tells_test import create_test_teller


async def test_load():
    teller = create_test_teller()

    confluence = MagicMock()

    source = ConfluenceSource(teller, confluence)
    await Sourcer.run_load_source(source)
    assert source.load_completed


def get_group_members(group_name):
    group = {
        CONFLUENCE_HUMAN_USERS: [
            {"username": "cosmicboy"},
            {"username": "saturngirl"},
            {"username": "lightninglad"},
        ],
    }.get(group_name)

    if group is None:
        raise RequestException("No Group specified for get_group_members")

    return group


async def test_retrieve_valid_confluence_usernames():
    confluence = MagicMock(type=Confluence)
    confluence.get_group_members.side_effect = get_group_members

    usernames = retrieve_valid_confluence_usernames(confluence)
    assert list(usernames) == ["cosmicboy", "lightninglad", "saturngirl"]
