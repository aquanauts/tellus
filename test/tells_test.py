# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests

import pytest

import tellus
import tellus.configuration
from tellus.configuration import (
    TELLUS_SAVE_FILE_NAME,
    TELLUS_INTERNAL,
    TELLUS_GO,
    TELLUS_LINK,
    TELLUS_USER,
)
from tellus.persistence import PickleFilePersistor
from tellus.tell import InvalidAliasException
from tellus.tell import Tell, InvalidTellUpdateException, SRC_TELLUS_USER
from tellus.tells import (
    Teller,
    DuplicateTellException,
    TheresNoTellingException,
)
from test.persistence_test import (
    create_current_save_file,
    TELLUS_PICKLE_SAVE_FILE_NO_HEADER,
)

TELLUS_TEST_USER = "test_user"  # For tests that need to test logging in


###
# Utility functions for creating Tellers and Tells
###


def create_test_teller(
    persistor=PickleFilePersistor(
        persist_root=None, save_file_name=TELLUS_SAVE_FILE_NAME, testing=True
    )
) -> Teller:
    """
    Creates a teller for test usage, to centralize handling of test persistence.
    Note that by default, this will create a Persistor that doesn't write to a file.
    If testing actual persistence, you'll need to pass an appropriate Persistor.
    """
    return Teller(persistor)


def create_tells_for_aliases(
    teller, alias_list, category=TELLUS_INTERNAL, test_name="some test"
):
    """
    Convenience testing method to just create a bunch of Tells for a list of Aliases because we do this a lot.
    :param teller: the teller to create the Tells in
    :param alias_list: a list of aliases
    :param category: a category for the Tells if it matters (defaults to TELLUS_INTERNAL)
    :param test_name: the name of the test if you want
    :return: a dict of all Tells created, by Alias in case you want to verify identity later
    """
    created_tells = {}
    for alias in alias_list:
        created_tells[alias] = teller.create_tell(alias, category, test_name)
    return created_tells


###
#  Teller Tests
###


def test_teller_basics():
    manager = create_test_teller()
    assert manager.tells_count() == 0

    try:
        manager.tells["boom"] = "anything"
        pytest.fail("tells should return an immutable tuple.")
    except Exception as exception:
        print(exception)


def test_create_tell():
    teller = create_test_teller()

    assert not teller.has_tell("tellus-test")

    tell = teller.create_tell("tellus test", TELLUS_INTERNAL, "tells_test")
    assert tell is not None
    assert tell.alias == "tellus-test"
    assert tell.go_url is None
    assert tell == teller.get("tellus-test")
    assert tell == teller.get("tellus test")
    assert tell == teller.get(
        "tellus_test"
    ), "Tells can be retrieved by a number of variant names..."
    assert tell == teller.get(
        "tellus+test"
    ), "Tells can be retrieved by a number of variant names..."
    assert tell == teller.get(
        "tellus?test"
    ), "Tells can be retrieved by a number of variant names..."
    assert teller.has_tell("tellus-test")
    assert teller.has_tell("tellus test"), "has_tell uses the same logic as get"

    tell = teller.create_tell("quislet", TELLUS_INTERNAL, "tells_test")
    assert tell is not None
    assert tell == teller.get("quislet")

    tell = teller.create_tell("Groot", TELLUS_INTERNAL, "tells_test")
    assert tell is not None
    assert tell.alias == "groot", "Tells should be saved as lowercase"
    assert tell == teller.get("GrOoT"), "Retrieving a tell should ignore case."

    try:
        teller.create_tell("tellus test", TELLUS_INTERNAL, "tells_test")
        pytest.fail("Should not be able to replace an existing Tell.")
    except DuplicateTellException as exception:
        print(exception)

    try:
        teller.create_tell("Tellus Test", TELLUS_INTERNAL, "tells_test")
        pytest.fail("Tell aliases should be case-insensitive.")
    except DuplicateTellException as exception:
        print(exception)

    try:
        teller.create_tell("Tellus_Test", TELLUS_INTERNAL, "tells_test")
        pytest.fail(
            "Tell aliases will be converted to their canonical form on creation."
        )
    except DuplicateTellException as exception:
        print(exception)

    try:
        teller.create_tell("Tellus+Test", TELLUS_INTERNAL, "tells_test")
        pytest.fail(
            "Tell aliases will be converted to their canonical form on creation."
        )
    except DuplicateTellException as exception:
        print(exception)


