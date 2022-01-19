import logging

from tellus.configuration import (
    TELLUS_USER_MODIFIED,
    TELLUS_GO,
    TELLUS_ABOUT_TELL,
    TELLUS_USER,
    TELLUS_INTERNAL,
    TELLUS_APP_USERNAME,
)
from tellus.sources import Source
from tellus.tell import Tell
from tellus.tells import TheresNoTellingException
from tellus.tellus_sources.socializer import CoffeeBot, Socializer
from tellus.tellus_utils import now_string
from tellus.wiring import ui_route_to_tell


class TellusInitialization(Source):
    """
    A special source that does some basic initialization of information for Tellus.
    This includes:
    - Setting up some internal Tellus Tells such as a default About tell
    - Running data migrations and cleanups between versions of Tellus.  These will often not run
        if it is not presently in a version of Tellus that requires a migration.

    This source needs to be very careful to only run in appropriate circumstances - it usually only runs
    once on startup, and should only run migrations with particular versions of Tellus, etc.
    """

    TELLUS_ABOUT_DESCRIPTION = "About Tellus."

    def __init__(self, teller, active_migrations=None):
        """
        :param teller: The usual.
        :param active_migrations:  For testing, to override with specific migration functions.
        """
        super().__init__(
            teller,
            source_id="data-migration",
            description="A special source for managing and migrating Tellus data between versions.",
            datum_display_name="Data Migration",
            run_restriction=Source.RUN_ON_STARTUP,
        )

        # This call is to ensure my Tell always exists - important for tests to run correctly
        self.source_tell.get_data_dict()

        self._migrations_run = 0
        if active_migrations is not None:
            self._active_migrations = active_migrations
        else:
            # THIS IS WHERE MIGRATIONS ARE SPECIFIED...
            self._active_migrations = [self.migration_update_coffee_bot_history_2021_05]

    async def load_source(self):
        # Note that for these, they will each individually persist, as some of the migrations may want
        # to persist sooner
        await self._create_default_tells()
        await self._run_migrations()

    def verify_or_create_about_tell(self):
        try:
            tellus_about = self.teller.get(TELLUS_ABOUT_TELL)
        except TheresNoTellingException:
            logging.info(
                "There is currently no 'About Tellus' Tell (%s).  Tellus is creating one.",
                TELLUS_ABOUT_TELL,
            )
            tellus_about = self.teller.create_tell(
                TELLUS_ABOUT_TELL,
                TELLUS_GO,
                self.source_id,
                url=ui_route_to_tell(TELLUS_ABOUT_TELL),
                description=self.TELLUS_ABOUT_DESCRIPTION,
            )

        if not tellus_about.has_tag(TELLUS_APP_USERNAME):
            tellus_about.add_tag(TELLUS_APP_USERNAME)
            return True

        return False

    async def _create_default_tells(self):
        should_persist = False
        should_persist = self.verify_or_create_about_tell() or should_persist

        if should_persist:
            self.teller.persist()

    async def _run_migrations(self):
        if len(self._active_migrations) == 0:
            logging.info(
                "No current migrations specified.  Will not run the Data Migration Source."
            )
            return

        for migration in self._active_migrations:
            migration_name = migration.__name__
            if self.source_tell.get_data(migration_name) is not None:
                logging.info(
                    "Migration %s has already been run.  Migrations will only be run once."
                )
            else:
                logging.info("Running %s", migration_name)
                migration()
                self.source_tell.update_datum_from_source(
                    migration_name, "Completed At", now_string()
                )
                logging.info("%s complete.", migration_name)
                self._migrations_run += 1

        self.teller.persist()

        logging.info(
            "Migrations complete - have run %s of %s migrations since startup.",
            self._migrations_run,
            len(self._active_migrations),
        )

    @staticmethod
    def _clear_old_data(tell, data_key):
        """
        Common use case.
        """
        if tell.get_data(data_key):
            old_data = tell.clear_data(data_key)
            logging.info(
                "Removed deprecated '%s' data from Tell '%s': %s",
                data_key,
                tell.alias,
                old_data,
            )

    def migration_update_coffee_bot_history_2021_05(self):
        """
        Update the User Tell coffee history for the new User page
        """
        user_tells = self.teller.tells(TELLUS_USER)
        coffee_tell = self.teller.get(CoffeeBot.TELL_COFFEE_BOT)
        coffee_bot = CoffeeBot(coffee_tell)
        logging.info(
            "migration_update_coffee_bot_history_2021_05: Updating CoffeeBot histories for all Users for new User Page."
        )
        for user_tell in user_tells:
            # Yes, all of this is totally cheating
            if (
                user_tell.get_datum(
                    Socializer.SOURCE_ID, CoffeeBot.DATUM_COFFEE_HISTORY
                )
                is None
            ):
                coffee_bot.update_user_history_for(user_tell, user_tell.alias)

    ####
    # Deprecated migrations  - these can usually go away eventually, but keeping some around for a couple of iterations
    # for examples and easy cribbing.
    ####
    def deprecated_migration_users_remove_tellus_internal_2020_11(self):
        """
        Had a situation where Users were all being added to TELLUS_INTERNAL when they logged in as a side effect of
        the new Categories-are-just-data-sources thing.  This cleans that up.
        """
        user_tells = self.teller.tells(TELLUS_USER)
        for user_tell in user_tells:
            if user_tell.in_category(TELLUS_INTERNAL):
                logging.info(
                    "migration_users_remove_tellus_internal_2020_11: Removing 'tellus-internal' from %s.",
                    user_tell.alias,
                )
                user_tell.remove_category(TELLUS_INTERNAL)

    def deprecated_migration_data_dict_includes_user_modified_data_2010_10(self):
        # pylint: disable=protected-access
        # some weird special cases
        ignore = [
            "groot",
            "prod-viewport",
            "tellus-coffee-bot",
            "tellus-config-tools",
            "tellus-source-data-migration",
        ]

        for tell in self.teller.tells():
            if (
                tell.in_any_categories([TELLUS_USER_MODIFIED, TELLUS_GO])
                and tell.alias not in ignore
            ):
                data = {}
                if tell.description is not None and len(tell.description) > 0:
                    data[Tell.DESCRIPTION] = tell.description
                else:
                    tell._description = None  # Yes, need to do this to fix old blanks
                if tell.go_url is not None and len(tell.go_url) > 0:
                    data[Tell.GO_URL] = tell.go_url
                else:
                    tell._go_url = None  # Yes, need to do this to fix old blanks
                if len(tell.tags) > 0:
                    data[Tell.TAGS] = ", ".join(tell.tags)
                tell.update_data_from_source(TELLUS_USER_MODIFIED, data, self.source_id)
