import calendar
import logging
import random
from datetime import timedelta

from tellus.sources import Source
from tellus.configuration import TELLUS_PREFIX, TELLUS_INTERNAL, TELLUS_USER_MODIFIED
from tellus.tells import TheresNoTellingException
from tellus.tellus_utils import now_string, datetime_from_string, now


class Socializer(Source):
    """
    A 'source' that causes us to socialize!  Coffee Bot, Lunch Bot, etc.
    """

    SOURCE_ID = "socializer"

    def __init__(self, user_manager):
        super().__init__(
            user_manager.teller,
            source_id=self.SOURCE_ID,
            description="Manages Setting up coffees, lunches, etc.",
        )
        self._user_manager = user_manager

    async def load_source(self):
        if self.should_generate_new_coffee_schedule():
            self.make_coffee_schedule()
            pairings = self.lock_in_coffee_schedule()
            self.teller.persist()
            message = f"Coffee Bot ran successfully.  Pairings: {pairings}"
        else:
            if self.coffee_bot().paused:
                message = "CoffeeBot is presently paused, and will not generate new coffee schedules."
            else:
                message = "Coffee Bot already ran - it will not run again until the weekend, unless forced."

        logging.debug(message)
        return message

    def should_generate_new_coffee_schedule(self):
        return self.coffee_bot().should_generate_coffee()

    def determine_coffee_bot_users(self):
        all_users = self._user_manager.get_active_users()
        coffee_usernames = []
        for user in all_users:
            if user.tell.has_tag(CoffeeBot.TAG_COFFEE_BOT):
                coffee_usernames.append(user.username)

        return coffee_usernames

    def make_coffee_schedule(self):
        logging.info("Makin' coffee!")
        bot = self.coffee_bot()

        people = self.determine_coffee_bot_users()
        bot.update_schedule(people)

        return bot

    def lock_in_coffee_schedule(self):
        bot = self.coffee_bot()
        pairings = bot.lock_in_current_schedule(self._user_manager.get_active_users())
        bot.finished_run()  # If we forced a run, remove the force
        return pairings

    def coffee_bot(self):
        try:
            return CoffeeBot(self.teller.get(CoffeeBot.TELL_COFFEE_BOT))
        except TheresNoTellingException:
            logging.info("No coffee bot Tell yet, creating it and scheduling a run.")
            tell = self.teller.create_tell(
                CoffeeBot.TELL_COFFEE_BOT,
                TELLUS_INTERNAL,
                self.source_id,
                description="Shh...I am a secret Tell for Coffee Bot.",
            )
            tell.add_category(
                TELLUS_USER_MODIFIED
            )  # Going to allow this to be edited for now
            bot = CoffeeBot(tell)
            bot.force_run()
            return bot

    @staticmethod
    def perform_new_user_setup(user):
        """
        Perform some social set up on new users added to Tellus.
        """
        user.tell.add_tag(
            CoffeeBot.TAG_COFFEE_BOT
        )  # New users get added to Coffee Bot by default