def test_tells():
    teller = create_test_teller()
    tellus = teller.create_tell("tellus", TELLUS_INTERNAL, "test_tells")
    cosmicboy = teller.create_tell("cosmicboy", TELLUS_INTERNAL, "test_tells")
    cosmicboy.add_category(TELLUS_USER)
    quislet = teller.create_tell("quislet", TELLUS_INTERNAL, "test_tells")
    groot = teller.create_tell("groot", TELLUS_USER, "test_tells")

    assert teller.tells(TELLUS_INTERNAL) == [cosmicboy, quislet, tellus]
    assert teller.tells(TELLUS_USER) == [cosmicboy, groot]
    assert teller.tells() == [cosmicboy, groot, quislet, tellus]


def test_create_go_tell():
    manager = create_test_teller()

    manager.create_tell("tellus", TELLUS_GO, "tells_test", url="http://tellus.github.com")
    tell = manager.get("tellus")
    assert tell is not None
    assert tell.go_url == "http://tellus.github.com"

    try:
        manager.create_tell("tellus", TELLUS_GO, "tells_test", url="bob")
        pytest.fail("Should not be able to replace an existing tellus go url.")
    except Exception as exception:
        print(exception)


def test_get_tell():
    teller = create_test_teller()
    unreal_tell = Tell(
        "tellus", TELLUS_INTERNAL
    )  # Creating a Tell does not make it real...

    try:
        teller.get("tellus")
        pytest.fail(
            "Getting a Tell that does not exist should raise a TheresNoTellingException."
        )
    except TheresNoTellingException as exception:
        pass

    tell = teller.create_tell("tellus", TELLUS_INTERNAL, "tells_test")
    assert teller.get("tellus") == tell
    assert teller.get("    tellus   ") == tell
    assert teller.get(" !!!   tellus   ???? ") == tell
    assert (
        teller.get(" @$#%)*#%   tellus   ???? ") == tell
    ), "Tellus will clean get requests..."


def test_get_or_create_tell():
    teller = create_test_teller()

    tell = teller.get_or_create_tell("tellus test", TELLUS_INTERNAL, "tells_test")
    assert tell is not None
    assert tell.alias == "tellus-test"
    assert tell.go_url is None
    assert tell == teller.get("tellus-test")
    assert not tell.in_category(tellus.configuration.TELLUS_GO)

    new_tell = teller.get_or_create_tell(
        "tellus test", tellus.configuration.TELLUS_GO, "tells_test"
    )
    assert tell == new_tell
    assert tell.in_category(tellus.configuration.TELLUS_GO)

    try:
        teller.get_or_create_tell(
            TELLUS_INTERNAL, TELLUS_GO, "test create reserved tell"
        )
        pytest.fail(
            "Attempting to get/create a non-existent Tell with a reserved name should throw an exception"
        )
    except InvalidAliasException:
        pass
    teller.create_tell(
        TELLUS_INTERNAL, TELLUS_INTERNAL, "Tellus is allowed to create this Tell"
    )
    teller.get_or_create_tell(TELLUS_INTERNAL, TELLUS_GO, "Now this should work")


