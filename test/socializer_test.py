# pylint: skip-file
import copy
import random

from tellus.configuration import TELLUS_INTERNAL
from tellus.tell import Tell, SRC_TELLUS_USER
from tellus.tellus_sources.socializer import Socializer, CoffeeBot
from tellus.tellus_utils import datetime_from_string
from tellus.users import UserManager
from test.tells_test import create_test_teller


def create_standard_source():
    teller = create_test_teller()
    users = ["quislet", "saturngirl", "cosmicboy", "lightninglad", "karatekid"]
    no_coffee_users = [
        "bouncingboy",
        "chameleonboy",
    ]  # These legionnaires are going to sit out our coffees for now
    user_manager = UserManager(teller, users + no_coffee_users)
    for username in users:
        user = user_manager.get_or_create_valid_user(username)
        user.tell.update_datum_from_source(
            Socializer.SOURCE_ID, CoffeeBot.DATUM_CURRENT_COFFEE_PAIR, "FAKE"
        )

    for username in no_coffee_users:
        user = user_manager.get_or_create_valid_user(username)
        user.tell.remove_tag(CoffeeBot.TAG_COFFEE_BOT)
        user.tell.update_datum_from_source(
            Socializer.SOURCE_ID, CoffeeBot.DATUM_CURRENT_COFFEE_PAIR, "FAKE"
        )

    socializer = Socializer(user_manager)

    return socializer, user_manager, users


def current_pair(username, teller):
    return teller.get(username).get_datum(
        Socializer.SOURCE_ID, CoffeeBot.DATUM_CURRENT_COFFEE_PAIR
    )


def history(username, teller):
    return teller.get(username).get_datum(
        Socializer.SOURCE_ID, CoffeeBot.DATUM_COFFEE_HISTORY
    )


async def test_load_source():
    socializer, user_manager, users = create_standard_source()
    teller = user_manager.teller
    bouncingboy = user_manager.get("bouncingboy")

    coffee_bot = socializer.coffee_bot()
    assert coffee_bot.last_run is None

    first_user = user_manager.get(users[0])
    assert first_user.tell.get_data(socializer.source_id) == {
        CoffeeBot.DATUM_CURRENT_COFFEE_PAIR: "FAKE"
    }
    assert bouncingboy.tell.get_data(socializer.source_id) == {
        CoffeeBot.DATUM_CURRENT_COFFEE_PAIR: "FAKE"
    }
    await socializer.load_source()
    assert first_user.tell.get_data(socializer.source_id) != {
        CoffeeBot.DATUM_CURRENT_COFFEE_PAIR: "FAKE"
    }, "load_source() should have updated the user's coffee pair."
    assert (
        bouncingboy.tell.get_datum(
            socializer.source_id, CoffeeBot.DATUM_CURRENT_COFFEE_PAIR
        )
        is None
    ), "load_source() should have removed Bouncing Boy's coffee pair."
    assert coffee_bot.last_run is not None
    previous_run = coffee_bot.last_run_time

    original_tell = teller.get(CoffeeBot.TELL_COFFEE_BOT)

    first_user.tell.update_datum_from_source(
        socializer.source_id, CoffeeBot.DATUM_CURRENT_COFFEE_PAIR, "FAKE2"
    )
    await socializer.load_source()
    assert (
        coffee_bot.last_run_time == previous_run
    ), "Did not force a run so should not have updated."
    assert original_tell == teller.get(
        CoffeeBot.TELL_COFFEE_BOT
    ), "Currently, we need to delete the schedule to cause it to run again..."
    assert first_user.tell.get_data(socializer.source_id) == {
        CoffeeBot.DATUM_COFFEE_HISTORY: {},
        CoffeeBot.DATUM_CURRENT_COFFEE_PAIR: "FAKE2",
    }, "load_source() will not update coffee pairs in this scenario."

    teller.delete_tell(CoffeeBot.TELL_COFFEE_BOT)
    await socializer.load_source()
    new_tell = teller.get(CoffeeBot.TELL_COFFEE_BOT)
    coffee_bot = socializer.coffee_bot()
    assert (
        original_tell != new_tell
    ), "Deleting the original schedule should result in a new schedule being generated on load."
    assert (
        original_tell.audit_info.created
        != teller.get(CoffeeBot.TELL_COFFEE_BOT).audit_info.created
    )
    assert coffee_bot.last_run is not None
    assert (
        coffee_bot.last_run_time > previous_run
    ), "New run should be more recent than previous."
    previous_run = coffee_bot.last_run_time

    quislet_history = copy.deepcopy(socializer.coffee_bot().history_for("quislet"))

    teller.get("bouncingboy").add_tag(CoffeeBot.TAG_COFFEE_BOT)
    await socializer.load_source()
    assert new_tell == teller.get(
        CoffeeBot.TELL_COFFEE_BOT
    ), "Adding a new user to the schedule should not have forced the schedule to be recreated..."
    assert quislet_history == socializer.coffee_bot().history_for(
        "quislet"
    ), "...and should not have changed the history."

    # Note we are explicitly doing this as if it was updated by a user - had an issue with this
    new_tell.update_datum_from_source(
        SRC_TELLUS_USER, Tell.TAGS, CoffeeBot.TAG_FORCE_COFFEE
    )

    schedule = socializer.coffee_bot().current_schedule()
    await socializer.load_source()
    assert not new_tell.has_tag(
        CoffeeBot.TAG_FORCE_COFFEE
    ), "Forcing a run should remove the force tag, even if the tag was put in by a different source (e.g., a user)"

    assert (
        not schedule == socializer.coffee_bot().current_schedule()
    ), "Should have a new schedule"
    assert (
        coffee_bot.last_run_time > previous_run
    ), "New run should be more recent than previous."


