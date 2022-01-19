import json
import logging

from aiohttp import web
from aiohttp_session import get_session
from sortedcontainers import SortedSet

from tellus.configuration import (
    NEVER_VALID_USERNAMES,
    TELLUS_APP_USERNAME,
    TELLUS_USER,
    TELLUS_INACTIVE_USER,
)
from tellus.tell import Tell
from tellus.tells import TheresNoTellingException
from tellus.tellus_sources.socializer import Socializer, CoffeeBot
from tellus.tellus_utils import now_string, TellusException
from tellus.wiring import (
    R_MGMT,
    R_USER,
    SESSION_TELLUS_USER,
)

SESSION_AUTH_USER_EMAIL = "OIDC_CLAIM_email"
SESSION_TELLUS_DEBUG_EMAIL = (
    "tellus_debug_email"  # user for debugging without the proxy - only works in dev
)


class TellusSession(object):
    @staticmethod
    async def construct(request, user_manager):
        """
        Construct (asynchronously) a session from a request (to take Async out of the TellusSession)
        :param request: the request passed to the handler
        :param user_manager: the user manager to use to look up user info
        :param login_username: (optional) a login username posted to the app.
        :return:
        """
        session = await get_session(request)
        return TellusSession(session, request.headers, user_manager)

    def __init__(self, session, headers, user_manager):
        self._session = session
        self._user = None
        self._update_session_user(headers, user_manager)

    @property
    def username(self):
        if self._user is None:
            return None
        return self.user.username

    @property
    def user(self):
        return self._user

    @property
    def tellus_internal_username(self):
        """
        Special case where Tellus will use its own "username" for certain purposes, if no user is logged in.
        """
        if self._user is None:
            return TELLUS_APP_USERNAME
        return self.username

    def _update_session_user(self, headers, user_manager):
        """
        :param headers: the current set of headers for this session
        :param user_manager: the user manager to look up user info
        """
        session_email = headers.get(SESSION_AUTH_USER_EMAIL)
        session_username = self._session.get(SESSION_TELLUS_USER)

        if session_email is None:
            debug_email = self._session.get(SESSION_TELLUS_DEBUG_EMAIL)
            if debug_email is None:
                self.invalidate()
                # If you get this warning during development, set a debug login email with UserHandler.ROUTE_DEBUG_LOGIN
                logging.warning(
                    "Session email is not specified, and no debug email specified.  "
                    "(In production, this shouldn't be possible if the proxy is working correctly.)\n"
                    "[debug email: %s, session email: %s, session username: %s]\nHeaders: %s",
                    debug_email,
                    session_email,
                    session_username,
                    headers,
                )
                return

            logging.debug(
                "Using the debugging email of '%s' to log in - this should only be possible in dev.",
                debug_email,
            )
            session_email = debug_email

        try:
            self._user = user_manager.get_by_email(session_email)
        except (NoExistingTellusUserException, InvalidTellusUserException) as e:
            logging.warning(
                "An attempt was made to login user for email '%s' but that is not a valid Tellus user:  %s",
                session_email,
                repr(e),
            )
            self.invalidate()
            return

        if session_username is not None and self._user.username != session_username:
            logging.warning(
                "User '%s' was logged in via Auth, but the session thinks they are '%s'.  "
                "Session user will be updated to '%s'.",
                self._user.username,
                session_username,
                self._user.username,
            )
        user_manager.login_user(self._user.username)
        # user_manager.persist()  # In the current paradigm, this leads to too many persistence calls...
        self._session[SESSION_TELLUS_USER] = self._user.username

    def invalidate(self):
        try:
            self._session.invalidate()
        except AttributeError:
            logging.error(
                "The object we are treating as a session isn't one.  This should only be true in testing: %s",
                self._session,
            )

    @staticmethod
    async def whoami(request, user_manager):
        return (await TellusSession.construct(request, user_manager)).username


class InvalidTellusUserException(TellusException):
    def __init__(self, message):
        TellusException.__init__(self, message)


class NoExistingTellusUserException(TellusException):
    def __init__(self, message, tell=None):
        TellusException.__init__(self, message)
        self.tell = tell


def is_user(tell):
    return tell.in_category(TELLUS_USER)