def test_update_tell_from_ui(fs):
    # FS is required for the load later...
    teller = create_test_teller()

    try:
        teller.update_tell_from_ui({Tell.ALIAS: "nope"}, TELLUS_TEST_USER)
        pytest.fail(
            "Attempting to update a nonexistent Tell should throw an InvalidTellUpdateException"
        )
    except InvalidTellUpdateException:
        pass

    tell = teller.create_tell("tell-to-update", TELLUS_INTERNAL, "tells_test")
    try:
        teller.update_tell_from_ui({Tell.ALIAS: "update tell"}, TELLUS_TEST_USER)
        pytest.fail("Restrictive on updates, will only work with a fully clean alias.")
    except InvalidTellUpdateException:
        pass
    assert tell.audit_info.created_by == "tells_test"
    assert (
        tell.audit_info.last_modified_by == "tells_test"
    ), "Failed update should not have updated modified by."

    old_alias = "tell-to-update"
    params = {
        Tell.ALIAS: old_alias,
        Teller.NEW_ALIAS: old_alias,  # This should have no effect...
        Tell.DESCRIPTION: "Tell me.",
        Tell.GO_URL: "http://whathappenedaboutme.com",
        Tell.TAGS: "silly, fake, silly, tags, really",
        "not_an_attribute": "But should still get tacked on as data!",
    }
    assert teller.tells_count() == 1
    returned_tell = teller.update_tell_from_ui(params, TELLUS_TEST_USER)
    assert returned_tell == teller.get(old_alias), "Should return the updated Tell."
    assert returned_tell.alias == params[Tell.ALIAS]
    assert returned_tell.description == params[Tell.DESCRIPTION]
    assert returned_tell.go_url == params[Tell.GO_URL]
    assert returned_tell.tags == ["fake", "really", "silly", "tags"]
    assert returned_tell.get_data_dict() == {
        SRC_TELLUS_USER: {
            Tell.ALIAS: old_alias,
            Tell.DESCRIPTION: "Tell me.",
            Tell.GO_URL: "http://whathappenedaboutme.com",
            Tell._SRC_TAGS: "silly, fake, silly, tags, really",
            "not_an_attribute": "But should still get tacked on as data!",
        }
    }, "User Data is just like anything else for a Tell."
    assert tell.audit_info.created_by == "tells_test"
    assert (
        tell.audit_info.last_modified_by == TELLUS_TEST_USER
    ), "Now should show appropriate modified-by"

    new_alias_unclean = "tell updated"  # Note the space to verify weird alias behaviors
    new_alias = "tell-updated"
    params = {
        Tell.ALIAS: old_alias,
        Teller.NEW_ALIAS: new_alias_unclean,
        Tell.TAGS: "just, some, new, tags, really",
    }
    returned_tell = teller.update_tell_from_ui(
        params, TELLUS_TEST_USER, replace_tags=True
    )
    assert returned_tell == teller.get(
        new_alias
    ), "Should return the updated Tell by its new alias."
    assert not teller.has_tell(
        old_alias
    ), "The Tell with the old Alias should not exist"
    assert returned_tell.tags == [
        "just",
        "new",
        "really",
        "some",
        "tags",
    ], "Replacing tags should replace tags."
    assert returned_tell.get_data_dict() == {
        SRC_TELLUS_USER: {
            Tell.ALIAS: new_alias,
            Tell.DESCRIPTION: "Tell me.",
            Tell.GO_URL: "http://whathappenedaboutme.com",
            Tell._SRC_TAGS: "just, some, new, tags, really",
            "not_an_attribute": "But should still get tacked on as data!",
        }
    }

    params = {
        Tell.ALIAS: new_alias,
        Tell.TAGS: "also, , this should work",
    }
    returned_tell = teller.update_tell_from_ui(
        params, TELLUS_TEST_USER, replace_tags=True
    )
    assert returned_tell.tags == [
        "also",
        "should",
        "this",
        "work",
    ], "Blanks should be ignored (tbd re: tag format)."

    existing_tell = teller.create_tell(
        "new-new-alias",
        TELLUS_INTERNAL,
        "test_updates",
        description="Should prevent updating the Tell with a new alias",
    )
    params = {
        Tell.ALIAS: new_alias,
        Teller.NEW_ALIAS: "new-new-alias",
        Tell.DESCRIPTION: "Should blow up",
    }
    try:
        teller.update_tell_from_ui(params, TELLUS_TEST_USER, replace_tags=True)
        pytest.fail(
            "Attempting to update a Tell with an existing Tell's alias should throw an exception."
        )
    except InvalidTellUpdateException:
        assert (
            existing_tell.description
            == "Should prevent updating the Tell with a new alias"
        ), "Should not have updated the existing unrelated Tell"

    new_teller = create_test_teller()
    new_teller.load_tells()
    assert new_teller.tells_count() == 0, "The teller does not persist itself!"