async def test_should_generate_coffee():
    socializer, user_manager, users = create_standard_source()

    bot = socializer.coffee_bot()
    assert bot.should_generate_coffee(), "By default, we should generate coffee."

    bot.pause()
    assert (
        not bot.should_generate_coffee()
    ), "We should not generate coffee when Paused."

    bot.force_run()
    assert (
        not bot.should_generate_coffee()
    ), "We should not generate coffee when Paused, even if forced."

    bot.pause(False)
    assert (
        bot.should_generate_coffee()
    ), "Unpausing should allow coffee to be generated."


async def test_calendar_scheduling():
    socializer, user_manager, users = create_standard_source()
    teller = user_manager.teller

    bot = socializer.coffee_bot()
    assert bot.should_generate_coffee(), "Just getting ourselves set up..."
    await socializer.load_source()
    assert not bot.should_generate_coffee(), "...and checking sanity..."

    last_run = datetime_from_string("2020-06-01")
    bot._tell.update_datum_from_source(
        Socializer.SOURCE_ID, CoffeeBot.DATUM_LAST_COFFEE_BOT_RUN, last_run.isoformat()
    )

    assert not bot.should_generate_coffee(
        datetime_from_string("2020-06-05")
    ), "Saturday"
    assert bot.should_generate_coffee(datetime_from_string("2020-06-07")), "Sunday"

    last_run = datetime_from_string("2020-06-05")
    bot._tell.update_datum_from_source(
        Socializer.SOURCE_ID, CoffeeBot.DATUM_LAST_COFFEE_BOT_RUN, last_run.isoformat()
    )

    assert not bot.should_generate_coffee(
        datetime_from_string("2020-06-05")
    ), "Saturday"
    assert not bot.should_generate_coffee(
        datetime_from_string("2020-06-07")
    ), "Sunday, but too recent prior run"
    assert bot.should_generate_coffee(
        datetime_from_string("2020-06-14")
    ), "Sunday, and far enough out it will run again"


async def test_should_generate_new_schedule():
    socializer, user_manager, users = create_standard_source()

    assert (
        socializer.should_generate_new_coffee_schedule()
    ), "Should always generate a new schedule before we've ever run."

    await socializer.load_source()
    coffee_tell = user_manager.teller.get(CoffeeBot.TELL_COFFEE_BOT)
    assert (
        not socializer.should_generate_new_coffee_schedule()
    ), "Should not generate a new schedule if we've got one."

    coffee_tell.add_tag(CoffeeBot.TAG_FORCE_COFFEE)
    assert (
        socializer.should_generate_new_coffee_schedule()
    ), "Should generate a new schedule if the bot says to force one."
    await socializer.load_source()
    assert not coffee_tell.has_tag(
        CoffeeBot.TAG_FORCE_COFFEE
    ), "Forcing a run should remove the force tag"
    assert (
        not socializer.should_generate_new_coffee_schedule()
    ), "And we should be back to not generating a schedule."


