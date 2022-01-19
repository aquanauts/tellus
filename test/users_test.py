# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests
from unittest.mock import MagicMock

import pytest
import json

from aiohttp import ClientSession

import tellus.configuration
import tellus.users
import tellus.wiring
from tellus.configuration import (
    NEVER_VALID_USERNAMES,
    TELLUS_INTERNAL,
    TELLUS_GO,
    TELLUS_USER,
)
from tellus.tell import Tell
from tellus.tellus_sources.socializer import Socializer
from tellus.users import (
    User,
    UserManager,
    UserHandler,
    InvalidTellusUserException,
    NoExistingTellusUserException,
    SESSION_AUTH_USER_EMAIL,
)
from tellus.wiring import SESSION_TELLUS_USER
from tellus.wiring import R_USER
from test.tellus_test_utils import this_test_name, mock_session
from test.tells_test import create_test_teller
from test.tellus_test import create_and_load_test_webapp, test_fs  # must import test_fs


def test_user_basics():
    tell = Tell("tellus", TELLUS_INTERNAL, created_by="test_user_basics")
    try:
        User(tell)
        pytest.fail(
            "Trying to create a User from a non-user Tell should throw an exception."
        )
    except InvalidTellusUserException:
        pass
    tell = Tell(
        "quislet",
        TELLUS_USER,
        created_by="test_user_basics",
        description="Quislet Q Quislet",
    )
    user = User(tell)
    assert user.tell == tell
    assert user.username == tell.alias
    assert user.full_name is None
    user.set_user_info(
        full_name="Quislet Q Quislet", email="quislet.quislet@thelegion.org"
    )
    assert user.full_name == "Quislet Q Quislet"
    assert user.email == "quislet.quislet@thelegion.org"

    # Checking these even though it exposes more internal implementation than I'd like,
    # as changing this can have an impact on the UI.
    assert user.tell.get_datum(user.USER_INFO_DATA, "Full Name") == "Quislet Q Quislet"
    assert (
        user.tell.get_datum(user.USER_INFO_DATA, "Email")
        == "quislet.quislet@thelegion.org"
    )

    json_dict = json.loads(user.to_simple_json())
    assert json_dict["fullName"] == user.full_name, "User JSON should add in full name"
    assert json_dict["email"] == user.email, "User JSON should add in email"

    user.set_user_info_property("Location", "Earth")
    assert user.get_user_info == {
        "Email": "quislet.quislet@thelegion.org",
        "Full Name": "Quislet Q Quislet",
        "Location": "Earth",
    }
    user.set_user_info_property("Location", None)
    assert user.get_user_info == {
        "Email": "quislet.quislet@thelegion.org",
        "Full Name": "Quislet Q Quislet",
        "Location": "Earth",
    }
    user.set_user_info_property("Location", None, True)
    assert user.get_user_info == {
        "Email": "quislet.quislet@thelegion.org",
        "Full Name": "Quislet Q Quislet",
    }


def test_promote_info(this_test_name):
    user = User(Tell("quislet", TELLUS_USER, created_by=this_test_name))
    user.set_user_info(
        full_name="Quislet Q Quislet", email="quislet.quislet@thelegion.org"
    )
    user.tell.update_data_from_source(
        "Source 1",
        {
            User.FULL_NAME: "Bob Quislet, Jr.",
            User.EMAIL: "quislet@thelegion.org",
            "Not A Property": "Something",
        },
    )
    user.tell.update_data_from_source(
        "Source 2",
        {
            User.FULL_NAME: "Q",
            User.EMAIL: "q@thelegion.org",
            User.PHONE: "867-5309",
            User.AVATAR_URL: "https://www.comicbookreligion.com/img/q/u/Quislet.jpg",
            "Also Not a Property": "Something Else",
        },
    )
    user.tell.update_data_from_source("Empty Source", {})

    assert user.get_user_info == {
        "Email": "quislet.quislet@thelegion.org",
        "Full Name": "Quislet Q Quislet",
    }

    user.promote_info("Empty Source")
    assert user.get_user_info == {
        "Email": "quislet.quislet@thelegion.org",
        "Full Name": "Quislet Q Quislet",
    }

    user.promote_info("Source 1")
    assert user.get_user_info == {
        "Email": "quislet@thelegion.org",
        "Full Name": "Bob Quislet, Jr.",
    }

    user.promote_info("Source 2")
    assert user.get_user_info == {
        User.FULL_NAME: "Q",
        User.EMAIL: "q@thelegion.org",
        User.PHONE: "867-5309",
        User.AVATAR_URL: "https://www.comicbookreligion.com/img/q/u/Quislet.jpg",
    }

    user.promote_info("Empty Source")
    assert user.get_user_info == {
        User.FULL_NAME: "Q",
        User.EMAIL: "q@thelegion.org",
        User.PHONE: "867-5309",
        User.AVATAR_URL: "https://www.comicbookreligion.com/img/q/u/Quislet.jpg",
    }

    try:
        user.promote_info("Not A Source")
        pytest.fail("Should have thrown an exception if trying to promote a non-Source")
    except TypeError:
        pass
    assert user.get_user_info == {
        User.FULL_NAME: "Q",
        User.EMAIL: "q@thelegion.org",
        User.PHONE: "867-5309",
        User.AVATAR_URL: "https://www.comicbookreligion.com/img/q/u/Quislet.jpg",
    }