def test_delete_tell():
    teller = create_test_teller()
    tell = teller.create_tell("tellus test", TELLUS_INTERNAL, "tells_test")
    assert tell == teller.get("tellus-test")

    try:
        teller.delete_tell("tellus test")
        pytest.fail("Deleting should only work on a fully clean alias.")
    except KeyError:
        pass

    try:
        teller.delete_tell("tellus_test")
        pytest.fail("Deleting should only work on a fully clean alias.")
    except KeyError:
        pass

    deleted_tell = teller.delete_tell("tellus-test")
    assert deleted_tell == tell
    assert teller.tells_count() == 0
    try:
        teller.delete_tell("tellus-test")
        pytest.fail("tellus-test should have been deleted.")
    except KeyError:
        pass


def test_parse_query_string():
    categories, tags = Teller.parse_query_string(None)
    assert len(categories) == 0, f"Shouldn't have any categories: {categories}"
    assert len(tags) == 0, f"Shouldn't have any tags: {tags}"

    categories, tags = Teller.parse_query_string("")
    assert len(categories) == 0, f"Shouldn't have any categories: {categories}"
    assert len(tags) == 0, f"Shouldn't have any tags: {tags}"

    categories, tags = Teller.parse_query_string(".......")
    assert len(categories) == 0, f"Shouldn't have any categories: {categories}"
    assert len(tags) == 0, f"Shouldn't have any tags: {tags}"

    categories, tags = Teller.parse_query_string(TELLUS_GO)
    assert list(categories) == [TELLUS_GO]
    assert list(tags) == []

    # THE FIRST ONE IS ALWAYS EXPECTED TO BE A CATEGORY - and will also be added to tags
    categories, tags = Teller.parse_query_string("go")
    assert list(categories) == [
        TELLUS_GO
    ], "The first query element is a special category element - can be unqualified."
    assert list(tags) == []

    categories, tags = Teller.parse_query_string("aq-link")
    assert list(categories) == [
        TELLUS_LINK
    ], "The first query element is a special category element - can be unqualified."
    assert list(tags) == []

    categories, tags = Teller.parse_query_string(".go")
    assert list(categories) == []
    assert list(tags) == [
        "go"
    ], "If you prefix with a . you should be into tags now with no special handling"

    categories, tags = Teller.parse_query_string(f"go.foo.bar.bar.baz.{TELLUS_LINK}")
    assert list(categories) == [
        TELLUS_LINK,
        TELLUS_GO,
    ], "Fully qualified categories later work."
    assert list(tags) == ["bar", "baz", "foo"]

    categories, tags = Teller.parse_query_string(f"aq-link.foo.bar.bar.baz.go")
    assert list(categories) == [
        TELLUS_LINK
    ], "But not fully qualified ones later are treated only as tags."
    assert list(tags) == ["bar", "baz", "foo", "go"]

    # Parsing will slugify anything that comes through into Tellus' canonical form
    categories, tags = Teller.parse_query_string(
        f"{TELLUS_GO}.i am not a valid tag.bar!!  .ba--z.{TELLUS_LINK}.also_underscores.also+plusses.tellus_internal"
    )
    assert list(categories) == [
        TELLUS_LINK,
        TELLUS_GO,
    ], "A non-canonical category will be treated just as a tag"
    assert list(tags) == [
        "also-plusses",
        "also-underscores",
        "ba--z",
        "bar",
        "i-am-not-a-valid-tag",
        "tellus-internal",
    ]