def test_coffee_for():
    schedule = [("quislet", "saturngirl"), ("lightninglad", "cosmicboy")]

    assert CoffeeBot.coffee_from_schedule("quislet", schedule) == "saturngirl"
    assert CoffeeBot.coffee_from_schedule("saturngirl", schedule) == "quislet"
    assert CoffeeBot.coffee_from_schedule("lightninglad", schedule) == "cosmicboy"
    assert CoffeeBot.coffee_from_schedule("cosmicboy", schedule) == "lightninglad"
    assert (
        CoffeeBot.coffee_from_schedule("mattereaterlad", schedule) is None
    ), "Matter Eater Lad should be lonely."


async def test_coffee_scheduler_2():
    socializer, user_manager, users = create_standard_source()
    teller = user_manager.teller

    # A little hackery to get into the state we want...
    bot_tell = teller.create_tell(
        CoffeeBot.TELL_COFFEE_BOT, TELLUS_INTERNAL, "test_new_coffee_scheduler"
    )
    bot = socializer.coffee_bot()
    history = {
        "quislet": {"saturngirl": 1, "cosmicboy": 1, "lightninglad": 1},
        "lightninglad": {"saturngirl": 1, "cosmicboy": 1},
    }
    bot_tell.update_datum_from_source(
        socializer.source_id, CoffeeBot.DATUM_COFFEE_HISTORY, history
    )
    assert bot.history_for("quislet") == history["quislet"], "Just to check..."
    assert (
        bot.history_for("lightninglad") == history["lightninglad"]
    ), "Just to check..."

    assert bot.should_generate_coffee()
    await socializer.load_source()
    assert (
        bot.coffee_with("quislet") == "karatekid"
    ), "With the current history, Karate Kid should always be next for Quislet"

    assert history == bot.history()


async def test_ordered_history():
    socializer, user_manager, users = create_standard_source()
    teller = user_manager.teller

    # "quislet", "saturngirl", "cosmicboy", "lightninglad", "karatekid"
    # A little hackery to get into the state we want...
    bot_tell = teller.create_tell(
        CoffeeBot.TELL_COFFEE_BOT, TELLUS_INTERNAL, "test_new_coffee_scheduler"
    )
    bot = socializer.coffee_bot()
    pair_counts = {
        "quislet": {
            "saturngirl": 1,
            "cosmicboy": 1,
            "lightninglad": 1,
            "karatekid": 1,
            "BYEWEEK": 1,
        },
        "lightninglad": {
            "saturngirl": 1,
            "cosmicboy": 1,
            "karatekid": 1,
            "quislet": 1,
            "BYEWEEK": 1,
        },
        "saturngirl": {
            "cosmicboy": 1,
            "lightninglad": 1,
            "karatekid": 1,
            "quislet": 1,
            "BYEWEEK": 1,
        },
        "cosmicboy": {
            "saturngirl": 1,
            "lightninglad": 1,
            "karatekid": 1,
            "quislet": 1,
            "BYEWEEK": 1,
        },
        "karatekid": {
            "saturngirl": 1,
            "cosmicboy": 1,
            "lightninglad": 1,
            "quislet": 1,
            "BYEWEEK": 1,
        },
    }
    bot_tell.update_datum_from_source(
        socializer.source_id, CoffeeBot.DATUM_COFFEE_HISTORY, pair_counts
    )
    assert bot.history_for("quislet") == pair_counts["quislet"], "Spot check..."
    assert (
        bot.history_for("lightninglad") == pair_counts["lightninglad"]
    ), "Spot check..."

    for i in range(10):
        bot.force_run()
        assert bot.should_generate_coffee()
        await socializer.load_source()
        new_history = bot.history()

        for user, pair_counts in new_history.items():
            assert current_pair(user, teller) == list(pair_counts.keys())[-1]
            assert history(user, teller) == bot.history_for(user)
            for pair, count in pair_counts.items():
                if pair != CoffeeBot.BYE_WEEK_COFFEE:
                    assert new_history[user].get(pair) == new_history[pair].get(user), (
                        f"Users and their pairs should always have the same count, "
                        f"but {user} and {pair} do not match: {new_history}"
                    )


