import logging

from atlassian import Confluence
from atlassian.errors import ApiPermissionError
from sortedcontainers import SortedSet

from tellus.configuration import (
    CONFLUENCE_URL,
    CONFLUENCE_API_USERNAME,
    CONFLUENCE_API_PASSWORD,
)

CONFLUENCE_HUMAN_USERS = (
    "user"  # the Confluence group containing all (and only) humans
)


def get_confluence():
    """
    :return: an initialized instance of the github utility.
    """
    return Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_API_USERNAME,
        password=CONFLUENCE_API_PASSWORD,
    )


def retrieve_valid_confluence_usernames(confluence):
    """
    Retrieve the full set of Humans from Confluence (currently our easiest way of doing that.
    :return: a list of usernames considered to be currently valid in Confluence
    """
    valid_usernames = SortedSet()
    try:
        logging.info(
            "Trying to get valid users from Confluence, from group '%s'.  Using username '%s'.",
            CONFLUENCE_HUMAN_USERS,
            CONFLUENCE_API_USERNAME,
        )
        confluence_users = confluence.get_group_members(
            group_name=CONFLUENCE_HUMAN_USERS
        )
        logging.info("Retrieved %s users.", len(confluence_users))
        for user in confluence_users:
            valid_usernames.add(user.get("username"))
    except ApiPermissionError as exception:
        message = str(exception)
        logging.error(
            "Connected to Confluence, but user '%s' does not appear to be able to retrieve users: %s",
            CONFLUENCE_API_USERNAME,
            message[0 : min(200, len(message))],
        )
    except (ConnectionError, OSError) as exception:
        message = str(exception)
        logging.error(
            "Failed to connect to Confluence (may mean we aren't on the network): %s",
            message[0 : min(200, len(message))],
        )

    return valid_usernames