def test_query_links_and_tells():
    teller = create_test_teller()

    tell_quislet = teller.create_tell(
        "quislet", TELLUS_INTERNAL, "tells_test", url="quislet!"
    )
    tell_tellus = teller.create_tell(
        "tellus", TELLUS_GO, "tells_test", url="http://tellus.github.com"
    )
    tell_vfh = teller.create_tell(
        "vfh", TELLUS_GO, "tells_test", url="http://veryfinehat.com"
    )
    tell_quislet.add_tag("dc")
    tell_tellus.add_tags(["dc", "tellus", "tellus-test"])

    assert teller.query_tells() == {
        "quislet": "quislet!",
        "tellus": "http://tellus.github.com",
        "vfh": "http://veryfinehat.com",
    }

    assert teller.query_tells(TELLUS_INTERNAL) == {"quislet": "quislet!"}
    assert teller.query_tells(tellus.configuration.TELLUS_GO) == {
        "tellus": "http://tellus.github.com",
        "vfh": "http://veryfinehat.com",
    }

    assert teller.query_tells(".tellus") == {"tellus": "http://tellus.github.com"}
    assert teller.query_tells(".dc") == {
        "quislet": "quislet!",
        "tellus": "http://tellus.github.com",
    }

    # Now you're playing with queries
    assert teller.query_tells("...dc") == {
        "quislet": "quislet!",
        "tellus": "http://tellus.github.com",
    }, ".s are query separators"
    assert teller.query_tells(f"{TELLUS_GO}.dc") == {"tellus": "http://tellus.github.com"}

    assert (
        len(teller.query_tells(".")) == 3
    ), "A query that is just a separator should result in getting everything."
    assert teller.query_tells(".") == {
        "quislet": "quislet!",
        "tellus": "http://tellus.github.com",
        "vfh": "http://veryfinehat.com",
    }, "A query that is just a separator should result in getting everything."
    assert teller.query_tells(".......") == {
        "quislet": "quislet!",
        "tellus": "http://tellus.github.com",
        "vfh": "http://veryfinehat.com",
    }, "A query that is just a series of separators should result in getting everything."

    # Queries with more interesting tell names
    teller.create_tell(
        "marvel universe", TELLUS_GO, "tells_test", url="http://marvel.com"
    )

    teller.create_tell(
        "alias investigations",
        TELLUS_GO,
        "tells_test",
        url="http://alias-investigations",
    ).add_tags(["marvel", "marvel-universe"])

    assert teller.query_tells(".alias+investigations") == {
        "alias-investigations": "http://alias-investigations"
    }
    assert teller.query_tells("marvel_universe") == {
        "alias-investigations": "http://alias-investigations",
        "marvel-universe": "http://marvel.com",
    }
    assert teller.query_tells("marvel-universe") == {
        "alias-investigations": "http://alias-investigations",
        "marvel-universe": "http://marvel.com",
    }
    assert teller.query_tells("marvel universe") == {
        "alias-investigations": "http://alias-investigations",
        "marvel-universe": "http://marvel.com",
    }

    assert teller.query_tells("marvel universe", tell_repr_method="tellus_info") == {
        "alias-investigations": {},
        "marvel-universe": {},
    }

    # Note we are doing a bit of trickery to allow this to take properties as well
    assert teller.query_tells("marvel universe", tell_repr_method="alias") == {
        "alias-investigations": "alias-investigations",
        "marvel-universe": "marvel-universe",
    }


def test_get_categories():
    manager = create_test_teller()

    manager.create_tell("tellus", TELLUS_GO, "tells_test", url="http://tellus.github.com")
    manager.create_tell("vfh", TELLUS_GO, "tells_test", url="http://veryfinehat.com")
    manager.create_tell("quislet", TELLUS_INTERNAL, "tells_test", url="quislet!")

    assert manager.tells_count(TELLUS_INTERNAL) == 1
    assert manager.tells_count(tellus.configuration.TELLUS_GO) == 2


def test_load_with_no_file(fs):
    teller = create_test_teller()
    file = teller.persistence_file()

    assert teller.tells_count() == 0
    assert not file.exists()
    teller.load_tells()
    assert not file.exists()
    assert teller.tells_count() == 0


def test_persist_empty_tell_manager(fs):
    teller = create_test_teller()
    file = teller.persistence_file()

    assert not file.exists()
    teller.persist()
    assert file.exists()
    # This shouldn't happen in practice, but easy way to test loading and saving...
    new_manager = create_test_teller()
    new_manager.load_tells()
    assert new_manager.tells_count() == 0