def activate_quislet(user_manager):
    user_manager.get_or_create_valid_user("quislet")
    quislet = user_manager.get("quislet")
    quislet.set_user_info(full_name="Quislet Q. Quislet", email="quislet@thelegion.org")
    quislet.set_user_info_property(User.AVATAR_URL, "something")
    quislet.set_user_info_property(User.PHONE, "867-5309")
    user_manager.refresh()
    return quislet


def test_user_manager_update_valid_usernames():
    teller = create_test_teller()
    user_manager = UserManager(
        teller, valid_usernames=["quislet"] + NEVER_VALID_USERNAMES
    )

    assert user_manager.is_valid_username("quislet")
    assert not user_manager.is_valid_username("NEVER-A-VALID-USER")
    assert not user_manager.is_valid_username("tellus")

    quislet = activate_quislet(user_manager)

    for name in NEVER_VALID_USERNAMES:
        assert not user_manager.is_valid_username(
            name
        ), f"{name} is in NEVER_VALID_USERNAMES and should never be valid."

    usernames = user_manager.update_valid_usernames(
        ["quislet", "wildfire", "matter-eater-lad"]
    )
    assert user_manager.is_valid_username("quislet")
    assert user_manager.is_valid_username("wildfire")
    assert user_manager.is_valid_username("matter-eater-lad")

    usernames = user_manager.update_valid_usernames([])
    assert list(usernames) == [
        "matter-eater-lad",
        "quislet",
        "wildfire",
    ], "Attempting to remove all valid usernames is assumed to be an error, and ignored."

    user_manager.update_valid_usernames(["wildfire", "blok"])
    assert user_manager.is_valid_username("wildfire")
    assert user_manager.is_valid_username("blok")

    assert not user_manager.is_valid_username("matter-eater-lad")
    assert not user_manager.is_valid_username(
        "quislet"
    ), "Removing a user from the list of valid usernames, does."
    assert (
        not quislet.is_active()
    ), "Removing a user from the list of valid username deactivates them."

    # Edge case where we had a user previously, but in between Tellus restarts their username was removed
    wildfire = user_manager.get_or_create_valid_user("wildfire")
    user_manager._valid_usernames.remove("wildfire")
    assert wildfire.is_active()
    user_manager.update_valid_usernames(["blok"])
    assert (
        user_manager.get("wildfire") == wildfire
    ), "Should still be able to retrieve the User even if inactive."
    assert not wildfire.is_active()

    # An edge case (but a common one):  we loaded a bunch of users from persistence, that happens to be the same
    # as the set of valid usernames (which originally would result in the valid usernames not being updated).
    # This is a simpler (if cheat-y) way to simulate that.
    valid_usernames = ["blok", "dawnstar"]
    user_manager.update_valid_usernames(valid_usernames)
    user_manager.get_or_create_valid_user("blok")
    user_manager.get_or_create_valid_user("dawnstar")
    user_manager._valid_usernames.clear()
    assert user_manager.get_active_usernames() == ["blok", "dawnstar"]
    assert list(user_manager.get_valid_usernames()) == []
    user_manager.update_valid_usernames(valid_usernames)
    assert list(user_manager.get_valid_usernames()) == valid_usernames


