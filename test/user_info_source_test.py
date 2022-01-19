# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests

from unittest.mock import patch, MagicMock

import pytest
from asynctest import CoroutineMock
from atlassian import Confluence
from requests import RequestException

from tellus.configuration import (
    CONFLUENCE_URL,
    GITHUB_URL,
    TELLUS_INTERNAL,
    TELLUS_TOOL,
    TELLUS_USER,
)
from tellus.google_api_utils import retrieve_gsuite_user_directory
from tellus.sources import Sourcer
from tellus.tellus_sources.user_info_source import UserInfo
from tellus.users import UserManager, User
from test.tellus_test_utils import (
    this_test_name,
    assert_modified_since,
    assert_not_modified_since,
)
from test.tells_test import create_test_teller

TEST_CONFLUENCE_USER_DATA = {
    "cosmicboy": {"fullName": "Cosmic Boy", "email": "cosmic.boy@thelegion.org",},
    "saturngirl": {
        "fullName": "Saturn Girl",
        "email": "saturn.girl@thelegion.org",
        "avatarUrl": "/some/url/for/saturngirl",
    },
    "lightninglad": {
        "fullName": "Lightning Lad",
        "email": "lightning.lad@thelegion.com",
        # Has no avatar URL but shouldn't blow up
    },
    "quislet": {"fullName": "Quislet", "email": "quislet@thelegion.com",},
    "tellussvc": {
        "fullName": "Tellus Service Account",
        "email": "tellussvc@thelegion.com",
    },
}

TEST_GSUITE_USER_DATA = {
    "cosmic.boy@thelegion.org": {
        "addresses": [{"type": "home"}, {"type": "work"}],
        "emails": [
            {"address": "cosmicboy@thelegion.org", "primary": True},
            {"address": "rokk.krinn@gmail.com"},
        ],
        "etag": "¯\\_(ツ)_/¯",
        "externalIds": [{"type": "organization", "value": ""}],
        "id": "42",
        "kind": "admin#directory#user",
        "locations": [
            {
                "area": "desk",
                "buildingId": "20-N-Wacker-Dr",
                "floorName": "30",
                "type": "desk",
            }
        ],
        "name": {"familyName": "Krinn", "fullName": "Rokk Krinn", "givenName": "Rokk",},
        "organizations": [
            {
                "costCenter": "",
                "customType": "",
                "department": "",
                "description": "",
                "primary": True,
                "title": "",
            }
        ],
        "phones": [
            {"type": "vidphone", "value": "NOT A NUMBER"},
            {"type": "mobile", "value": "867 5309"},
        ],
        "primaryEmail": "cosmic.boy@thelegion.org",  # Intentionally wrong.
    },
    "saturngirl@thelegion.org": {  # intentionally wrong
        "emails": [  # these are intentionally wrong because they are currently not used
            {"address": "cosmicboy@thelegion.org", "primary": True,},
            {"address": "rokk.krinn@gmail.com"},
        ],
        "name": {
            "familyName": "Ardeen",
            "fullName": "Imra Ardeen",
            "givenName": "Imra",
        },
        "phones": [{"type": "mobile", "value": "888 8888"}],
        "primaryEmail": "saturn.girl@thelegion.org",  # Right, but shouldn't matter
    },
    "quislet@thelegion.org": {
        "emails": [  # these are intentionally wrong because they are currently not used
            {"address": "quislet@thelegion.org", "primary": True,},
        ],
        # "name": {"familyName": "", "fullName": "Quislet", "givenName": "",},  #  No names, to test weirdness
        "primaryEmail": "not_quislet@thelegion.org",
    },
    "groot@thelegion.org": {},  # Sorry Groot, you are not in the Legion...
}


