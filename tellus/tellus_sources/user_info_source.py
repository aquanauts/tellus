import logging

from requests import RequestException

from tellus.configuration import GITHUB_URL, CONFLUENCE_URL
from tellus.tellus_sources.confluence_helper import (
    get_confluence,
    retrieve_valid_confluence_usernames,
)
from tellus.google_api_utils import retrieve_gsuite_user_directory
from tellus.sources import Source
from tellus.tellus_utils import is_url_available
from tellus.users import InvalidTellusUserException, User

USERNAME = "|USERNAME|"


class UserInfo(Source):
    SOURCE_ID = User.USER_INFO_DATA
    CONFLUENCE_PROFILE_DATA = "confluence-profile"
    GSUITE_PROFILE_DATA = "gsuite-profile"
    GSUITE_PRIMARY_PHONE = "mobile"

    """
    A source that constructs a representation of a particular Tellus Users's footprint.
    Goal is to be easily extensible to add user pages from various systems.
    """

    _user_urls = [
        ("Confluence", f"{CONFLUENCE_URL}/display/~{USERNAME}"),
        ("Github", f"{GITHUB_URL}/{USERNAME}"),
    ]

    _data_urls = {
        "confluence": f"{CONFLUENCE_URL}/rest/mobile/1.0/profile/{USERNAME}",  # This one is required to get email
    }

    def __init__(self, user_manager, confluence=None, gsuite_directory_function=None):
        """
        :param user_manager:  The User Manager for this Source to get/add user data.
        :param confluence: Mostly to allow for easy mocking - if None, will get the real Confluence wrapper
        :param gsuite_directory_function: Mostly to allow for easy mocking - if None, will use the real method
        """
        super().__init__(
            user_manager.teller,
            source_id=UserInfo.SOURCE_ID,
            description="Connects a user Tell with various information about them from around the org.",
            datum_display_name="User Info",
        )
        self._user_manager = user_manager
        if confluence:
            self._confluence = confluence
        else:
            self._confluence = get_confluence()

        if gsuite_directory_function:
            self._gsuite_directory_function = gsuite_directory_function
        else:
            self._gsuite_directory_function = retrieve_gsuite_user_directory

    @staticmethod
    def _confluence_url(url_path):
        return f"{CONFLUENCE_URL}{url_path}"

    async def _update_available_user_urls(self, user):
        available_urls = []

        for system, url in UserInfo._user_urls:
            user_url = url.replace(USERNAME, user.username)
            if await is_url_available(user_url):
                available_urls.append((system, user_url))
            else:
                logging.debug("%s not available", user_url)

        if len(available_urls) > 0:
            for system, url in available_urls:
                self.update_from_source(user.tell, system, url)
        else:
            if self._user_manager.is_active_tellus_user(user.username):
                logging.warning(
                    "No active URLs found for existing Tellus user '%s', possible this User is inactive.",
                    user.username,
                )

        return available_urls

    def _populate_confluence_info(self, user):
        try:
            profile = self._confluence.get_mobile_parameters(
                user.username
            )  # ¯\_(ツ)_/¯ as far as I can determine, this is the only way to get email address
        except RequestException as e:
            logging.warning("Error loading User Info from Confluence:  %s", e)
            return

        user.tell.update_data_from_source(UserInfo.CONFLUENCE_PROFILE_DATA, profile)
        try:
            user.set_user_info(full_name=profile["fullName"], email=profile["email"])
        except KeyError:
            logging.warning(
                "Profile information did not contain either Full Name or Email: %s",
                profile,
            )
        if profile.get("avatarUrl") is not None:
            user.set_user_info_property(
                User.AVATAR_URL, f"{CONFLUENCE_URL}{profile.get('avatarUrl')}"
            )
        user.set_user_info_property(User.PHONE, profile.get("phone"))

    def populate_gsuite_info(self, user, users_data):
        if user.email is None:
            logging.warning(
                "User '%s' does not have an associated email prior to GSuite directory lookup. "
                "This should generally be impossible, and may indicate a Confluence issue. "
                "Please verify Confluence data for this user (or contact Help).",
                user.username,
            )
            return

        gsuite_user = users_data.get(user.email)
        if gsuite_user is None:
            logging.warning(
                "User '%s' does not have a corresponding GSuite user with email address '%s'. "
                "This indicates a mismatch between Confluence and GSuite information for this user. "
                "Please verify data for this user in those sources (or contact Help).",
                user.username,
                user.email,
            )
            return

        try:
            # Note:  because we are using email as the key, we use the existing email here.
            user.tell.update_datum_from_source(
                UserInfo.GSUITE_PROFILE_DATA, User.EMAIL, user.email,
            )
            if gsuite_user.get("primaryEmail") != user.email:
                # This should theoretically be impossible, but being overly cautious
                user.tell.update_datum_from_source(
                    UserInfo.GSUITE_PROFILE_DATA,
                    "GSuite Primary Email",
                    gsuite_user.get("primaryEmail"),
                )

            if gsuite_user.get("name"):
                user.tell.update_datum_from_source(
                    UserInfo.GSUITE_PROFILE_DATA,
                    User.FULL_NAME,
                    gsuite_user.get("name").get("fullName"),
                )

            for phone in gsuite_user.get("phones", {}):
                if phone.get("type") == UserInfo.GSUITE_PRIMARY_PHONE:
                    user.tell.update_datum_from_source(
                        UserInfo.GSUITE_PROFILE_DATA, User.PHONE, phone.get("value")
                    )

            user.promote_info(UserInfo.GSUITE_PROFILE_DATA)
        except (KeyError, TypeError, AttributeError) as e:
            logging.warning(
                "The GSuite data for User '%s' was at least partially malformed, so will not override User Info:  %s",
                user.username,
                repr(e),
            )

    async def load_source(self):
        usernames = self._user_manager.update_valid_usernames(
            retrieve_valid_confluence_usernames(self._confluence)
        )

        gsuite_users = self._gsuite_directory_function()
        logging.info("Retrieved %s GSuite Users from the directory.", len(gsuite_users))

        for username in usernames:
            try:
                user = self._user_manager.get_or_create_valid_user(username)
                await self._update_available_user_urls(user)
                self._populate_confluence_info(user)
                self.populate_gsuite_info(user, gsuite_users)
            except InvalidTellusUserException as exception:
                logging.warning(
                    "Attempted to get/create user for '%s', but received exception: %s",
                    username,
                    str(exception),
                )

        self._user_manager.refresh()
        self._user_manager.persist()