def test_user_manager_deactivate_user():
    teller = create_test_teller()
    user_manager = UserManager(teller)
    user_manager.update_valid_usernames(["quislet", "wildfire", "matter-eater-lad"])
    quislet = activate_quislet(user_manager)

    # Testing some ancillary stuff here as the most logical place...
    socializer = Socializer(user_manager)

    # Some sanity checks
    assert quislet in user_manager.get_active_users()
    assert "quislet" in user_manager.get_active_usernames()
    assert user_manager.get_by_email("quislet@thelegion.org") == quislet
    assert "quislet" in socializer.determine_coffee_bot_users()

    assert (
        user_manager.deactivate_user("wildfire") is None
    ), "Deactivating a nonexistent user will not throw an exception, but will return None."

    # Main event
    assert (
        user_manager.deactivate_user("quislet") == quislet
    ), "Deactivating a user returns the deactivated User"
    assert user_manager.is_valid_username(
        "quislet"
    ), "Deactivating a User does *not* by itself affect valid usernames."
    assert (
        user_manager.get("quislet") == quislet
    ), "Getting an invalid User by username still returns a User."
    assert not user_manager.is_active_tellus_user(
        "quislet"
    ), "Deactivating a User takes the user out of the list of active users."
    assert quislet not in user_manager.get_active_users()
    assert "quislet" not in user_manager.get_active_usernames()
    assert (
        user_manager.get_by_email("quislet@thelegion.org") == quislet
    ), "We can still look up the user by email."

    # Side effects of deactivating a user
    assert "quislet" not in socializer.determine_coffee_bot_users()

    # What happens after a refresh?
    user_manager.refresh()
    assert user_manager.is_valid_username(
        "quislet"
    ), "Refreshing the UserManager does not affect valid usernames even with Invalid users."
    assert (
        user_manager.get("quislet") == quislet
    ), "Getting an invalid User by username still returns a User after a UserManager refresh."
    assert not user_manager.is_active_tellus_user(
        "quislet"
    ), "Even though it is a valid username, the user should remain inactive after a UserManager refresh."
    assert quislet not in user_manager.get_active_users()
    assert "quislet" not in user_manager.get_active_usernames()
    try:
        user_manager.get_by_email("quislet@thelegion.org")
        pytest.fail(
            "After a UserManager refresh, we can no longer look up the user by email."
        )
    except NoExistingTellusUserException:
        pass


def test_get_users_and_usernames():
    teller = create_test_teller()
    user_manager = UserManager(
        teller, valid_usernames=["quislet", "wildfire", "matter-eater-lad"]
    )

    teller.create_tell("legion-headquarters", TELLUS_INTERNAL, "test_get_users")
    teller.create_tell("saturn-girl", TELLUS_GO, "test_get_users")

    assert (
        len(user_manager.get_active_users()) == 0
    ), "Getting users should ignore any other existing Tells"
    user_manager.get_or_create_valid_user("quislet")
    user_manager.get_or_create_valid_user("wildfire")
    users = user_manager.get_active_users()
    assert len(users) == 2
    for user in users:
        assert user.tell == teller.get(user.username)

    usernames = user_manager.get_active_usernames()
    assert len(usernames) == len(users)
    for username in usernames:
        assert teller.get(username) == user_manager.get(username).tell


def test_get_user():
    teller = create_test_teller()
    users = UserManager(
        teller, valid_usernames=["quislet", "plantlad", "rjbrande", "sensor"]
    )
    rj = teller.create_tell("rjbrande", TELLUS_GO, "test_get_user")
    quislet = users.get_or_create_valid_user("quislet")
    sensor = users.get_or_create_valid_user("sensor")
    users.update_valid_usernames(
        ["quislet", "plantlad", "rjbrande"]
    )  # Sensor is now Invalid

    assert quislet == users.get(
        "quislet"
    ), "Users are wrappers, and and are equivalent..."
    assert (
        quislet.tell == users.get("quislet").tell
    ), "...as long as their internal Tell is equivalent."

    try:
        users.get("NONE-MORE-INVALID")
        pytest.fail(
            "Attempting to get an invalid username with no Tell should throw an NoExistingTellusUserException."
        )
    except NoExistingTellusUserException:
        pass

    assert not sensor.is_active()
    assert (
        users.get("sensor") == sensor
    ), "Directly etting an inactive User will still return the User"

    try:
        users.get("rjbrande")
        pytest.fail(
            "Attempting to get a User but getting a different kind of Tell "
            "should throw a NoExistingTellusUserException."
        )
    except NoExistingTellusUserException as exception:
        assert (
            rj == exception.tell
        ), "The Exception will have the non-user Tell attached."

    rj.add_category(TELLUS_USER)
    assert (
        rj == users.get("rjbrande").tell
    ), "Now this works, as RJ has become a Tellus User."

    try:
        users.get("plantlad")
        pytest.fail(
            "Attempting to get a valid user that has no Tell should throw a TheresNoTellingException."
        )
    except NoExistingTellusUserException:
        pass