def test_persist(fs):
    teller = create_test_teller()
    file = teller.persistence_file()

    teller.create_tell("tellus", TELLUS_GO, "tells_test", url="/tellus")
    teller.create_tell("vfh", TELLUS_GO, "tells_test", url="http://veryfinehat.com")

    assert not file.exists()
    teller.persist()
    assert file.exists()

    # This shouldn't happen in practice, but easy way to test loading and saving...
    new_teller = create_test_teller()
    assert new_teller.tells_count() == 0
    new_teller.load_tells()
    assert new_teller.tells_count() == 2
    assert new_teller.get("tellus").go_url == "/tellus"
    assert new_teller.get("vfh").go_url == "http://veryfinehat.com"

    new_teller.persist()
    new_teller.delete_tell("vfh")
    assert not new_teller.has_tell("vfh"), "Deleting should work"
    new_teller.load_tells()
    assert new_teller.has_tell(
        "vfh"
    ), "Deleting must be persisted outside of the teller."


def test_load(fs):
    teller = create_test_teller()
    file = teller.persistence_file()

    assert teller.tells_count() == 0
    fs.create_file(file, contents=create_current_save_file())
    teller.load_tells()
    assert teller.tells_count() == 3

    tell_tellus = teller.get("tellus")
    assert tell_tellus.alias == "tellus"
    assert tell_tellus.go_url == "/tellus"
    assert tell_tellus.categories == [tellus.configuration.TELLUS_GO]

    tell_tellus = teller.get("vfh")
    assert tell_tellus.go_url == "http://veryfinehat.com"
    assert tell_tellus.categories == [tellus.configuration.TELLUS_GO]


def test_old_pickle_load(fs):
    # tellus-task: this should be deprecated fairly quickly...
    teller = create_test_teller()
    file = teller.persistence_file()

    assert teller.tells_count() == 0
    fs.create_file(file, contents=TELLUS_PICKLE_SAVE_FILE_NO_HEADER)
    teller.load_tells()
    assert teller.tells_count() == 2

    tell_tellus = teller.get("tellus")
    assert tell_tellus.alias == "tellus"
    assert tell_tellus.go_url == "/tellus"
    assert tell_tellus.categories == [tellus.configuration.TELLUS_GO]

    tell_tellus = teller.get("vfh")
    assert tell_tellus.go_url == "http://veryfinehat.com"
    assert tell_tellus.categories == [tellus.configuration.TELLUS_GO]


SEARCH_TELL_ALIASES = [
    "strategic-improvements-board",
    "saturn_girl",
    "cosmic_boy",
    "lightning_lad",
    "the-big-board",
    # Add some chaff:
    "hoard",
    "research-board",
]


def create_search_tells(teller, test_name="some search test"):
    """
    Create a standard set of search Tells to test search functionality in various places.
    """
    return create_tells_for_aliases(teller, SEARCH_TELL_ALIASES, test_name=test_name,)


# A list of search terms for SEARCH_TELL_ALIASES
# and the Tells aliases they should be matching based on our current implementation.
# For use across different ways to access search, to help ensure consistency
SEARCH_TERM_MATCHES = {
    "strategicimprovementsboard": ["strategic-improvements-board"],
    "bigboard": ["the-big-board"],
    "saturngirl": ["saturn-girl"],
    "cosmic boy": ["cosmic-boy"],
    "lightning": ["lightning-lad"],
    "board": [
        "research-board",
        "strategic-improvements-board",
        "the-big-board",
        "hoard",
    ],
    # "sib": ["strategic-improvements-board",],
}


def test_search_tells_and_get_with_search():
    teller = create_test_teller()
    search_tells = create_search_tells(teller, "test_fuzzy_get")

    for alias in SEARCH_TELL_ALIASES:
        assert (
            teller.get(alias, True) == search_tells[alias]
        ), "Searching for an existing alias should ALWAYS just return that Tell, even with search on"

    for search_term in SEARCH_TERM_MATCHES.keys():
        results = teller.search_tells(search_term)
        expected_aliases = SEARCH_TERM_MATCHES[search_term]
        assert len(results) == len(
            expected_aliases
        ), f"Expected {expected_aliases} for {search_term} but received: {[tell.alias for tell in results]}"
        for tell in results:
            assert tell.alias in expected_aliases
        if len(SEARCH_TERM_MATCHES[search_term]) == 1:
            assert (
                teller.get(search_term, True).alias
                == SEARCH_TERM_MATCHES[search_term][0]
            )
