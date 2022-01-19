import json
import logging
from abc import ABC
from aiohttp import web
from tellus.tell import Tell, InvalidAliasException
from tellus.tells import Teller, TheresNoTellingException
from tellus.tellus_utils import now_string, TellusException
from hotsocket.timer import DurableTimer

from tellus.configuration import TELLUS_APP_USERNAME, TELLUS_PREFIX, TELLUS_INTERNAL

SRC_PREFIX = f"{TELLUS_PREFIX}src-"
SRC_UNSPECIFIED = f"{SRC_PREFIX}unspecified"

STATUS_NOT_RUN = "Not Run"
STATUS_RUNNING = "Running"
STATUS_COMPLETED = "Completed"
STATUS_FAILED = "Failed"


class Source(ABC):
    RUN_ON_STARTUP = "on-startup"

    _PREFIX = f"{TELLUS_PREFIX}source-"

    def __init__(
        self,
        teller: Teller,
        *,
        source_id,
        description,
        datum_display_name=None,
        run_restriction=None,
    ):
        if source_id != Tell.clean_alias(source_id):
            raise InvalidAliasException(
                source_id, "Sources must have an alias that can be a valid Tell alias."
            )

        self._teller = teller
        self._source_id = source_id

        self._description = description
        self._last_run = None
        self._last_run_message = STATUS_NOT_RUN
        self._status = STATUS_NOT_RUN
        if not datum_display_name:
            self._display_name = source_id
        else:
            self._display_name = datum_display_name

        self._run_restriction = run_restriction

    @property
    def source_tell_alias(self):
        return f"{Source._PREFIX}{self._source_id}"

    @property
    def source_tell(self):
        try:
            return self._teller.get(self.source_tell_alias)
        except TheresNoTellingException:
            logging.info(
                "Creating Tell for '%s' source (Alias: %s).",
                self._source_id,
                self.source_tell_alias,
            )
            return self._teller.create_tell(
                self.source_tell_alias, TELLUS_INTERNAL, TELLUS_APP_USERNAME
            )

    def datum(self, tell, key, default=None):
        """
        Return the specified datum from my data block on a Tell.
        """
        return tell.get_datum(self.source_id, key, default)

    @property
    def teller(self):
        return self._teller

    @staticmethod
    def create_transient_teller() -> Teller:
        """
        Creates a teller to hold onto Tells *only* for this source.  This is kind of experimental, and should be used
        carefully.

        :return:  A new teller with no Persistor.
        """
        return Teller(persistor=None)

    @property
    def source_id(self):
        return self._source_id

    @property
    def description(self):
        return self._description

    @property
    def last_run(self):
        return self._last_run

    @property
    def display_name(self):
        return self._display_name

    @property
    def run_restriction(self):
        return self._run_restriction

    @property
    def should_run(self):
        if self._run_restriction == self.RUN_ON_STARTUP and self._last_run is not None:
            return False

        return True

    def status_starting(self):
        """
        :return: True if the last run of load was successful, False otherwise.
        """
        self._last_run = now_string()
        self._last_run_message = "Currently running..."
        self._status = STATUS_RUNNING

    def status_failed(self, message):
        self._last_run_message = message
        self._status = STATUS_FAILED

    def status_complete(self, message):
        """
        :return: True if the last run of load was successful, False otherwise.
        """
        self._last_run_message = message
        self._status = STATUS_COMPLETED

    @property
    def load_completed(self):
        """
        :return: True if the last run of load was successful, False otherwise.
        """
        return self._status == STATUS_COMPLETED

    @property
    def load_failed(self):
        """
        :return: True if the last run of load failed, False otherwise.
        """
        return self._status == STATUS_FAILED

    async def load_source(self):
        """
        Invoke whatever functionality is needed to load the source.  These should generally not be called directly,
        but instead will be called via load().

        NOTE: this should be an @abstractmethod - but is not because it is also async which causes weird behavior.
        It MUST be overridden by any subclasses or will throw an exception.

        :return: a string with any message about the load results
        """
        raise Exception("load_source must be overridden")

    def update_from_source(self, tell, datum, value):
        tell.update_datum_from_source(self.source_id, datum, value)

    def source_info(self):
        return {
            "source_id": self.source_id,
            "description": self.description,
            "display_name": self.display_name,
            "last_run": self.last_run,
            "last_run_message": self._last_run_message,
            "status": self._status,
        }


