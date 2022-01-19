import asyncio
import logging
import sys
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from aiohttp import web
from aiohttp_session import session_middleware, SimpleCookieStorage

from tellus import routes, __version__
from tellus.configuration import TELLUS_SAVE_FILE_NAME
from tellus.persistence import PickleFilePersistor
from tellus.sources import Sourcer, SourceHandler
from tellus.tells import Teller
from tellus.tells_handler import TellsHandler
from tellus.tellus_sources.tellus_initialization_source import TellusInitialization
from tellus.tellus_sources.socializer import Socializer
from tellus.tellus_sources.tellus_yaml_source import TellusYMLSource
from tellus.tellus_sources.user_info_source import UserInfo
from tellus.users import UserHandler, UserManager
from tellus.wiring import TELLUS_COOKIE_NAME


def _parse_arguments():
    parser = ArgumentParser("tellus", formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", help="Log at debug level", action="store_true")
    parser.add_argument(
        "--persistence-root", help="Set the root directory for the persistence files."
    )
    parser.add_argument("--host", default="0.0.0.0", help="set the host to bind to")
    parser.add_argument(
        "--port", type=int, default=8080, help="set the port to bind to"
    )
    return parser.parse_args()


async def _load_tellus(teller, sourcer):
    teller.load_tells()
    routes.loading(False)
    sourcer.start_periodic_loads()

    logging.info("Tellus is ready for Telling.")


async def on_prepare(_, response):
    response.headers["cache-control"] = "no-cache"


def _create_and_load_webapp(teller, sourcer, user_manager):
    session = session_middleware(SimpleCookieStorage(cookie_name=TELLUS_COOKIE_NAME))

    app = web.Application(middlewares=[session])
    app.on_response_prepare.append(on_prepare)

    routes.loading(True)

    user_handler = UserHandler(user_manager)
    tell_handler = TellsHandler(teller, user_manager)
    source_handler = SourceHandler(sourcer)

    routes.setup_routes(app, tell_handler, source_handler, user_handler)

    asyncio.ensure_future(_load_tellus(teller, sourcer))

    return app


def _run_app(args):
    persistor = PickleFilePersistor(
        persist_root=args.persistence_root, save_file_name=TELLUS_SAVE_FILE_NAME
    )

    teller = Teller(persistor)

    user_manager = UserManager(teller)

    # Note: Order Matters here, as the first Source will win for creating any new Tells
    # And some sources will be affected by the results of earlier sources
    # (e.g., UserInfo updates the list of valid users...)
    enabled_sources = [
        TellusInitialization(
            teller
        ),  # This should almost certainly always be first, to ensure data is clean
        UserInfo(user_manager),
        TellusYMLSource(teller),
        Socializer(user_manager),
        #DNSHandler(teller),  # DNS Should probably always be last, as it is the noisiest
    ]

    sourcer = Sourcer(teller, enabled_sources)

    app = _create_and_load_webapp(teller, sourcer, user_manager)

    logging.info("Starting web app...")
    web.run_app(app, host=args.host, port=args.port)
    logging.info("Tellus out.")


def main(argv):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)-25s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    logging.info("Starting tellus version %s with arguments: %s", __version__, argv)

    args = _parse_arguments()
    if args.debug:
        logging.root.setLevel(logging.DEBUG)
    else:
        logging.getLogger("aiohttp.access").setLevel(
            logging.WARN
        )  # Without this aiohttp is suuuuuuuper chatty

    _run_app(args)


if __name__ == "__main__":
    main(sys.argv)