def test_get_user_by_email():
    teller = create_test_teller()
    users = UserManager(teller, valid_usernames=["quislet", "plantlad", "rjbrande"])
    rj = teller.create_tell("rjbrande", TELLUS_GO, "test_get_user")
    quislet = users.get_or_create_valid_user("quislet")
    quislet.set_user_info(full_name="Quislet Q. Quislet", email="quislet@thelegion.org")
    users.refresh()

    assert quislet == users.get_by_email("quislet@thelegion.org")


def test_get_or_create_user():
    teller = create_test_teller()
    users = UserManager(teller, valid_usernames=["quislet", "rjbrande"])
    rj = teller.create_tell("rjbrande", TELLUS_GO, "test_get_user")

    quislet = users.get_or_create_valid_user("quislet")
    assert quislet.tell == teller.get(
        "quislet"
    ), "get_or_create_user with a valid User should create the user."

    try:
        users.get_or_create_valid_user("NONE-MORE-INVALID")
        pytest.fail(
            "get_or_create_user with an invalid user should throw an InvalidTellusUserException."
        )
    except InvalidTellusUserException:
        pass

    rj_user = users.get_or_create_valid_user("rjbrande")
    assert (
        rj_user.tell == rj
    ), "get_or_create_user with an alias for a non-user Tell should turn that Tell into a user."
    assert teller.get("rjbrande").in_category(TELLUS_USER)


def test_tellus_session():
    user_manager = UserManager(create_test_teller(), ["quislet"])
    quislet = user_manager.get_or_create_valid_user("quislet")
    quislet.set_user_info(full_name="Quislet Q Quislet", email="quislet@thelegion.org")
    user_manager.refresh()

    session = tellus.users.TellusSession(
        {},
        {tellus.users.SESSION_AUTH_USER_EMAIL: "quislet@thelegion.org"},
        user_manager,
    )

    assert session.username == "quislet"
    assert session.username == session.tellus_internal_username

    session = tellus.users.TellusSession({}, {}, user_manager)

    assert session.username is None
    assert session.tellus_internal_username == tellus.configuration.TELLUS_APP_USERNAME

    session = tellus.users.TellusSession(
        {},
        {tellus.users.SESSION_AUTH_USER_EMAIL: "quislet@thelegion.org"},
        user_manager,
    )
    assert session.username == "quislet"
    assert session.user.email == "quislet@thelegion.org"


async def test_retrieve_user(test_fs, aiohttp_client):
    teller = create_test_teller()
    users = UserManager(teller, ["quislet"])
    app = create_and_load_test_webapp(teller, user_manager=users)
    quislet = users.get_or_create_valid_user("quislet")

    client = await aiohttp_client(app)

    response = await client.get(f"/{R_USER}/quislet")
    assert response.status == 200
    text = await response.text()
    assert text == quislet.to_simple_json()

    response = await client.get(f"/{R_USER}/nobody")
    assert response.status == 404, "Will 404 if cannot retrieve a user for a username."
    text = await response.text()
    assert (
        text == "Error retrieving User 'nobody': No User currently exists for 'nobody'."
    )

    response = await client.get(f"/{R_USER}/tellus")
    assert response.status == 404, "Tellus is not (presently) an actual user."

    teller.create_tell("notauser", TELLUS_INTERNAL, "test")
    response = await client.get(f"/{R_USER}/notauser")
    assert (
        response.status == 404
    ), "If there is a Tell that is not a User, still will 404."