@pytest.mark.asyncio
async def test_load_user_info():
    teller = create_test_teller()
    user_manager = UserManager(teller, ["quislet", "saturngirl", "tellus"])
    confluence = MagicMock(type=Confluence)
    confluence.get_mobile_parameters.return_value = {}
    source = UserInfo(user_manager, confluence)
    assert source.source_id == "user-info"
    assert source.display_name == "User Info"

    quislet = teller.create_tell("quislet", TELLUS_USER, "test_load_user_info")
    dray = teller.create_tell("dray", TELLUS_TOOL, "test_load_user_info")
    tellus = teller.create_tell("tellus", TELLUS_TOOL, "test_load_user_info")

    with patch(
        "tellus.tellus_sources.user_info_source.is_url_available", new=CoroutineMock()
    ) as mocked_iua:
        mocked_iua.return_value = True
        message = await Sourcer.run_load_source(source)

    assert source.load_completed, message

    assert dray.get_data(source.source_id) is None
    urls = quislet.get_data(source.source_id)
    assert len(urls) == 2
    assert urls["Confluence"] == f"{CONFLUENCE_URL}/display/~quislet"
    assert urls["Github"] == f"{GITHUB_URL}/quislet"

    assert user_manager.is_valid_username("saturngirl")
    assert user_manager.is_active_tellus_user("saturngirl")
    saturngirl = user_manager.get(
        "saturngirl"
    )  # Note the above process created SaturnGirl
    urls = saturngirl.tell.get_data(source.source_id)
    assert len(urls) == 2
    assert urls["Confluence"] == f"{CONFLUENCE_URL}/display/~saturngirl"
    assert urls["Github"] == f"{GITHUB_URL}/saturngirl"

    tellus = teller.get("tellus")
    assert not tellus.in_category(TELLUS_USER), "Tellus should still not be a User."
    assert (
        tellus.get_data(source.source_id) is None
    ), "Tellus should not have added URLs, since it is not a User."

    # Now let's test with no available URLs
    valid_usernames = user_manager.get_valid_usernames().update(
        ["wildfire", "timberwolf"]
    )
    user_manager.update_valid_usernames(valid_usernames)
    timberwolf = user_manager.get_or_create_valid_user("timberwolf")

    with patch(
        "tellus.tellus_sources.user_info_source.is_url_available", new=CoroutineMock()
    ) as mocked_iua:
        mocked_iua.return_value = False
        await source.load_source()

    assert (
        timberwolf.tell.get_data(source.source_id) is None
    ), "If there are no URLs available for an existing user, shouldn't have added them."

    assert teller.has_tell(
        "wildfire"
    ), "If there are no URLs available, we *will* now go ahead and create the User."

    assert dray.get_data(source.source_id) is None
    urls = quislet.get_data(source.source_id)
    assert len(urls) == 2
    assert (
        urls["Confluence"] == f"{CONFLUENCE_URL}/display/~quislet"
    ), "Once it adds the URL, it sticks around."
    assert (
        urls["Github"] == f"{GITHUB_URL}/quislet"
    ), "Once it adds the URL, it sticks around."


def get_profile(username):
    profile = TEST_CONFLUENCE_USER_DATA.get(username)

    if profile is None:
        raise RequestException("Empty Profile from test method")

    return profile


async def test_confluence_users(this_test_name):
    teller = create_test_teller()
    teller.create_tell("cosmicboy", TELLUS_INTERNAL, this_test_name)
    user_manager = UserManager(
        teller, ["saturngirl", "tellus", "tellussvc", "notauser"]
    )

    confluence = MagicMock(type=Confluence)
    confluence.get_mobile_parameters.side_effect = get_profile
    gsuite = MagicMock(function=retrieve_gsuite_user_directory)
    gsuite.return_value = {}
    source = UserInfo(user_manager, confluence, gsuite)

    await source.load_source()
    saturngirl = user_manager.get("saturngirl")
    confluence_profile = saturngirl.tell.get_data(source.CONFLUENCE_PROFILE_DATA)
    assert confluence_profile is not None
    assert confluence_profile["email"] == "saturn.girl@thelegion.org"
    assert confluence_profile["fullName"] == "Saturn Girl"
    assert confluence_profile["avatarUrl"] == "/some/url/for/saturngirl"
    assert saturngirl.full_name == "Saturn Girl"
    assert saturngirl.email == "saturn.girl@thelegion.org"
    assert (
        saturngirl.tell.get_datum(source.CONFLUENCE_PROFILE_DATA, "avatarUrl")
        == "/some/url/for/saturngirl"
    )
    assert (
        saturngirl.tell.get_datum(User.USER_INFO_DATA, "Avatar URL")
        == f"{CONFLUENCE_URL}/some/url/for/saturngirl"
    )

    # Some weird edge cases to explain what happens...
    assert user_manager.get_active_usernames() == [
        "notauser",
        "saturngirl",
        "tellussvc",
    ]
    assert user_manager.get("saturngirl") == saturngirl

    assert not user_manager.is_active_tellus_user(
        "tellus"
    ), "Tellus is never a valid username, so wouldn't have been created."
    assert (
        user_manager.get("notauser").tell.get_data(source.CONFLUENCE_PROFILE_DATA)
        is None
    ), "notauser is valid for Tellus, but not a user in Confluence (we hope)"
    assert (
        user_manager.get("tellussvc").tell.get_data(source.CONFLUENCE_PROFILE_DATA)
        is not None
    ), (
        "tellussvc is the Tellus service account - if listed as valid a user would be created & profile data retrieved."
        "HOWEVER - it should generally not be listed as valid, as users should be humans."
        "Note however that determining whether a user is valid for Tellus is distinct from the retrieval"
        "of the Profile data."
    )
    assert (
        teller.get("cosmicboy").get_data(source.CONFLUENCE_PROFILE_DATA) is None
    ), "Cosmic Boy is always a confluence user, and a Tell - but not a valid Tellus user, so his profile would not be retrieved."


