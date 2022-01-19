import json
import logging

from aiohttp import web
from aiohttp_session import get_session

from tellus import __version__
from tellus.tell import Tell
from tellus.configuration import (
    TELLUS_INTERNAL,
    TELLUS_GO,
    TELLUS_USER_MODIFIED,
    TELLUS_ABOUT_TELL,
)
from tellus.tells import TheresNoTellingException
from tellus.users import TellusSession, User, is_user
from tellus.wiring import (
    PARAM_SEPARATOR,
    TELLUS_PROTOCOL,
    ALL_TELLS,
    ui_route_to_tell,
    ui_route_go,
    TELL_TOGGLE_TAG,
    UI_SUPPRESSED_CATEGORIES,
    STATIC_FILES,
)


class TellsHandler(object):
    """
    The main handler for the web interface around Tells
    """

    TELLUS_TOGGLE_TAG = TELL_TOGGLE_TAG
    TELLUS_DEBUG_SOURCE = "tellus-debug-info"
    PARAM_QUERY_STRING = "query_string"
    PARAM_SEARCH_STRING = "search_string"
    WHOAMI_API_NO_USER = "[Presumed API call with no specified user]"

    def __init__(self, teller, user_manager):
        self._teller = teller
        self._user_manager = user_manager
        self._debug_urls = {}

    def _simple_json(self, tell):
        """
        Return the simple JSON for the specified Tell.
        Users are special, so we have to handle their JSON a little differently.
        """
        if is_user(tell):
            return User.enhanced_simple_json(tell)
        return tell.to_simple_json()

    async def get_tell(self, request):
        """
        Get a single Tell, matching the alias sent in the request
        """
        alias = request.match_info[Tell.ALIAS]
        tell = self._retrieve_tell(alias)
        return web.json_response(text=self._simple_json(tell))

    def _retrieve_tell(self, alias):
        """
        Retrieves a tell for the given alias and decorates with any transient information.
        """
        tell = self._teller.get(alias)

        self._decorate_transient_information(tell)

        return tell

    def _decorate_transient_information(self, tell):
        # Right now this is just for this single tell, will extend further
        if tell.alias == TELLUS_ABOUT_TELL:
            self._update_about_tell(tell)

    async def create_go_tell(self, request):
        params = await request.post()
        if params == {}:
            return web.HTTPFound("/#go")
        session = await TellusSession.construct(request, self._user_manager)

        logging.info("Go link created by %s.", session.username)

        tell = await self._create_tell(TELLUS_GO, params, session.username)
        return web.json_response(text=tell.go_json())

    async def _create_tell(self, category, params, username):
        logging.info(
            "Attempt by %s to create tell with parameters: %s", username, params
        )
        tell = self._teller.create_tell_with_parameters(
            TELLUS_USER_MODIFIED, params, username
        )
        tell.add_category(category)
        self._teller.persist()
        logging.info("Tell created: %s", self._simple_json(tell))
        return tell

    async def update_tell(self, request):
        params = await request.post()
        session = await TellusSession.construct(request, self._user_manager)
        logging.info(
            "Request to update tell by '%s', with parameters: %s",
            session.username,
            params,
        )
        tell = self._teller.update_tell_from_ui(
            params, session.username, replace_tags=True
        )
        self._teller.persist()

        return web.json_response(text=self._simple_json(tell))

    async def delete_tell(self, request):
        alias = request.match_info[Tell.ALIAS]
        tell = self._teller.delete_tell(alias)
        self._teller.persist()
        return web.Response(text=f"DELETED TELL '{alias}': {self._simple_json(tell)}")

    def query_for(self, request, tell_repr_method=Tell.minimal_tell_dict.__name__):
        try:
            query_string = request.match_info[self.PARAM_QUERY_STRING]
        except KeyError:
            query_string = None

        if (
            query_string is None
            or query_string == PARAM_SEPARATOR
            or query_string == ALL_TELLS
        ):
            return self._all_displayable_tells(tell_repr_method,)
        else:
            return self._teller.query_tells(
                query_string=query_string, tell_repr_method=tell_repr_method
            )

    def query_tells(self, request):
        return web.json_response(self.query_for(request))

    def query_links(self, request):
        return web.json_response(self.query_for(request, "go_url"))

    def _all_displayable_tells(self, tell_repr_method):
        return self._teller.query_tells(
            query_string=None,
            ignore_categories=UI_SUPPRESSED_CATEGORIES,
            tell_repr_method=tell_repr_method,
        )

    def search_for(self, request):
        """
        Perform a search of Tellus and return the results as a set of Tells.  This is currently for a set of Tells -
        but should eventually have broader search functionality across other sources.
        """
        try:
            search_string = request.match_info[self.PARAM_SEARCH_STRING]
        except KeyError:
            return web.json_response(
                self._all_displayable_tells(Tell.minimal_tell_dict.__name__)
            )

        search_tells = self._teller.search_tells(search_string)
        return web.json_response(
            {tell.alias: tell.minimal_tell_dict() for tell in search_tells}
        )

    def all_go_links(self, _=None):
        return web.json_response(text=json.dumps(self._teller.query_tells(TELLUS_GO)))

    async def goto(self, request):
        alias = request.match_info[Tell.ALIAS]
        logging.info("goto %s", alias)
        shortcut = request.match_info.get("shortcut")
        redirection_url = self.retrieve_redirection_url(self._teller, alias, shortcut)
        if redirection_url is None:
            return web.Response(status=302, headers={"location": ui_route_go(alias)})

        logging.debug("Redirecting to: %s", redirection_url)
        return web.Response(status=302, headers={"location": redirection_url})

    @staticmethod
    def retrieve_redirection_url(teller, alias, shortcut=None):
        try:
            tell = teller.get(alias)

            if shortcut == "t":
                return ui_route_to_tell(alias)

            return tell.go_url
        except TheresNoTellingException as exception:
            logging.info(
                "Failed attempt to retrieve tell '%s' for redirection: %s",
                alias,
                repr(exception),
            )
            return None

    async def toggle_tag(self, request):
        params = await request.post()
        alias = params[Tell.ALIAS]
        tag = params[self.TELLUS_TOGGLE_TAG]
        try:
            response = {alias: (tag, (self._teller.toggle_tag(alias, tag) is not None))}
            self._teller.persist()
        except TheresNoTellingException:
            logging.info(
                "Tried to toggle tag '%s' for non-existent Tell '%s'.", tag, alias
            )
            response = False

        return web.json_response(text=json.dumps(response))

    # These are really Tellus methods for debugging and the like.
    # Should probably be refactored into another class at some point.
    async def status(self, request, *, api_call=False):
        if api_call:
            whoami = TellsHandler.WHOAMI_API_NO_USER
        else:
            whoami = await TellusSession.whoami(request, self._user_manager)

        return web.json_response(
            text=json.dumps(
                {
                    "tellusVersion": __version__,
                    "localPersistence": self._teller.is_local_persistence(),
                    "whoami": whoami,
                    f"valid users ({len(self._user_manager.get_valid_usernames())})": list(
                        self._user_manager.get_valid_usernames()
                    ),
                    f"active users ({len(self._user_manager.get_active_usernames())})": list(
                        self._user_manager.get_active_usernames()
                    ),
                }
            )
        )

    async def is_alive(self, request):
        """
        This is presently for the CONSUL_CHECK of aliveness, and will assume there is not a valid user.
        (To prevent a bunch of warnings in the log.)
        """
        return await self.status(request, api_call=True)

    def save_file(self, _=None):
        # Note: this should not be a json_response for now as the file format yields a weird error
        return web.Response(text=self._teller.read_file())

    @staticmethod
    async def dump_session_information(request):
        """
        Mostly for debugging - will dump session information to the Tellus log file.
        """
        info = "\nSession Data:\n"

        session = await get_session(request)
        for key in session.keys():
            info += f"{key}: {session.get(key)}\n"

        info += f"Headers {len(request.headers)}:\n"

        session = await get_session(request)
        for key in request.headers:
            info += f"{key}: {request.headers.get(key)}\n"

        logging.info(info)
        return web.Response(text="\nSession info logged.\n")

    async def we_are_groot(self, _):
        """
        Yes, mostly an easter egg, though was originally using it to test some things.
        Making this an internal Tell to keep it "hidden".
        """
        logging.info("We are groot.")
        if not self._teller.has_tell("groot"):
            groot = self._teller.create_tell(
                "groot", TELLUS_INTERNAL, "tellus", url="tellus:dgroothuis"
            )
            groot.make_user_modified()  # But making it user-modifiable to keep it removable
        return web.Response(text="We are Groot.")

    def add_debug_route(self, label, router, url, function):
        """
        Stashing these URLs to put somewhere useful later.
        """
        self._debug_urls[label] = f"{TELLUS_PROTOCOL}{url}"
        router.add_get(url, function)

    @property
    def debug_urls(self):
        return dict(self._debug_urls)

    def _update_about_tell(self, tell):
        """
        Update the "About Tellus" tell with assorted useful information and links, including some debugging tools.
        """
        tell.clear_data(self.TELLUS_DEBUG_SOURCE)
        tell.update_datum_from_source(
            self.TELLUS_DEBUG_SOURCE, "Tellus Version", __version__
        )
        tell.update_data_from_source(self.TELLUS_DEBUG_SOURCE, self._debug_urls)
        tell.update_datum_from_source(
            self.TELLUS_DEBUG_SOURCE,
            "DEV ONLY - Coverage Report",
            f"tellus:/{STATIC_FILES}/tests/coverage/index.html",
        )

        tell.update_datum_from_source(
            self.TELLUS_DEBUG_SOURCE,
            "Old About Page",
            f"tellus:/{STATIC_FILES}/tellus.html",  # For posterity...
        )