async def test_user_session_through_whoami(test_fs, aiohttp_client):
    teller = create_test_teller()
    users = UserManager(teller, ["quislet", "wildfire"])
    app = create_and_load_test_webapp(teller, user_manager=users)

    client = await aiohttp_client(app)

    response = await client.get(UserHandler.ROUTE_WHOAMI)
    assert response.status == 200
    text = await response.text()
    assert text == "", "Whoami returns a blank if there is no specified user"

    assert not teller.has_tell("quislet")
    response = await client.get(
        UserHandler.ROUTE_WHOAMI,
        headers={SESSION_AUTH_USER_EMAIL: "quislet@thelegion.org"},
    )
    assert response.status == 200
    text = await response.text()
    assert (
        text == ""
    ), "Whoami still is valid and returns a blank if there is no Tellus user for a passed email address."

    quislet = users.get_or_create_valid_user("quislet")
    response = await client.get(
        UserHandler.ROUTE_WHOAMI,
        headers={SESSION_AUTH_USER_EMAIL: "quislet@tellus.com"},
    )
    assert response.status == 200
    text = await response.text()
    assert text == "", (
        "Whoami still is valid and returns a blank if there is "
        "no Tellus user for a passed email address (even if there is a user)."
    )
    assert quislet.last_login is None, "Quislet has not yet logged in successfully."

    quislet.set_user_info(full_name="Quislet Q Quislet", email="quislet@thelegion.org")
    wildfire = users.get_or_create_valid_user("wildfire")
    wildfire.set_user_info(full_name="Drake Burroughs", email="wildfire@thelegion.org")
    users.refresh()

    response = await client.get(
        UserHandler.ROUTE_WHOAMI, headers={SESSION_AUTH_USER_EMAIL: quislet.email},
    )
    assert response.status == 200
    text = await response.text()
    assert text == "quislet", "Whoami should return the username for a valid user"
    assert quislet.last_login is not None, "Should have recorded the log in."

    response = await client.get(
        UserHandler.ROUTE_VALID_USERS, headers={SESSION_AUTH_USER_EMAIL: quislet.email}
    )
    assert response.status == 200
    text = await response.text()
    assert text == "Valid Tellus users:\nquislet <-- current user\nwildfire"

    response = await client.get(UserHandler.ROUTE_VALID_USERS)
    assert response.status == 200
    text = await response.text()
    assert (
        text == "Valid Tellus users:\nquislet\nwildfire"
    ), "Without the email header, Tellus doesn't assume who the current user is."

    response = await client.get(
        UserHandler.ROUTE_WHOAMI,
        headers={SESSION_AUTH_USER_EMAIL: quislet.email},
        data={SESSION_TELLUS_USER: wildfire.email},
    )
    assert response.status == 200
    text = await response.text()
    assert (
        text == "quislet"
    ), "Whoami should return the username for the auth user, even if a session user is specified"

    response = await client.get(UserHandler.ROUTE_WHOAMI)
    assert response.status == 200
    text = await response.text()
    assert (
        text == ""
    ), "Whoami should return a blank if the auth user (somehow) goes away..."

    await client.get(f"{UserHandler.ROUTE_DEBUG_LOGIN}/{wildfire.email}")
    response = await client.get(UserHandler.ROUTE_WHOAMI)
    assert response.status == 200
    text = await response.text()
    assert (
        text == "wildfire"
    ), "Whoami should return the debug user if there is no authed user (only in dev)"


async def test_all_users(test_fs, aiohttp_client):
    teller = create_test_teller()
    users = UserManager(teller, ["quislet", "saturngirl", "cosmicboy", "lightninglad"])
    app = create_and_load_test_webapp(teller, user_manager=users)

    quislet = users.get_or_create_valid_user("quislet")
    saturngirl = users.get_or_create_valid_user("saturngirl")

    client = await aiohttp_client(app)

    response = await client.get(f"/{R_USER}/")
    assert response.status == 200
    text = await response.text()
    json_dict = json.loads(text)
    assert len(json_dict) == 2, "Should only return Users for actually created Users."

    assert json_dict["quislet"] == quislet.to_simple_json()
    assert json_dict["saturngirl"] == saturngirl.to_simple_json()