def test_find_best_pair():
    history = {
        "quislet": {"saturngirl": 1, "cosmicboy": 1, "lightninglad": 1},
        "lightninglad": {"saturngirl": 1, "cosmicboy": 1, "karatekid": 1},
        "saturngirl": {"quislet": 1, "cosmicboy": 3, "karatekid": 2, "lightninglad": 2},
    }  # this is, of course, impossible

    assert (
        CoffeeBot._find_best_pair(
            history["quislet"], ["saturngirl", "cosmicboy", "lightninglad", "karatekid"]
        )
        == "karatekid"
    ), "Quislet should always be paired with Karate Kid given the history"
    assert (
        CoffeeBot._find_best_pair(
            history["lightninglad"], ["saturngirl", "cosmicboy", "quislet", "karatekid"]
        )
        == "quislet"
    ), "Lightning Lad should always be paired with Quislet given the history"
    assert (
        CoffeeBot._find_best_pair(
            history["saturngirl"], ["quislet", "cosmicboy", "lightninglad", "karatekid"]
        )
        == "quislet"
    ), "Saturn girl should always be paired with Quislet given the history"

    assert (
        CoffeeBot._find_best_pair(
            history["saturngirl"],
            ["cosmicboy", "lightninglad", "karatekid", "wildfire"],
        )
        == "wildfire"
    ), "Wildfire should always be the best pair given the history"

    assert CoffeeBot._find_best_pair(
        history["quislet"], ["cosmicboy", "lightninglad", "karatekid", "wildfire"]
    ) in [
        "wildfire",
        "karatekid",
    ], "Wildfire or Karate Kid should always be the best pair given the history"


def test_sorted_coffee_users():
    users = ["quislet", "saturngirl", "cosmicboy", "lightninglad", "karatekid"]
    random.shuffle(users)  # just to check myself
    history = {
        "quislet": {"saturngirl": 1, "cosmicboy": 1, "lightninglad": 1},
        "lightninglad": {"saturngirl": 1, "cosmicboy": 9, "karatekid": 1},
        "saturngirl": {"cosmicboy": 1, "karatekid": 1},
        "karatekid": {"quislet": 4},
    }

    assert CoffeeBot.sorted_coffee_users(users, history) == [
        "lightninglad",
        "karatekid",
        "quislet",
        "saturngirl",
        "cosmicboy",
    ]


async def s_test_iterations(fs):
    # Using this occasionally to eyeball how the algorithm does over time
    # It should generate a roughly balanced set of coffees
    # It...mostly works?
    socializer, user_manager, users = create_standard_source()

    enabled_users = socializer.determine_coffee_bot_users()
    bot = socializer.coffee_bot()
    history_history = ""
    run_assertions = (
        True  # To turn on the inconsistent assertions when I want to test them
    )
    bot.set_algo(CoffeeBot.TAG_ALGO_1)

    cycles = 100
    for cycle in range(1, cycles):
        for week in range(0, len(enabled_users)):
            await socializer.load_source()
            bot.force_run()
            history_history += f"{cycle}: {bot.history()}\n"

        if run_assertions:
            for user in enabled_users:
                history = bot.history_for(user)

                # These assertions are true a lot of the time but not always - there is some probability involved,
                # depending on which algo I'm using.
                # So this will fail inconsistently, hence not a safe unit test.
                assert len(history) == len(
                    enabled_users
                ), f"{cycle}: {user} should have had coffee with each user once after a cycle: {history}"
                if cycle < 50:
                    # This is only true till we add in the newcomers
                    assert (
                        count == cycle for count in history.values()
                    ), f"{user} should have had {cycle} coffees with each user: {history}"

        if cycle == cycles / 2:  # Halfway through, we add a couple of users
            history_history += f"CYCLE {cycle}: Adding users\n"
            user_manager.get("bouncingboy").tell.add_tag(CoffeeBot.TAG_COFFEE_BOT)
            user_manager.get("chameleonboy").tell.add_tag(CoffeeBot.TAG_COFFEE_BOT)
            enabled_users = socializer.determine_coffee_bot_users()

    print(history_history)
    bot.print_history()


