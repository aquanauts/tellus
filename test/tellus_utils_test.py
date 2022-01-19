from tellus.tellus_sources.github_helper import verify_github_user_validity
from tellus.tellus_utils import (
    now,
    datetime_string,
    datetime_from_string,
    prettify_string,
    prettify_datetime,
)


def test_tellus_time():
    now_datetime = now()
    now_string = now_datetime.isoformat()

    assert now_string == datetime_string(now_datetime)
    assert now_datetime == datetime_from_string(now_string)


class MockGithubUser:
    def __init__(self, user_dict):
        self.__dict__ = user_dict


def test_verify_github_validity():
    github_user = MockGithubUser(
        {"name": "Quislet", "suspended_at": None, "login": "quislet",}
    )
    assert "quislet" == verify_github_user_validity(github_user)

    github_user = MockGithubUser(
        {"name": None, "suspended_at": None, "login": "tellus",}
    )
    assert verify_github_user_validity(github_user) is None, "No name means not valid."

    github_user = MockGithubUser(
        {"name": "Projectra", "suspended_at": "anything", "login": "projectra",}
    )
    assert (
        verify_github_user_validity(github_user) is None
    ), "Any supsended at means not valid."


# def test_vault_availability():
#     # This is to verify that we can access vault - if this fails, you are probably not connected to our network
#     secret = get_credentials_from_vault(path="tellus")
#     assert secret == {'TEST': 'testtoken'}


def test_prettify_datetime():
    test_string = "2021-02-01T17:49:54.922667+00:00"
    test_datetime = datetime_from_string(test_string)

    assert prettify_string(test_string) == prettify_datetime(test_datetime)

    assert prettify_string(test_string) == "2021-02-01 17:49 UTC"
    assert (
        prettify_string("foo") == "foo"
    ), "If it isn't a valid string, it's just going to return it."