class DuplicateSourceException(TellusException):
    def __init__(self, source_id):
        TellusException.__init__(
            self,
            f"Attempted to add two sources with the same source id: '{source_id}'.",
        )


class Sourcer:
    DEFAULT_PERIOD = 3600  # seconds

    def __init__(self, teller, enabled_sources):
        self._teller = teller
        self._sources = {}
        for source in enabled_sources:
            if source.source_id in self._sources:
                raise DuplicateSourceException(source.source_id)
            self._sources[source.source_id] = source

        self._runs = 0

        logging.info("The following sources are enabled:  %s", self.active_source_ids())

    def active_source_ids(self):
        return list(self._sources.keys())

    def active_source_info(self):
        """
        :return: a map of source_id to info about the source (e.g., description), for each active source.
        """
        info_dict = {}
        for source in self._sources.values():
            info_dict[source.source_id] = source.source_info()

        return info_dict

    async def load_sources(self):
        self._runs += 1
        logging.info("SOURCER RUN %s STARTING.", self._runs)

        for source in self._sources.values():
            await self.run_load_source(source)

        logging.info(
            "SOURCER RUN %s COMPLETE.  All enabled sources loaded.", self._runs
        )

    async def load_source_for_id(self, source_id):
        return await self.run_load_source(self._sources[source_id])

    @staticmethod
    async def run_load_source(source):
        """
        Does any necessary common set up and teardown for the load, but mostly defers to load_source.

        :return: a string with any message about the load results (e.g., for return in a web response)
        """
        if not source.should_run:
            message = (
                f"'{source.source_id}' source will not load, as it has a run restriction of {source.run_restriction}."
                f"  Last run was:  {source.last_run}",
            )
            logging.info(message)
            return message

        logging.info("SOURCE:  '%s' - starting load", source.source_id)
        source.status_starting()
        try:
            message = await source.load_source()
        # pylint: disable=broad-except
        except Exception as exception:
            message = f"'{source.source_id}' source failed to load, with exception: {repr(exception)}"
            source.status_failed(message)
            logging.exception(message)
            return message

        if message is None:
            message = STATUS_COMPLETED
        source.status_complete(message)
        logging.info("SOURCE '%s' - load complete: %s", source.source_id, message)
        return message

    @staticmethod
    async def periodic_load_alert(exception):
        logging.error("Received an error during source run: %s", repr(exception))

    def start_periodic_loads(self, period=DEFAULT_PERIOD):
        logging.info(
            "Scheduling Tellus to reload its sources every %s seconds.", period
        )
        if period < self.DEFAULT_PERIOD:
            logging.warning(
                "The period is less than the default period of %s.  Be advised.",
                self.DEFAULT_PERIOD,
            )

        timer = DurableTimer(None, self.load_sources, period)
        timer.start()


class SourceHandler(object):
    """
    The handler for the web interface around sources.
    """

    def __init__(self, sourcer):
        self._sourcer = sourcer

    def sources(self, _):
        return web.json_response(text=json.dumps(self._sourcer.active_source_info()))

    async def load_single_source(self, request):
        source_id = request.match_info["source_id"]
        await self._sourcer.load_source_for_id(source_id)
        return web.Response(text=f"Load started for source {source_id}")

    async def load_all_sources(self, _):
        await self._sourcer.load_sources()
        return web.Response(text="Load started for all sources.")