#####
# Prior Algo
#
# I'm being a little overly careful here because figuring out an algo that worked was...not as easy as it sounds.
# So while I am trying to simplify Coffee bot, I am putting the original algo here for safekeeping.
#
# This is deprecated, and can be deleted once we have backed in without this algo as a safety net for a while.
#
#####

# @pytest.mark.skip(
#     reason="We are currently using Algo 2, and this test has a low probability intermittent failure."
# )
def old_test_coffee_scheduler_1(fs):
    socializer, user_manager, users = create_standard_source()
    enabled_users = socializer.determine_coffee_bot_users()
    coffee_bot = socializer.coffee_bot()
    coffee_bot.set_algo(CoffeeBot.TAG_ALGO_1)

    socializer.make_coffee_schedule()
    current_schedule = coffee_bot.current_schedule()
    assert current_schedule is not None
    people_scheduled = coffee_bot.current_scheduled_users()
    assert people_scheduled == sorted(enabled_users)

    assert coffee_bot.history() == {}
    socializer.lock_in_coffee_schedule()
    coffee_history = coffee_bot.history()
    assert len(coffee_history) == len(enabled_users)

    for user in enabled_users:
        user_history = coffee_bot.history_for(user)
        assert len(user_history) == 1, "Should have only had one coffee"
        assert (
            next(iter(user_history.values())) == 1
        ), "Should have had one coffee with that person"

    for week in range(1, len(enabled_users)):
        coffee_bot.update_schedule(enabled_users)
        socializer.lock_in_coffee_schedule()
        assert current_schedule != coffee_bot.current_schedule()

    for user in enabled_users:
        user_history = coffee_bot.history_for(user)
        assert len(user_history) == len(
            enabled_users
        ), "Every user should have had coffee with the other scheduled users"
        for value in user_history.values():
            assert (
                value == 1
            ), "Everyone should have just had one coffee with each other user..."

    # Let's roll along!
    for cycle in range(2, 10):
        for week in range(0, len(enabled_users)):
            coffee_bot.update_schedule(enabled_users)
            socializer.lock_in_coffee_schedule()
            # This assertion will very occasionally result in an intermittent failure - not currently worth debugging.
            assert current_schedule != coffee_bot.current_schedule()

        for user in enabled_users:
            user_history = coffee_bot.history_for(user)
            assert len(user_history) == len(
                enabled_users
            ), "Every user should have had coffee with the other scheduled users"
            for value in user_history.values():
                assert (
                    value == cycle
                ), "Everyone should have had two coffees with each other user..."

    bouncingboy = user_manager.get("bouncingboy")
    bouncingboy.tell.add_tag(CoffeeBot.TAG_COFFEE_BOT)
    enabled_users = socializer.determine_coffee_bot_users()
    assert bouncingboy.username in enabled_users

    coffee_bot.update_schedule(enabled_users)
    socializer.lock_in_coffee_schedule()
    bb_history = coffee_bot.history_for(bouncingboy.username)
    assert len(bb_history) == 1, "Bouncing Boy should have had one coffee"
    assert (
        next(iter(bb_history.values())) == 1
    ), "Should have had one coffee with that person"


# -- ALGO 1 ---
def _schedule_coffees_1(people, sets=None):
    """
    Schedules coffee pairings for a group of people.  Created from various "round robin tournament" algorithms.

    :param people: a group of people to schedule for coffees (if you want it to be random, do externally)
    :param sets: the number of sets of coffee to calculate (defaults to people - 1)
    :return: a list of coffee pairing tuples
    """
    # logging.info("Scheduling Coffees with Algo 1.")
    if len(people) % 2:
        people = list(people)
        people.append(CoffeeBot.BYE_WEEK_COFFEE)

    count = len(people)
    sets = sets or (count - 1)
    half = int(count / 2)
    schedule = []
    for turn in range(sets):
        left = people[:half]
        right = people[count - half - 1 + 1 :][::-1]
        pairings = zip(left, right)
        if turn % 2 == 1:
            pairings = [(y, x) for (x, y) in pairings]
        else:
            pairings = [
                (x, y) for (x, y) in pairings
            ]  # quick way to extract the tuples
        people.insert(1, people.pop())
        schedule.append(pairings)

    return schedule