class User:
    """
    A wrapper around a Tell that represents a user with more semantically clear names.
    In anticipation of this eventually becoming a more first class Tellus object.
    """

    LAST_LOGIN = "last_login"

    USER_INFO_DATA = "user-info"
    FULL_NAME = "Full Name"
    EMAIL = "Email"
    PHONE = "Phone"
    AVATAR_URL = "Avatar URL"
    USER_INFO_PROPERTIES = [FULL_NAME, EMAIL, PHONE, AVATAR_URL]

    _JSON_FULL_NAME = "fullName"
    _JSON_EMAIL = "email"

    def __init__(self, user_tell: Tell):
        if not User.is_user_tell(user_tell):
            raise InvalidTellusUserException(
                f"Attempted to create a user with a non-User Tell:  {user_tell.to_simple_json()}"
            )

        self._tell = user_tell

    def __eq__(self, other):
        """Users are a wrapper around a Tell, so they are equivalent if their internal Tell is equivalent."""
        if isinstance(other, User):
            return self._tell == other._tell
        return False

    @staticmethod
    def is_user_tell(tell):
        return tell.in_category(TELLUS_USER) or tell.in_category(TELLUS_INACTIVE_USER)

    @property
    def username(self):
        return self._tell.alias

    @property
    def full_name(self):
        return self._tell.get_datum(self.USER_INFO_DATA, self.FULL_NAME)

    @property
    def email(self):
        return self._tell.get_datum(self.USER_INFO_DATA, self.EMAIL)

    def set_user_info(self, *, full_name, email):
        """
        Set the primary user information in addition to the alias (which is their short username).
        """
        self._tell.update_datum_from_source(
            self.USER_INFO_DATA, self.FULL_NAME, full_name
        )
        self._tell.update_datum_from_source(self.USER_INFO_DATA, self.EMAIL, email)

    def set_user_info_property(self, data_key, value, remove_if_none=False):
        """
        Set a User Info property value.

        :param data_key: the property key
        :param value: the property value
        :param remove_if_none: if True, will remove the property if the value is None.  Otherwise, will ignore it.
        """
        if value:
            self._tell.update_datum_from_source(self.USER_INFO_DATA, data_key, value)
        elif remove_if_none:
            self._tell.remove_datum(self.USER_INFO_DATA, data_key)

    def promote_info(self, data_key):
        """
        "Promotes" the User Info from the specified data source to be primary.  This will overwrite whatever the current
        user info is from the specified Source.  It is strictly additive - it will not remove any properties
        not in the specified source.
        """
        data = self._tell.get_data(data_key)
        for user_property in User.USER_INFO_PROPERTIES:
            if user_property in data:
                self.set_user_info_property(user_property, data[user_property])

    def get_user_info_property(self, data_key):
        return self._tell.get_datum(self.USER_INFO_DATA, data_key)

    @property
    def get_user_info(self):
        return self._tell.get_data(self.USER_INFO_DATA)

    @property
    def tell(self):
        return self._tell

    @property
    def last_login(self):
        return self._tell.get_datum(User.USER_INFO_DATA, self.LAST_LOGIN)

    @staticmethod
    def enhanced_simple_json(tell):
        """
        :param tell: The tell (assumed to be a User) to return json for, enhanced with user info properties
        :return: the userified to_simple_json
        :raises: an InvalidTellusUserException if the Tell passed is not a user
        """
        return User(tell).to_simple_json()

    def to_simple_json(self):
        return self._tell.to_simple_json(
            {User._JSON_EMAIL: self.email, User._JSON_FULL_NAME: self.full_name,}
        )

    def record_login(self):
        """
        Sets the current time as the last time the User logged into Tellus
        """
        self._tell.update_datum_from_source(
            User.USER_INFO_DATA, self.LAST_LOGIN, now_string()
        )

    def is_active(self):
        return not self._tell.in_category(TELLUS_INACTIVE_USER)


