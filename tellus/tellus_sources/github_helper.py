import logging

import requests
from github import Github, GithubException
from sortedcontainers import SortedSet

from tellus.configuration import GITHUB_ACCESS_TOKEN, GITHUB_API_URL


def gethub():
    """
    :return: an initialized instance of the github utility.
    """
    # Thanks, I'll be here all week.
    return Github(base_url=GITHUB_API_URL, login_or_token=GITHUB_ACCESS_TOKEN)


def download_github_file(file_url, access_token=GITHUB_ACCESS_TOKEN):
    request = requests.get(file_url, headers={"Authorization": f"token {access_token}"})
    return request.text


def verify_github_user_validity(github_user):
    if github_user.name is None or github_user.suspended_at is not None:
        logging.info(
            "Github user '%s' considered invalid for Tellus:  name is '%s', suspended at %s",
            github_user.login,
            github_user.name,
            github_user.suspended_at,
        )
        return None

    return github_user.login


def retrieve_valid_github_usernames():
    # This is a bit of a temporary hack to restrict our user list to those in github...
    confluence_users = SortedSet(["tellus"])
    try:
        logging.info("Trying to get valid users from Github...")
        github = gethub()
        users = github.get_users()
        for user in users:
            username = verify_github_user_validity(user)
            if username:
                confluence_users.add(username)
    except (ConnectionError, OSError, GithubException) as exception:
        message = str(exception)
        logging.error(
            "Failed to connect to Github (may mean we aren't on the network): %s",
            message[0 : min(200, len(message))],
        )  # That Github Exception gets very very long

    return confluence_users