class CoffeeBot:
    """
    A wrapper around our Coffee Schedule Tell, to make it a cleaner abstraction.
    """

    TAG_COFFEE_BOT = "coffee-bot"
    TELL_COFFEE_BOT = TELLUS_PREFIX + TAG_COFFEE_BOT
    TAG_FORCE_COFFEE = "force-coffee"
    TAG_PAUSE_COFFEE = "pause-coffee"

    BYE_WEEK_COFFEE = "BYEWEEK"
    DATUM_CURRENT_COFFEE_SCHEDULE = "coffee schedule"
    DATUM_SCHEDULED_USERS = "users in schedule"
    DATUM_LAST_SCHEDULE_CREATED = "coffee schedule created on"
    DATUM_CURRENT_COFFEE_PAIR = "coffee-pair"
    DATUM_COFFEE_HISTORY = "coffee-history"
    DATUM_LAST_COFFEE_BOT_RUN = "last coffee bot run"

    def __init__(self, coffee_tell, history=None):
        self._tell = coffee_tell
        if self._tell.get_data(Socializer.SOURCE_ID) is None:
            if history is None:
                self._update_datum(self.DATUM_COFFEE_HISTORY, {})
            else:  # Mostly for testing
                self._update_datum(self.DATUM_COFFEE_HISTORY, history)

    def _datum(self, datum, default=None):
        return self._tell.get_datum(Socializer.SOURCE_ID, datum, default)

    def _update_datum(self, datum, value):
        self._tell.update_datum_from_source(Socializer.SOURCE_ID, datum, value)

    def current_schedule(self):
        return self._datum(self.DATUM_CURRENT_COFFEE_SCHEDULE)

    def current_scheduled_users(self):
        return self._datum(self.DATUM_SCHEDULED_USERS)

    def coffee_with(self, username):
        return CoffeeBot.coffee_from_schedule(username, self.current_schedule())

    def force_run(self):
        self._tell.add_tag(self.TAG_FORCE_COFFEE)

    def pause(self, pause=True):
        if pause:
            self._tell.add_tag(self.TAG_PAUSE_COFFEE)
        else:
            self._tell.remove_tag(self.TAG_PAUSE_COFFEE)

    @property
    def paused(self):
        return self._tell.has_tag(self.TAG_PAUSE_COFFEE)

    def finished_run(self):
        if self._tell.remove_tag(self.TAG_FORCE_COFFEE) is not None:
            logging.info("Coffee was forced, removed %s tag.", self.TAG_FORCE_COFFEE)
        self._update_last_run()

    @property
    def last_run(self):
        return self._datum(self.DATUM_LAST_COFFEE_BOT_RUN)

    @property
    def last_run_time(self):
        if self.last_run:
            return datetime_from_string(self.last_run)
        return None

    def _update_last_run(self):
        self._update_datum(self.DATUM_LAST_COFFEE_BOT_RUN, now_string())

    @staticmethod
    def coffee_from_schedule(username, coffee_schedule):
        index = next(
            (
                pair
                for pair, tuple in enumerate(coffee_schedule)
                if tuple[0] == username or tuple[1] == username
            ),
            None,
        )
        if index is None:
            return None

        coffee_pair = coffee_schedule[index]
        if coffee_pair[0] == username:
            return coffee_pair[1]
        else:
            return coffee_pair[0]

    def history(self):
        try:
            return self._datum(self.DATUM_COFFEE_HISTORY)
        except KeyError:
            self._update_datum(self.DATUM_COFFEE_HISTORY, {})
            return self._datum(self.DATUM_COFFEE_HISTORY)

    def _update_coffee_history(self, user, pair):
        """
        Update the coffee history for the user - preserving the history order in the history (i.e., the current pair
        should always be the last entry).
        :param user:  The user to update the history for.
        :param pair:  The current pairing for that user.
        """
        history = self.history()

        if user not in history:
            history[user] = {}

        pair_count = history.get(user).get(pair, 0)
        if pair_count > 0:
            history.get(user).pop(pair)  # we want to re-add the user to preserve order

        history[user][pair] = pair_count + 1

    def history_for(self, user):
        try:
            return self._datum(self.DATUM_COFFEE_HISTORY)[user]
        except KeyError:
            return {}

    def _check_calendar(self, as_of):
        """
        Coffee Bot will generally just run on Sundays, unless it has been to recently run.

        :param as_of: for testing, mostly - check the calendar as of that date
        :return: True if we should run, False otherwise
        """
        if self.last_run is None:
            # If we've never been run, require a bit more manual intervention
            logging.warning(
                "Calendar Bot does not think it has been run before, so will not run automatically.  "
                "You will need to force a run."
            )
            return False

        min_days_since_last_run = 5
        if as_of is None:
            as_of = now()

        if as_of.weekday() == calendar.SUNDAY:
            if as_of - timedelta(days=min_days_since_last_run) > self.last_run_time:
                return True
            logging.warning(
                "Coffee bot was last run on %s, so will not run since that was less than %s days ago.  "
                "It will run automatically again next week.  "
                "You will need to force a run if you would like one sooner.",
                self.last_run,
                min_days_since_last_run,
            )

        logging.debug(
            "Coffee bot currently only runs on Sundays, so is still taking a nap!"
        )

        return False

    def should_generate_coffee(self, as_of=None):
        """
        Should we generate new coffees?
        :param as_of: As of a particular date - generally just for testing.
        """
        return not self.paused and (
            self._tell.has_tag(CoffeeBot.TAG_FORCE_COFFEE)
            or self._check_calendar(as_of)
            or self.current_schedule() is None
        )

    def lock_in_current_schedule(self, users):
        """
        "Lock in" the current set of coffee pairings - once this is run, the pairings are finalized and
        history has been written, so Coffee Bot considers them to have happened for the purposes of future
        scheduling.
        """
        pairings = {}
        for user in users:
            user.tell.clear_data(Socializer.SOURCE_ID)
            if user.username in self.current_scheduled_users():
                pair = self.coffee_with(user.username)
                user.tell.update_datum_from_source(
                    Socializer.SOURCE_ID, self.DATUM_CURRENT_COFFEE_PAIR, pair,
                )
                self.update_user_history_for(user.tell, user.username)
                self._update_coffee_history(user.username, pair)
                pairings[user.username] = pair
        return pairings

    def update_user_history_for(self, tell, username):
        """
        Update the User's coffee history on their Tell.
        TODO: this can be re-inlined after the migration
        """
        tell.update_datum_from_source(
            Socializer.SOURCE_ID, self.DATUM_COFFEE_HISTORY, self.history_for(username),
        )

    def _replace_schedule(self, current_schedule, people):
        self._update_datum(self.DATUM_CURRENT_COFFEE_SCHEDULE, current_schedule)
        self._update_datum(self.DATUM_LAST_SCHEDULE_CREATED, now_string())
        self._update_datum(self.DATUM_SCHEDULED_USERS, sorted(people))

    def update_schedule(self, people):
        """
        Generates a new Coffee schedule from the list of people, replacing the current one.
        """
        schedule = self._schedule_coffees(people)
        self._replace_schedule(schedule, people)

    def _schedule_coffees(self, people):
        """
        An attempt at a better algorithm if people are coming in and out of coffees.
        Turns out the original brute force one may actually be better though, particularly
        in the scenario where the group is relatively stable over time...
        """
        logging.info("Scheduling Coffees with Algo 2.")
        pairings = []

        shuffled_people = list(people)
        random.shuffle(
            shuffled_people
        )  # Ensure we don't have weird skews in scheduling based on names
        if len(shuffled_people) % 2:
            shuffled_people.append(CoffeeBot.BYE_WEEK_COFFEE)
        sorted_people = self.sorted_coffee_users(shuffled_people, self.history())

        for person in sorted_people:
            if person in shuffled_people and len(shuffled_people) > 1:
                shuffled_people.remove(person)
                pair = self._find_best_pair(self.history_for(person), shuffled_people)
                shuffled_people.remove(pair)
                pairings.append((person, pair))

        if len(shuffled_people) > 1:
            # Because I'm neurotic...
            logging.error(
                "Had more than one unpaired person - that really shouldn't be possible: %s",
                shuffled_people,
            )

        for bye in shuffled_people:
            pairings.append((bye, CoffeeBot.BYE_WEEK_COFFEE))

        return pairings

    # -- ALGO 2 ---
    @staticmethod
    def sorted_coffee_users(users, history):
        coffee_totals = {}
        for user in users:
            if user in history:
                coffee_totals[user] = -1 * (
                    sum(history[user].values())
                )  # want descending
            else:
                coffee_totals[user] = 0

        return sorted(coffee_totals, key=coffee_totals.get)

    @staticmethod
    def _find_best_pair(history, people):
        best_pair = people[0]
        for possible_pair in people:
            if possible_pair not in history:
                return possible_pair

            if history[possible_pair] < history[best_pair]:
                best_pair = possible_pair

        return best_pair