class UserManager:
    """
    Because while Userer would be funny to to along with Teller and Sourcer, it's probably not a great name for this.
    """

    def __init__(self, teller, valid_usernames=None):
        self._teller = teller
        self._valid_usernames = SortedSet()
        if valid_usernames:
            self._add_valid_usernames(valid_usernames)
        self._users_by_email = {}
        self._users_by_username = {}

    @property
    def teller(self):
        return self._teller

    def persist(self):
        self._teller.persist()

    def _add_valid_usernames(self, usernames):
        for name in usernames:
            if name not in NEVER_VALID_USERNAMES:
                self._valid_usernames.add(name)
            else:
                logging.warning(
                    "An attempt was made to add '%s' as a valid username, "
                    "but it is in Tellus' list of Never Valid Usernames (%s).",
                    name,
                    NEVER_VALID_USERNAMES,
                )

    def update_valid_usernames(self, current_valid_usernames):
        """
        Loads valid usernames from whatever source we are retrieving them from.
        If any usernames have become invalid, deactivates them as Tellus users.
        :returns: the list of valid usernames
        """
        if len(current_valid_usernames) == 0:
            logging.error(
                "Tellus was just told there are no valid usernames.  "
                "Tellus considers this impossible, so is leaving the valid usernames as: %s.",
                list(self.get_valid_usernames()),
            )
            return self.get_valid_usernames()

        self._valid_usernames = SortedSet(current_valid_usernames)
        all_active_usernames = SortedSet(self.get_active_usernames()).update(
            self._valid_usernames
        )
        if self._valid_usernames == all_active_usernames:
            logging.info(
                "The set of %s new usernames is the same as our current %s valid usernames and Users.",
                len(self._valid_usernames),
                len(all_active_usernames),
            )
            return self.get_valid_usernames()

        logging.info("Updating valid user names.")
        removed_usernames = all_active_usernames.difference(self._valid_usernames)
        logging.info(
            "Removing %s from the list of valid usernames and Users.",
            list(removed_usernames),
        )
        for username in removed_usernames:
            self.deactivate_user(username)

        logging.info(
            "Current Valid Usernames: %s", list(self._valid_usernames),
        )

        return self.get_valid_usernames()

    def refresh(self):
        """
        Refreshes the User Manager after updates to user data in Tellus.  Includes updating
        the set of valid user names (note this is distinct from Tellus' internal set of Users), creating
        lookups by email (vs username) etc.
        """
        logging.info("Refreshing User Manager.")
        logging.info(
            "...Constructing email lookups for %s users...", self.count_active_users()
        )
        new_dict = {}
        for user in self.get_active_users():
            if user.email is None:
                logging.info(
                    "User '%s' has no associated email address.", user.username
                )
            elif user.email in new_dict:
                logging.error(
                    "User '%s' has email '%s', but that is already associated with user '%s'.  "
                    "This should not happen.",
                    user.username,
                    user.email,
                    new_dict[user.email],
                )
            else:
                new_dict[user.email] = user.username

        self._users_by_email = new_dict
        logging.info("...wired up %s emails to users.", len(self._users_by_email))
        logging.info("...User manager refresh complete")

    def is_valid_username(self, username):
        return username in self._valid_usernames

    def is_active_tellus_user(self, username):
        try:
            return self.is_valid_username(username) and self.get(username).is_active()
        except (InvalidTellusUserException, NoExistingTellusUserException):
            pass

        return False

    def login_user(self, username):
        logging.debug("'%s'  logged into Tellus.", username)
        user = self.get_or_create_valid_user(username)
        user.record_login()
        return user

    def get_or_create_valid_user(self, username):
        """
        Attempt to get a valid User, if it doesn't exist, create it.
        Note Tellus still needs to be persisted after this call if a User is created.
        Note also this will *not* get a deactivated user.
        :raises:
            InvalidTellusUserException if the username is invalid
            NoExistingTellusUserException if the Tell found for username is not a User.
        """
        if not self.is_valid_username(username):
            raise InvalidTellusUserException(
                f"'{username}' is not a valid tellus username."
            )

        new_user = None
        try:
            return self.get(username)
        except NoExistingTellusUserException as exception:
            if exception.tell:
                exception.tell.add_category(TELLUS_USER)
                logging.warning(
                    "'%s' exists as a Tell, but is not currently a user.  Adding as a User: %s",
                    username,
                    exception.tell.to_simple_json(),
                )
                new_user = User(exception.tell)

        if not new_user:
            new_user = User(
                self._teller.create_tell(
                    username, TELLUS_USER, created_by=TELLUS_APP_USERNAME
                )
            )
            logging.info("No existing User for username '%s', created one.", username)

        self.perform_new_user_setup(new_user)

        return new_user

    @staticmethod
    def perform_new_user_setup(user):
        """
        Users are special, and have some special setup as a result.
        """
        Socializer.perform_new_user_setup(user)

    def get(self, username) -> User:
        """
        :param username: the username to get a User for
        :return: the user for the given username - note that this will also get inactive users.
        :raises:
            NoExistingTellusUserException if the Tell for username is not a User.
        """
        try:
            tell = self._teller.get(username)
            if User.is_user_tell(tell):
                return User(tell)
            else:
                raise NoExistingTellusUserException(
                    f"An attempt was made to retrieve User '{username}', "
                    f"but the Tell found was not a user: {tell.to_simple_json()}",
                    tell,
                )
        except TheresNoTellingException as e:
            raise NoExistingTellusUserException(
                f"No User currently exists for '{username}'."
            ) from e

    def get_by_email(self, user_email):
        try:
            username = self._users_by_email[user_email]
            return self.get(username)
        except KeyError as e:
            raise NoExistingTellusUserException(
                f"No Tellus user was found with email '{user_email}'."
            ) from e

    def get_valid_usernames(self):
        return self._valid_usernames

    def count_active_users(self):
        return len(self._teller.tells(TELLUS_USER))

    def get_active_users(self):
        user_tells = self._teller.tells(TELLUS_USER)
        return [User(tell) for tell in user_tells]

    def get_active_usernames(self):
        user_tells = self._teller.tells(TELLUS_USER)
        return [user.alias for user in user_tells]

    def deactivate_user(self, username):
        """
        :param username: the username to deactivate as a Tellus user
        :return: the deactivated user, or None if no User could be found to deactivate
        """
        try:
            logging.info("Deactivating user %s.", username)
            user = self.get(username)
            user.tell.add_category(TELLUS_INACTIVE_USER)
            user.tell.remove_category(TELLUS_USER)
            return user
        except (InvalidTellusUserException, NoExistingTellusUserException) as e:
            logging.error("Error while attempting to deactivate user:  %s", repr(e))
            return None


