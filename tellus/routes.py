import logging

from aiohttp import web

# Known Routes and Route Parts
from tellus.creds import get_credentials_from_vault

from tellus.configuration import VAULT_PATH
from tellus.tells_handler import TellsHandler
from tellus.wiring import (
    FAIL,
    R_GO,
    R_LINKS,
    R_TELL,
    R_SOURCES,
    STATIC_FILES,
    R_TESTING,
    PARAM_SEPARATOR,
    ALL,
    TELL_DELETE,
    TELL_UPDATE,
    R_TELLS,
    R_UNSECURE,
    R_SEARCH,
)

STATIC_DIR = "web/public"

# Mostly used for debugging
URL_ALL_GO_LINKS = f"{R_GO}/{ALL}"

# Tell actions
URL_TELL_UPDATE = f"{R_TELL}/{TELL_UPDATE}"  # post only!
TELL_TOGGLE_TAG = f"{R_TELL}/{TellsHandler.TELLUS_TOGGLE_TAG}"  # post only!

# Debugging Info
TELLUS_STATUS = f"/{R_TESTING}/tellus-status"
CONSUL_CHECK = f"/{R_UNSECURE}/consul_check"

_loading = False


def setup_routes(app, tell_handler, source_handler, user_manager):
    # ORDER MATTERS for many of these...
    router = app.router
    router.add_route("*", "/", home)

    router.add_get(f"/{FAIL}", fail)

    # Note the first route returns links for all Tells:
    router.add_get(f"/{R_LINKS}/", tell_handler.query_links)
    router.add_get(f"/{R_LINKS}/" + "{query_string}", tell_handler.query_links)

    # Note the first route returns all Tells:
    router.add_get(f"/{R_TELLS}/", tell_handler.query_tells)
    router.add_get(f"/{R_TELLS}/" + "{query_string}", tell_handler.query_tells)

    router.add_get(f"/{R_SEARCH}/", tell_handler.search_for)
    router.add_get(f"/{R_SEARCH}/" + "{search_string}", tell_handler.search_for)

    router.add_get(f"/{R_TELL}/" + "{alias}", tell_handler.get_tell)
    # allowing this as an alternative:
    router.add_get(f"/{R_TELL}" + PARAM_SEPARATOR + "{alias}", tell_handler.get_tell)
    router.add_get(
        f"/{R_TELL}/" + "{alias}" + f"/{TELL_DELETE}", tell_handler.delete_tell
    )
    router.add_post(f"/{URL_TELL_UPDATE}", tell_handler.update_tell)
    router.add_post(f"/{TELL_TOGGLE_TAG}", tell_handler.toggle_tag)

    # needs to be first to override g/:
    router.add_get(f"/{URL_ALL_GO_LINKS}", tell_handler.all_go_links)
    router.add_get(f"/{R_GO}", tell_handler.create_go_tell)
    router.add_post(f"/{R_GO}", tell_handler.create_go_tell)
    router.add_get(f"/{R_GO}/" + "{alias}", tell_handler.goto)

    router.add_get("/sources", source_handler.sources)
    router.add_get(f"/{R_SOURCES}", source_handler.sources)
    router.add_get(f"/{R_SOURCES}/load-all", source_handler.load_all_sources)
    router.add_get(
        f"/{R_SOURCES}/" + "{source_id}/load", source_handler.load_single_source
    )

    # Mostly for debugging
    tell_handler.add_debug_route("Status", router, TELLUS_STATUS, tell_handler.status)
    tell_handler.add_debug_route("Consul", router, CONSUL_CHECK, tell_handler.is_alive)
    tell_handler.add_debug_route(
        "Save File", router, f"/{R_TESTING}/tellus-save-file", tell_handler.save_file
    )
    tell_handler.add_debug_route(
        "Test Vault", router, f"/{R_TESTING}/test-vault", test_vault
    )
    tell_handler.add_debug_route(
        "Dump Session Info",
        router,
        f"/{R_TESTING}/session-info",
        tell_handler.dump_session_information,
    )
    tell_handler.add_debug_route(
        "We Are Groot", router, f"/{R_TESTING}/we-are-groot", tell_handler.we_are_groot
    )

    user_manager.setup_user_routes(router)

    # This must be towards the end - HOWEVER, it must be before the master route
    router.add_static(f"/{STATIC_FILES}", path=STATIC_DIR)

    # This is the master route.  Anything that isn't overridden above should just route to the go link
    # using /<alias>
    router.add_get("/{alias}", tell_handler.goto)
    router.add_get("/{alias}/", tell_handler.goto)
    router.add_get("/{alias}/{shortcut}", tell_handler.goto)

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        _print_routes(router)


def _print_routes(router):
    print("****  Currently Defined Routes:  ****\n")
    for resource in router.resources():
        print(resource)


def loading(status):
    # pylint: disable=global-statement
    # I know, I know...
    global _loading
    _loading = status
    if _loading:
        logging.info("Tellus is currently loading...")
    else:
        logging.info("Loading complete!  Tellus is ready for Telling.")


async def home(_):
    if _loading:
        return web.Response(text="Tellus is loading...stand by...")
    return web.FileResponse(f"{STATIC_DIR}/index.html")


async def test_vault(_):
    get_credentials_from_vault(path=VAULT_PATH)
    return web.Response(text="OK")


async def fail(_):
    logging.info("Fail route called")
    raise RuntimeError("This is a test exception.")