def test_populate_gsuite_info():
    teller = create_test_teller()
    teller.create_tell("cosmicboy", TELLUS_INTERNAL, this_test_name)
    user_manager = UserManager(
        teller, ["saturngirl", "tellus", "tellussvc", "notauser"]
    )
    source = UserInfo(user_manager, None)
    saturngirl = user_manager.get_or_create_valid_user("saturngirl")

    last_update = assert_modified_since(saturngirl.tell, None)
    source.populate_gsuite_info(saturngirl, TEST_GSUITE_USER_DATA)
    assert (
        saturngirl.full_name is None
    ), "Updating from GSuite requires email population from a prior source - this will do nothing."
    last_update = assert_not_modified_since(saturngirl.tell, last_update)

    saturngirl.set_user_info(
        full_name="Saturn Girl", email="saturn.girl@thelegion.org"
    )  # Note that these do not match GSuite, intentionally (but it does update the Tell, so...)
    last_update = assert_modified_since(saturngirl.tell, last_update)
    # This should *not* update the Tell:
    source.populate_gsuite_info(saturngirl, TEST_GSUITE_USER_DATA)
    last_update = assert_not_modified_since(saturngirl.tell, last_update)
    assert saturngirl.tell.get_data(UserInfo.GSUITE_PROFILE_DATA) is None, (
        "This should not have generated an error, "
        "but also should not have updated the GSuite data since the email doesn't match."
    )
    assert saturngirl.get_user_info == {
        "Email": "saturn.girl@thelegion.org",
        "Full Name": "Saturn Girl",
    }

    saturngirl.set_user_info(
        full_name="Saturn Girl", email="saturngirl@thelegion.org"
    )  # Full Name still does not match GSuite, intentionally
    source.populate_gsuite_info(saturngirl, TEST_GSUITE_USER_DATA)
    # *Now* we are actually updating the Tell
    last_update = assert_modified_since(saturngirl.tell, last_update)
    assert saturngirl.tell.get_data(UserInfo.GSUITE_PROFILE_DATA) == {
        "Email": "saturngirl@thelegion.org",
        # Note that this indicates sort of an error condition, but low probability/impact so we're mostly ignoring it:
        "GSuite Primary Email": "saturn.girl@thelegion.org",
        "Full Name": "Imra Ardeen",
        "Phone": "888 8888",
    }
    assert saturngirl.tell.get_data(UserInfo.SOURCE_ID) == {
        "Email": "saturngirl@thelegion.org",
        "Full Name": "Imra Ardeen",
        "Phone": "888 8888",
    }
    assert (
        saturngirl.full_name == "Imra Ardeen"
    ), "GSuite Data, if available, will overwrite anything else as primary."

    # Edge cases
    # This one should be basically impossible - but will technically modify info because of email
    source.populate_gsuite_info(saturngirl, {"saturngirl@thelegion.org": {}})
    last_update = assert_modified_since(saturngirl.tell, last_update)
    assert saturngirl.get_user_info == {
        "Email": "saturngirl@thelegion.org",
        "Full Name": "Imra Ardeen",
        "Phone": "888 8888",
    }, " Should be unchanged"

    source.populate_gsuite_info(
        saturngirl,
        {
            "saturngirl@thelegion.org": {
                "name": {"fullName": "Psi-Girl"},
                "primaryEmail": "foo@bar.baz",
            }
        },
    )
    last_update = assert_modified_since(saturngirl.tell, last_update)
    assert saturngirl.get_user_info == {
        "Email": "saturngirl@thelegion.org",
        "Full Name": "Psi-Girl",
        "Phone": "888 8888",
    }, "Should have successfully changed Full Name but nothing else"


async def test_gsuite_users(this_test_name):
    teller = create_test_teller()
    teller.create_tell("cosmicboy", TELLUS_INTERNAL, this_test_name)
    user_manager = UserManager(
        teller, ["saturngirl", "cosmicboy", "tellussvc", "notauser"]
    )

    confluence = MagicMock(type=Confluence)
    confluence.get_mobile_parameters.side_effect = get_profile
    gsuite = MagicMock(function=retrieve_gsuite_user_directory)
    gsuite.return_value = TEST_GSUITE_USER_DATA
    source = UserInfo(user_manager, confluence, gsuite)

    await source.load_source()
    assert (
        user_manager.get("cosmicboy").full_name == "Rokk Krinn"
    ), "Based on the data, Cosmic Boy should have been updated..."
    assert (
        user_manager.get("saturngirl").full_name == "Saturn Girl"
    ), "...but Saturn Girl should not because of mismatched emails"


async def test_removed_users():
    teller = create_test_teller()
    users = UserManager(teller, ["saturngirl", "cosmicboy", "sensor"])

    confluence = MagicMock(type=Confluence)
    confluence.get_mobile_parameters.side_effect = get_profile
    source = UserInfo(users, confluence)

    await source.load_source()
    sensor = users.get("sensor")

    with patch(
        "tellus.tellus_sources.user_info_source.retrieve_valid_confluence_usernames",
        new=MagicMock(),
    ) as confluence_usernames:
        confluence_usernames.return_value = ["cosmicboy", "saturngirl"]
        await source.load_source()
        assert users.get_active_usernames() == ["cosmicboy", "saturngirl"]
        assert not sensor.is_active()
        assert users.get("saturngirl").is_active()