class UserHandler(object):
    USERNAME = "username"

    ROUTE_WHOAMI = f"/{R_MGMT}/whoami"
    ROUTE_VALID_USERS = f"/{R_MGMT}/users"
    ROUTE_USER_INFO = f"/{R_USER}/{{{USERNAME}}}"
    ROUTE_USER_INFO_ALT = f"/{R_USER}.{{{USERNAME}}}"
    ROUTE_ALL_USERS = f"/{R_USER}/"
    ROUTE_DEBUG_LOGIN = f"/{R_MGMT}/debug_login"
    ROUTE_FORCE_TOGGLE_COFFEE_BOT = f"/{R_MGMT}/{{{USERNAME}}}/toggle_coffee_bot"

    def __init__(self, user_manager):
        self._manager = user_manager

    def setup_user_routes(self, router):
        logging.info("Setting up basic login functionality.")
        router.add_get(self.ROUTE_WHOAMI, self.whoami)
        router.add_get(self.ROUTE_VALID_USERS, self.list_valid_users)
        router.add_get(self.ROUTE_USER_INFO, self.get_user_info)
        router.add_get(
            self.ROUTE_USER_INFO_ALT, self.get_user_info
        )  # temporary-ish, for consistency with Tells
        router.add_get(self.ROUTE_ALL_USERS, self.all_users)
        router.add_get(f"{self.ROUTE_DEBUG_LOGIN}/{{email}}", self.debug_login)
        router.add_get(self.ROUTE_FORCE_TOGGLE_COFFEE_BOT, self.toggle_coffee_bot)

    async def get_user_info(self, request):
        """
        :return: the json representation of the username specified in the request
        """
        username = request.match_info[self.USERNAME]

        try:
            user = self._manager.get(username)
        except (InvalidTellusUserException, NoExistingTellusUserException) as exception:
            return web.Response(
                text=f"Error retrieving User '{username}': {str(exception)}", status=404
            )

        return web.json_response(text=user.to_simple_json())

    async def whoami(self, request):
        whoami = await TellusSession.whoami(request, self._manager)

        if whoami is None:
            whoami = ""
        return web.Response(text=whoami)

    @staticmethod
    async def debug_login(request):
        """
        Really just for testing and debugging.  Sets a debug email.
        There is probably a better way to do this.
        """
        email = request.match_info["email"]
        session = await get_session(request)
        session[SESSION_TELLUS_DEBUG_EMAIL] = email
        return web.Response(
            text=f"Debug email set to {session[SESSION_TELLUS_DEBUG_EMAIL]}.   "
            f"(Note this won't actually do anything in production.)"
        )

    async def toggle_coffee_bot(self, request):
        """
        Toggle Coffee Bot for the specified use.  A temporary way to force it if people aren't around, or (currently)
        if they leave.  Should eventually be deprecated when inactive users are handled better.
        """
        username = request.match_info[UserHandler.USERNAME]
        response = {
            username: (
                CoffeeBot.TAG_COFFEE_BOT,
                (
                    self._manager.teller.toggle_tag(username, CoffeeBot.TAG_COFFEE_BOT)
                    is not None
                ),
            )
        }
        logging.info("Tellus admin toggle of coffee bot: %s", response)
        self._manager.teller.persist()
        return web.json_response(text=json.dumps(response))

    async def all_users(self, _):
        json_users = {
            user.username: user.to_simple_json()
            for user in self._manager.get_active_users()
        }

        return web.json_response(text=json.dumps(json_users))

    async def list_valid_users(self, request):
        session = await TellusSession.construct(request, self._manager)

        response = ["Valid Tellus users:"]
        for user in self._manager.get_valid_usernames():
            if user == session.tellus_internal_username:
                response.append(user + " <-- current user")
            else:
                response.append(user)

        return web.Response(text="\n".join(response))
