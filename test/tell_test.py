import string
from json import JSONDecodeError

import pytest
from sortedcontainers import SortedSet

import tellus
import tellus.configuration
from tellus.persistable import UNKNOWN_USER
from tellus.sources import SRC_UNSPECIFIED
from tellus.tell import (
    Tell,
    InvalidTellUpdateException,
    InvalidAliasException,
    InvalidTagException,
    SRC_TELLUS_USER,
)
from tellus.configuration import (
    TELLUS_INTERNAL,
    TELLUS_TESTING,
    TELLUS_GO,
    TELLUS_LINK,
    TELLUS_DNS,
    TELLUS_DNS_OTHER,
    TELLUS_USER_MODIFIED,
    TELLUS_CATEGORIES,
    EDITABLE_CATEGORIES,
)
from tellus.wiring import SESSION_TELLUS_USER, RESERVED_UI_WORDS
from tellus.tellus_utils import now, now_string


# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests


def test_valid_category():
    assert Tell.valid_category(TELLUS_GO), "TELLUS_GO should be a valid category."
    for category in TELLUS_CATEGORIES:
        assert Tell.valid_category(category), f"{category} should be a valid category."

    assert not Tell.valid_category("go")
    assert Tell.valid_category(Tell.ensure_category_prefix(TELLUS_GO))
    assert Tell.valid_category(Tell.ensure_category_prefix("go"))


def test_new_minimal_tell():
    tell = Tell(alias="tellus", category=TELLUS_TESTING)
    assert tell.alias == "tellus"
    assert tell.has_no_properties()
    assert tell.categories == [TELLUS_TESTING]
    assert tell.go_url is None
    assert tell.description is None
    assert tell.tags == []
    assert tell.groups == []
    assert tell.audit_info.created_by == UNKNOWN_USER
    assert tell.audit_info.last_modified_by == UNKNOWN_USER


def test_groups():
    dray = Tell("dray", TELLUS_TESTING)
    assert len(dray.groups) == 0, "By default, a Tell is not in a group"

    dray.add_tags(["dray", "drayify", "bard", "dray-stuff"])
    assert dray.groups == [], "Adding its own alias as a tag does not make it a group."

    assert dray.groups == []

    foo = Tell("foo", TELLUS_TESTING)
    foo.create_group()
    assert foo.groups == ["foo"]
    assert foo.tags == [
        "foo"
    ], "Using a tell to create a group also adds the group tag."
    foo.add_to_tell_group(dray)
    assert foo.groups == ["foo", "dray"]
    assert foo.tags == ["foo", "dray"]
    assert not dray.has_tag("foo")
    assert not dray.in_group("foo")

    this = Tell("this", TELLUS_TESTING)
    that = Tell("that", TELLUS_TESTING)
    this.add_to_tell_group(that)
    assert this.in_group(that.alias)
    assert that.in_group(
        that.alias
    ), "If you add a Tell to anothers group, it should create the group"
    assert not this.in_group(this.alias)


def create_maximal_tell():
    tell = Tell(
        alias="tellus",
        category=TELLUS_TESTING,
        go_url="/tellus",
        created_by=SESSION_TELLUS_USER,
        description="I am Tellus.",
    )
    tell.add_tags(["tellus", "test", "apples"])
    tell.update_datum_from_source(
        source_id=SRC_UNSPECIFIED, key="randomdata", value="I am some random data"
    )
    tell.create_group()
    return tell


def test_new_maximal_tell():
    tell = create_maximal_tell()

    assert tell.alias == "tellus"
    assert tell.go_url == "/tellus"
    assert tell.categories == [tellus.configuration.TELLUS_TESTING]
    assert tell.tags == ["apples", "tellus", "test"]
    assert tell.description == "I am Tellus."
    assert (
        tell.get_data_dict()
        == {
            SRC_UNSPECIFIED: {"randomdata": "I am some random data"},
            TELLUS_TESTING: {"description": "I am Tellus.", "go_url": "/tellus",},
        }
        != {"tellus-src-unspecified": {"randomdata": "I am some random data"}}
    )
    assert tell.groups == ["tellus"]
    assert tell.audit_info.created_by == SESSION_TELLUS_USER
    assert tell.audit_info.last_modified_by == SRC_UNSPECIFIED


def should_except_creating_tell(
    string,
    message,
    expected_exception=InvalidAliasException,
    tags_too=False,
    category=TELLUS_GO,
):
    try:
        Tell(alias=string, category=category)
        pytest.fail(message)
    except expected_exception:
        pass

    if tags_too:
        tell = Tell(alias="test-tags", category=category)
        try:
            tell.add_tag(string)
            pytest.fail(message + " (Should also be true for tags).")
        except InvalidTagException:
            pass

    return True


def test_tell_aliases():
    should_except_creating_tell(
        None, "Creating a tell with No alias should throw an Exception."
    )
    should_except_creating_tell(
        "     ", "Creating a Tell with a blank alias should result in an exception."
    )
    should_except_creating_tell(
        "   z   ",
        "Creating a Tell with a single character alias should result in an exception.",
    )
    for letter in string.ascii_letters:
        should_except_creating_tell(
            letter,
            "Creating any Tell with any single character alias should result in an exception.",
        )

        assert Tell.is_slug_reserved(f"{letter}-anything")
        should_except_creating_tell(
            f"{letter}-anything",
            "Creating any Tell with an alias that *starts* with a single letter should fail.",
        )
        assert not Tell.is_slug_reserved(
            f"{letter}-anything", category_override=TELLUS_INTERNAL
        )
        Tell(
            f"{letter}-anything", category=TELLUS_INTERNAL
        )  # Unless it is in the TELLUS_INTERNAL category...

    assert set(RESERVED_UI_WORDS).issubset(Tell.RESERVED_ALIASES), "Just a safety check"

    for reserved in Tell.RESERVED_ALIASES:
        assert Tell.is_slug_reserved(reserved)
        should_except_creating_tell(
            reserved,
            f"Any string in the reserved aliases should generate an exception, but {reserved} did not.  "
            "Mostly these will be Tellus categories and Tell properties.",
        )
        assert not Tell.is_slug_reserved(reserved, category_override=TELLUS_INTERNAL)
        try:
            Tell(
                reserved, category=TELLUS_INTERNAL
            )  # Unless it is in the TELLUS_INTERNAL category...
        except Exception as e:
            pytest.fail(f"{reserved} failed with exception: {repr(e)}")

    # Some tests to indicate what happens with certain aliases...
    assert Tell(alias="  ah   ", category=TELLUS_TESTING).alias == "ah"
    assert Tell("valid-alias", TELLUS_TESTING).alias == "valid-alias"
    assert (
        Tell("replace   whitespace    with dashes   ", TELLUS_TESTING).alias
        == "replace-whitespace-with-dashes"
    )
    assert (
        Tell("strip    non-word characters !%@", TELLUS_TESTING).alias
        == "strip-non-word-characters"
    )
    assert Tell("numb3rs 4r3 0k", TELLUS_TESTING).alias == "numb3rs-4r3-0k"
    assert Tell("NO YELLING!!!", TELLUS_TESTING).alias == "no-yelling"
    assert Tell("no+plusses", TELLUS_TESTING).alias == "no-plusses"
    assert Tell("no_underscores", TELLUS_TESTING).alias == "no-underscores"


def test_alt_and_derived_aliases():
    alias = "main-tell-alias"

    tell = Tell(alias=alias, category=TELLUS_TESTING)
    derived_aliases = tell.derived_aliases()
    # assert "maintellalias" in derived_aliases
    # assert "main_tell_alias" in derived_aliases


def set_go_url(tell, value):
    """
    Convenience method to set this attribute quickly...
    """
    tell._update_property(Tell.GO_URL, value, False)


# Some Categories of Tells have idiosyncratic behavior, documented and tested here...
def test_specific_tell_categories():
    # AQ Links
    tell = Tell("dns-link", TELLUS_LINK)
    assert (
        tell.go_url == "http://dns-link.github.com"
    ), "A DNS Link gets an github.com address if none is specified."
    set_go_url(tell, "something")
    assert tell.go_url == "something", "The URL of a DNS link can be overridden."
    set_go_url(tell, "")
    assert (
        tell.go_url == "http://dns-link.github.com"
    ), "Setting a DNS Link URL back to blank puts it back to github.com."
    set_go_url(tell, None)
    assert (
        tell.go_url == "http://dns-link.github.com"
    ), "Setting a DNS Link URL to None also puts it back to github.com."

    # DNS Other are read-only
    tell = Tell("dns-other", TELLUS_DNS_OTHER)
    assert tell.read_only, f"{TELLUS_DNS_OTHER} Tells are read only in the UI."


def test_read_only_tells():
    for category in TELLUS_CATEGORIES:
        tell = Tell(f"category-{category}", category)
        if category not in EDITABLE_CATEGORIES:
            assert tell.read_only
            tell.make_user_modified()
            assert (
                not tell.read_only
            ), "Once a tell is modified by a user, it becomes not read only."
        else:
            assert not tell.read_only


def test_tell_to_from_json():
    tell = create_maximal_tell()
    tell_json = tell.to_json_pickle()
    new_tell = Tell.from_json_pickle(tell_json)

    assert new_tell.alias == tell.alias
    assert new_tell.go_url == tell.go_url
    assert new_tell.categories == tell.categories
    assert new_tell.tags == tell.tags
    assert new_tell.description == tell.description
    assert new_tell.get_data_dict() == tell.get_data_dict()
    assert new_tell.groups == tell.groups
    assert new_tell.audit_info == tell.audit_info

    try:
        Tell.from_json_pickle("This should blow up")
        pytest.fail("Should have thrown a JSONDecodeError on an invalid dict.")
    except JSONDecodeError as exception:
        print(exception)

    tell = Tell(
        alias="tellus", category=tellus.configuration.TELLUS_TESTING, go_url="/tellus"
    )
    tell.add_category(tellus.configuration.TELLUS_GO)
    # If this breaks, the save file may also break...
    tell_from_string = Tell.from_json_pickle(
        '{"_alias": "tellus", "_categories": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, '
        '{"py/tuple": [{"py/set": ["tellus-go", "tellus-unit-testing-only"]}, null]}]}, "_go_url": "/tellus", '
        '"_tags": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": []}, '
        'null]}]}, "py/object": "tellus.tells.Tell"}'
    )
    modified = now()
    assert tell_from_string.alias == tell.alias
    assert tell_from_string.go_url == tell.go_url
    assert tell_from_string.categories == tell.categories
    # THE FOLLOWING IS INTENTIONALLY MISSING FROM THE ABOVE STRING to test changes to Tells from saved file
    assert tell_from_string.get_data_dict() == {}  # should be empty, but not blow up
    assert tell_from_string.audit_info is not None
    assert (
        tell_from_string.audit_info.created_by == UNKNOWN_USER
    ), "Tells deserialized without audit info will default in the Unknown User"
    assert (
        tell_from_string.audit_info.last_modified_by == UNKNOWN_USER
    ), "Tells deserialized without audit info will default in the Unknown User"
    assert (
        tell_from_string.audit_info.last_modified == tell_from_string.audit_info.created
    )
    assert tell_from_string.audit_info.seconds_since_last_modified(modified) == 0


def test_tell_to_simple_and_minimal_json():
    tell = Tell(
        alias="tellus", category=tellus.configuration.TELLUS_INTERNAL, go_url="/tellus"
    )
    tell.add_category(tellus.configuration.TELLUS_GO)
    tell.add_tag("tellus")
    tell.add_tag("test")
    tell.create_group()
    tell_json = tell.to_simple_json()

    assert (
        tell_json
        == '{"alias": "tellus", "go_url": "/tellus", "description": null, "categories": ["tellus-go", "tellus-internal"], '
        '"tags": ["tellus", "test"], "groups": ["tellus"], "data": {"tellus-internal": {"go_url": "/tellus"}}, '
        '"read-only": false, "z-audit-info": ' + tell.audit_info.to_simple_json() + "}"
    )

    assert (
        '{"alias": "tellus", "go_url": "/tellus", "description": null, "categories": ["tellus-go", "tellus-internal"], '
        '"tags": ["tellus", "test"]}' == tell.to_simple_json(minimal=True)
    )

    tell = Tell(alias="decider", category=tellus.configuration.TELLUS_LINK)
    tell.add_category(tellus.configuration.TELLUS_GO)
    tell.add_tag("decider")
    tell.add_tag("test")
    tell_json = tell.to_simple_json()

    assert (
        '{"alias": "decider", "go_url": "http://decider.github.com", "description": null, "categories": ["tellus-aq-link", "tellus-go"], '
        '"tags": ["decider", "test"], "groups": [], "data": {}, "read-only": false, "z-audit-info": '
        + tell.audit_info.to_simple_json()
        + "}"
        == tell_json
    )

    assert (
        '{"alias": "decider", "go_url": "http://decider.github.com", "description": null, "categories": ["tellus-aq-link", "tellus-go"], '
        '"tags": ["decider", "test"]}' == tell.to_simple_json(minimal=True)
    )


def test_go_url():
    tell = Tell("tellus", TELLUS_TESTING)
    assert tell.go_url is None

    set_go_url(tell, "http://tellus.github.com")
    assert tell.go_url == "http://tellus.github.com"
    assert tell.go_json() == '{"tellus": "http://tellus.github.com"}'


def test_internal_url():
    tell = Tell("tellus", tellus.configuration.TELLUS_LINK)
    assert tell.internal_url == "http://tellus.github.com"
    assert (
        tell.go_url == "http://tellus.github.com"
    ), "DNS Go URL should default to internal link."

    set_go_url(tell, "/tellus")
    assert (
        tell.go_url == "/tellus"
    ), "If you there is an URL, it will return the new one."

    tell = Tell("Is possible link", tellus.configuration.TELLUS_DNS)
    assert (
        tell.internal_url == "http://is-possible-link.github.com"
    ), "Returns a URL for something that *might* be a link."

    tell = Tell(
        "Cannot be a link (as far as we know)", tellus.configuration.TELLUS_DNS_OTHER
    )
    assert tell.internal_url is None, "DNS_OTHER Tells are assumed to be non-links"


def test_string_to_tags():
    tags = Tell.string_to_tags(
        "tellus, tell, us, tellus, spaces do    ,   .   what  ?, camelCaseNo?, Z0MGC4T$!!"
    )
    assert tags == SortedSet(
        ["tellus", "tell", "us", "spaces", "do", "what", "camelcaseno", "z0mgc4t"]
    )


def test_tags():
    tell = Tell("tellus", TELLUS_TESTING)
    assert len(tell.tags) == 0

    assert tell.has_tag("tellus", include_alias=True), "Alias is considered a tag"
    assert tell.has_tag("tellus"), "...by default"
    assert not tell.has_tag(
        "tellus", include_alias=False
    ), "Alias is usually also considered a tag, but can be excluded"

    tell.add_tag("yellow")
    tell.add_tag("purple")
    tell.add_tag("quislet")
    tell.add_tag("purple")

    assert len(tell.tags) == 3
    assert ["purple", "quislet", "yellow"] == tell.tags

    assert tell.has_tag("quislet")
    assert tell.has_all_tags(["quislet", "purple"])

    # Tellus has OPINIONS about valid tags...
    tell.add_tag("I-AM   a TaG YO!!!?!")
    assert tell.has_tag("i-am-a-tag-yo")
    tell.add_tag("iYamWhatIYam")
    assert tell.has_tag("iyamwhatiyam")
    tell.add_tag("i_am_a+yam")
    assert tell.has_tag("i-am-a-yam")

    response = tell.remove_tag("iyamwhatiyam")
    assert not tell.has_tag("iyamwhatiyam")
    assert (
        response == "iyamwhatiyam"
    ), "Removing a tag returns the tag removed if successful."

    response = tell.remove_tag("I-AM   a TaG YO!!!?!")
    assert tell.has_tag(
        "i-am-a-tag-yo"
    ), "Tags can only be removed explicitly (will not clean)"
    assert response is None, "Removing a tag returns None if unsuccessful."

    # Test tags with coalesce...which got all weird...
    assert ["i-am-a-tag-yo", "i-am-a-yam", "purple", "quislet", "yellow"] == tell.tags
    tell.update_datum_from_source(SRC_TELLUS_USER, Tell.TAGS, "user-tag-1,user-tag-2")
    assert [
        "i-am-a-tag-yo",
        "i-am-a-yam",
        "purple",
        "quislet",
        "user-tag-1",
        "user-tag-2",
        "yellow",
    ] == tell.tags
    tell.remove_tag("user-tag-1")
    assert [
        "i-am-a-tag-yo",
        "i-am-a-yam",
        "purple",
        "quislet",
        "user-tag-2",
        "yellow",
    ] == tell.tags
    tell.coalesce()
    assert [
        "i-am-a-tag-yo",
        "i-am-a-yam",
        "purple",
        "quislet",
        "user-tag-2",
        "yellow",
    ] == tell.tags, "oops."


def test_categories():
    tell = Tell("tellus", TELLUS_TESTING)
    assert len(tell.categories) == 1
    try:
        tell.add_category("tellus internal")
        pytest.fail("Adding a non-verified category should throw an exception.")
        # Of note:  Categories are not slugified like tags - the idea here is that categories are really internal use
        # only, so if we get a weird one we should really blow up
    except Exception as exception:
        assert len(tell.categories) == 1
        print(exception)

    assert not tell.in_category(tellus.configuration.TELLUS_LINK)
    tell.add_category(tellus.configuration.TELLUS_LINK)
    tell.remove_category(TELLUS_TESTING)
    assert tell.in_category(tellus.configuration.TELLUS_LINK)
    assert tell.categories == [tellus.configuration.TELLUS_LINK]

    assert not tell.in_category(TELLUS_INTERNAL)
    tell.add_category(TELLUS_INTERNAL)
    assert tell.categories == [TELLUS_LINK, TELLUS_INTERNAL]

    assert tell.in_category(TELLUS_LINK)
    assert tell.in_category(TELLUS_INTERNAL)

    assert tell.in_all_categories([TELLUS_LINK, TELLUS_INTERNAL])
    assert not tell.in_all_categories(
        [TELLUS_LINK, TELLUS_INTERNAL, TELLUS_DNS_OTHER]
    )
    assert tell.in_all_categories([TELLUS_INTERNAL])
    assert tell.in_all_categories(
        []
    ), "A Tell *is* in a set of empty categories with in_all_categories."

    assert tell.in_any_categories([TELLUS_LINK, TELLUS_INTERNAL])
    assert tell.in_any_categories(
        [TELLUS_LINK, TELLUS_INTERNAL, TELLUS_DNS_OTHER]
    )
    assert not tell.in_any_categories([TELLUS_DNS_OTHER])
    assert not tell.in_any_categories(
        []
    ), "A Tell is *not* in a set of empty categories with in_any_categories."

    assert tell.categories_equal([TELLUS_LINK, TELLUS_INTERNAL])
    assert not tell.categories_equal(
        [TELLUS_LINK, TELLUS_INTERNAL, TELLUS_DNS_OTHER]
    )
    assert not tell.categories_equal([TELLUS_LINK])
    assert not tell.categories_equal([TELLUS_DNS_OTHER])
    assert not tell.categories_equal([])
    no_categories = Tell("no-categories", TELLUS_INTERNAL)
    no_categories.remove_category(TELLUS_INTERNAL)
    assert no_categories.categories_equal([])

    new_tell = Tell("new-tell-a", TELLUS_DNS_OTHER)
    assert new_tell.categories_are_subset_of([TELLUS_DNS_OTHER])
    assert new_tell.categories_are_subset_of([TELLUS_DNS, TELLUS_DNS_OTHER])
    assert new_tell.categories_are_subset_of(
        [TELLUS_LINK, TELLUS_DNS, TELLUS_DNS_OTHER]
    )
    assert new_tell.categories_are_subset_of(
        [TELLUS_INTERNAL, TELLUS_DNS, TELLUS_DNS_OTHER]
    )
    assert not new_tell.categories_are_subset_of([TELLUS_INTERNAL])
    new_tell.add_category(TELLUS_DNS)
    assert new_tell.categories_are_subset_of(
        [TELLUS_LINK, TELLUS_DNS, TELLUS_DNS_OTHER]
    )
    assert not new_tell.categories_are_subset_of([TELLUS_LINK])
    assert new_tell.categories_are_subset_of(
        [TELLUS_DNS, TELLUS_DNS_OTHER, TELLUS_GO]
    )


def test_update_property():
    tell = Tell("test-tell", TELLUS_GO)

    assert (
        "alias",
        "description",
        "go_url",
        "tags",
    ) == Tell.CORE_PROPERTIES, (
        "Make sure we test any new updateable properties added..."
    )

    tell._update_property("alias", "something else")
    assert (
        tell.alias == "test-tell"
    ), "Attempting to update the Alias will simply be ignored."

    try:
        tell._update_property("something else", "Not a property.")
        pytest.fail("Updating an unrecognized property should throw an exception.")
    except InvalidTellUpdateException as exception:
        assert (
            str(exception)
            == f"'something else' is not a valid Tell property for update_properties.  Can only update the following properties using this method: {Tell.CORE_PROPERTIES}"
        )

    tell._update_property("description", "O HAI.")
    assert tell.description == "O HAI."
    tell._update_property("description", "Department of Redundancy Department.")
    assert tell.description == "Department of Redundancy Department.", (
        "Updating the description will update the " "description. "
    )

    tell._update_property("go_url", "http://brucebanner.com")
    assert tell.go_url == "http://brucebanner.com"
    tell._update_property("go_url", "http://hulksmash.com")
    assert (
        tell.go_url == "http://hulksmash.com"
    ), "Updating the go_url will update the go_url."

    assert tell.tags == []
    tell._update_property("tags", ["tag", "youre", "it"])
    assert tell.tags == ["it", "tag", "youre"], "Updating tags adds tags..."
    tell._update_property("tags", ["mor", "tags", "tag"])
    assert tell.tags == [
        "it",
        "mor",
        "tag",
        "tags",
        "youre",
    ], "Updating tags ADDS tags..."
    tell._update_property("tags", [])
    assert tell.tags == [
        "it",
        "mor",
        "tag",
        "tags",
        "youre",
    ], "No realli - it ADDS tags."
    tell._update_property("tags", "string")
    assert tell.tags == [
        "it",
        "mor",
        "string",
        "tag",
        "tags",
        "youre",
    ], "It will also handle a single string correctly."
    tell._update_property("tags", "some, more tags")
    assert tell.tags == [
        "it",
        "mor",
        "more",
        "some",
        "string",
        "tag",
        "tags",
        "youre",
    ], "Note that it will tagify a list of tags."

    tell._update_property("tags", ["can", "also", "replace", "tags"], replace_tags=True)
    assert tell.tags == ["also", "can", "replace", "tags"]

    # Testing this here for now for minimal coverage
    assert not tell.has_no_properties()
    new_tell = Tell("new-tell", TELLUS_TESTING)
    assert new_tell.has_no_properties()


def test_update_tell():
    tell = Tell("test-add-values", TELLUS_TESTING)

    try:
        tell.update_from_dict_representation(
            {"alias": "cant-send-invalid-alias"},
            source_id=SRC_UNSPECIFIED,
            modified_by="test_update_tell",
        )
        pytest.fail("Should not be able to call update tell with a different alias.")
    except InvalidTellUpdateException as exception:
        print(exception)

    tell.add_tags(["old", "tag"])
    values_dict = {
        "alias": "test-add-values",
        "description": "Test description.",
        "go_url": "http://gogogadget-tell.com",
        "go-url": "whoops",  # note where this goes - this is not the correct parameter name
        "tags": ["new", "tags", "old", "tag"],
        "category": "tellus-internal",  # This won't work the way it looks...
        "flavor": "chartreuse",
    }

    tell.update_from_dict_representation(
        values_dict, source_id=SRC_UNSPECIFIED, modified_by="test_update_tell"
    )
    assert tell.alias == values_dict["alias"]
    assert tell.description == values_dict["description"]
    assert tell.go_url == values_dict["go_url"]
    assert tell.tags == [
        "new",
        "old",
        "tag",
        "tags",
    ], "Updating tags via update_tell is additive"
    assert tell.categories == [
        "tellus-unit-testing-only"
    ]  # Can't update categories this way
    # But we're still going to stash it all here...
    assert tell.get_data_dict() == {
        SRC_UNSPECIFIED: {
            "alias": "test-add-values",
            "description": "Test description.",
            "go_url": "http://gogogadget-tell.com",
            "source-tags": ["new", "tags", "old", "tag"],
            "go-url": "whoops",
            "category": "tellus-internal",
            "flavor": "chartreuse",
        }
    }

    tell.update_from_dict_representation(
        {Tell.ALIAS: "test Add-Values"}, SRC_UNSPECIFIED, modified_by="test_update_tell"
    )
    assert tell.alias == "test-add-values", "Note that the weird alias will be cleaned."
    assert (
        tell.get_data_dict()[SRC_UNSPECIFIED]["alias"] == "test Add-Values"
    ), "But the data dict will not."

    # Some last sanity checks as I'm messing with properties
    assert tell.description is not None
    tell._update_property(Tell.DESCRIPTION, "", False)
    assert tell.description is None

    assert tell.go_url is not None
    tell._update_property(Tell.GO_URL, "", False)
    assert tell.go_url is None


def test_update_tell_with_human_modification():
    tell = Tell("test-update-protection", TELLUS_TESTING)

    values_dict = {
        "alias": "test-update-protection",
        "description": "First description.",
        "go_url": "some-url",
        "flavor": "chartreuse",
    }
    tell.update_from_dict_representation(
        values_dict, source_id=SRC_UNSPECIFIED, modified_by="somehuman"
    )
    assert tell.alias == values_dict["alias"]
    assert tell.description == values_dict["description"]
    assert tell.go_url == "some-url"
    assert tell.tags == []
    assert tell.categories == ["tellus-unit-testing-only"]
    assert tell.sources == [SRC_UNSPECIFIED]
    assert tell.get_data_dict() == {
        SRC_UNSPECIFIED: {
            "alias": "test-update-protection",
            "description": "First description.",
            "go_url": "some-url",
            "flavor": "chartreuse",
        }
    }

    values_dict = {
        "alias": "test-update-protection",
        "description": "Second description.",
        "go_url": "/go-url",
        "tags": "other, source",
        "flavor": "bacon",
    }
    tell.update_from_dict_representation(
        values_dict, source_id="made up source", modified_by="somehuman"
    )  # We don't check source validity here
    assert tell.alias == values_dict["alias"]
    assert (
        tell.description == "Second description."
    ), "Updating from a source just overlays other sources."
    assert tell.go_url == "/go-url"
    assert tell.tags == ["other", "source"]
    assert tell.categories == ["tellus-unit-testing-only"]
    assert tell.get_data_dict() == {
        "made up source": {
            "alias": "test-update-protection",
            "description": "Second description.",
            "go_url": "/go-url",
            "source-tags": "other, source",
            "flavor": "bacon",
        },
        SRC_UNSPECIFIED: {
            "alias": "test-update-protection",
            "description": "First description.",
            "go_url": "some-url",
            "flavor": "chartreuse",
        },
    }, "Different sources will go in different maps, even with the same value"

    tell.add_category(TELLUS_DNS_OTHER)
    tell.remove_category(TELLUS_TESTING)
    values_dict_last = {
        "alias": "test-update-protection",
        "description": "Go update",
        "go_url": "/gogotamago",
        "source-tags": "goto",
        "flavor": "umami",
    }
    tell.update_from_dict_representation(
        values_dict_last, source_id=SRC_UNSPECIFIED, modified_by="somehuman"
    )
    assert tell.alias == values_dict_last["alias"]
    assert (
        tell.description == values_dict["description"]
    ), "There is a coalesce at the end of the update!"
    assert (
        tell.go_url == values_dict["go_url"]
    ), "There is a coalesce at the end of the update!"
    assert tell.tags == ["other", "source"]
    assert tell.categories == [TELLUS_DNS_OTHER]
    assert tell.get_data_dict() == {
        "made up source": {
            "alias": "test-update-protection",
            "description": "Second description.",
            "flavor": "bacon",
            "go_url": "/go-url",
            "source-tags": "other, source",
        },
        SRC_UNSPECIFIED: {
            "alias": "test-update-protection",
            "description": "Go update",
            "flavor": "umami",
            "go_url": "/gogotamago",
            "source-tags": "goto",
        },
    }, "Same source should update its map"

    tell.add_category(TELLUS_GO)
    set_go_url(tell, None)
    values_dict_post_human = {
        "alias": "test-update-protection",
        "description": "Oh.  The humanity.",
        "go_url": None,  # Note - this won't really work...
        "source-tags": "humans-only",
        "flavor": "durian",
    }
    tell.update_from_dict_representation(
        values_dict_post_human, source_id=TELLUS_USER_MODIFIED, modified_by="somehuman"
    )
    assert tell.get_data_dict() == {
        TELLUS_USER_MODIFIED: {
            "alias": "test-update-protection",
            "description": "Oh.  The humanity.",
            "flavor": "durian",
            "go_url": None,
            "source-tags": "humans-only",
        },
        SRC_UNSPECIFIED: {
            "alias": "test-update-protection",
            "description": "Go update",
            "flavor": "umami",
            "go_url": "/gogotamago",
            "source-tags": "goto",
        },
        "made up source": {
            "alias": "test-update-protection",
            "description": "Second description.",
            "flavor": "bacon",
            "go_url": "/go-url",
            "source-tags": "other, source",
        },
    }
    assert tell.alias == values_dict_post_human["alias"]
    assert (
        tell.description == "Oh.  The humanity."
    ), "Human updates always take precedence...."
    assert tell.go_url == "/go-url", "You can't really override with None by a human."
    assert tell.tags == [
        "other",
        "source",
    ], "Tags remain additive, BUT are only added once by a source."
    assert tell.categories == [
        TELLUS_DNS_OTHER,
        TELLUS_GO,
        TELLUS_USER_MODIFIED,
    ], "Will not lose attributes - but will add them into the data source dictionary"


def test_data_blocks():
    tell = Tell("test-tell", TELLUS_TESTING)

    assert tell.get_data("Any Source") is None
    assert tell.get_datum("Any Source", "Any Value") is None
    assert tell.get_datum("Any Source", "Any Value", "Bar") == "Bar"

    tell.update_datum_from_source(
        source_id=SRC_UNSPECIFIED, key="A thing", value="Some stuff!"
    )
    assert tell.get_data_dict() == {SRC_UNSPECIFIED: {"A thing": "Some stuff!"}}

    assert tell.get_data(SRC_UNSPECIFIED) == {"A thing": "Some stuff!"}
    assert tell.get_datum(SRC_UNSPECIFIED, "A thing") == "Some stuff!"
    assert (
        tell.get_datum(SRC_UNSPECIFIED, "A thing", "Not some stuff!") == "Some stuff!"
    )
    assert (
        tell.get_datum(SRC_UNSPECIFIED, "Another thing", "Not some stuff!")
        == "Not some stuff!"
    )
    assert tell.get_datum(SRC_UNSPECIFIED, "Another thing") is None

    tell.update_datum_from_source(SRC_UNSPECIFIED, "And Another Thing", "Whyyyyyyyy?")
    tell.update_datum_from_source("foo", "bar", "baz")
    assert tell.get_data_dict() == {
        "foo": {"bar": "baz"},
        "tellus-src-unspecified": {
            "A thing": "Some stuff!",
            "And Another Thing": "Whyyyyyyyy?",
        },
    }

    assert tell.remove_datum(SRC_UNSPECIFIED, "A thing") == "Some stuff!"
    assert tell.get_data_dict() == {
        "foo": {"bar": "baz"},
        "tellus-src-unspecified": {"And Another Thing": "Whyyyyyyyy?",},
    }
    assert tell.remove_datum(SRC_UNSPECIFIED, "A thing") is None

    assert tell.clear_data(SRC_UNSPECIFIED) == {
        "And Another Thing": "Whyyyyyyyy?",
    }
    assert tell.get_data_dict() == {"foo": {"bar": "baz"}}
    assert tell.clear_data(SRC_UNSPECIFIED) is None


def test_coalesce():
    # Just a check in case we update properties
    assert Tell.UPDATEABLE_PROPERTIES == (Tell.DESCRIPTION, Tell.GO_URL, Tell.TAGS)

    alias = "test-coalesce"
    tell = Tell(alias, TELLUS_TESTING)

    sorted_sources = tell.prioritized_sources()
    assert sorted_sources == []

    tell.coalesce()
    assert tell.has_no_properties(), "Empty Tell is empty, even after Coalesce."
    assert tell.property_sources == {}

    first_source = {
        "source_id": "first-source",
        "alias": "first-source",  # Note this will be ignored
        Tell.DESCRIPTION: "first-source description",
    }

    tell.update_data_from_source(first_source["source_id"], first_source)
    assert not tell.has_no_properties(), "Coalesce is called in the update"
    sorted_sources = tell.prioritized_sources()
    assert sorted_sources == ["first-source"]
    assert tell.description == "first-source description"
    assert tell.go_url is None
    assert tell.tags == []
    assert tell.property_sources == {"description": ["first-source"]}

    second_source = {
        "source_id": "second-source",
        Tell.DESCRIPTION: "second-source description",
        Tell.GO_URL: "second-source.com",
        Tell.TAGS: "blue, no, yellow",
    }

    tell.update_data_from_source(second_source["source_id"], second_source)
    sorted_sources = tell.prioritized_sources()
    assert sorted_sources == [
        "first-source",
        "second-source",
    ]
    # tell.coalesce() - this is now called in update_data_from_source
    assert tell.description == "first-source description"
    assert tell.go_url == "second-source.com"
    assert tell.tags == ["blue", "no", "yellow"]
    assert tell.property_sources == {
        "description": ["first-source", "second-source"],
        "go_url": ["second-source"],
        "tags": ["second-source"],
    }

    third_source = {
        "source_id": "a_third_source",
        Tell.GO_URL: "third_source.gov",
        Tell.TAGS: "purple, yellow",
        "randomness": "something else",
        "category": TELLUS_USER_MODIFIED,
        "group": "tellus",
    }

    tell.update_data_from_source(third_source["source_id"], third_source)
    sorted_sources = tell.prioritized_sources()
    assert sorted_sources == [
        "a_third_source",
        "first-source",
        "second-source",
    ]
    # tell.coalesce() - this is now called in update_data_from_source
    assert tell.description == "first-source description"
    assert tell.go_url == "third_source.gov"
    assert tell.tags == ["blue", "no", "purple", "yellow"]
    assert tell.property_sources == {
        "description": ["first-source", "second-source"],
        "go_url": ["a_third_source", "second-source"],
        "tags": ["a_third_source"],
    }, (
        "Note the order is alphabetical.  AND NOTE that 'second-source' is no longer part of the tags sources.  "
        "See coalesce() for details."
    )

    # Various cheating, to verify Coalesce still works as expected...
    tell._update_property(
        Tell.DESCRIPTION, "Manually set description - don't do this any more", False
    )
    set_go_url(tell, "second-source.com")
    tell._update_tags("chartreuse", True)
    assert (
        tell.description == "Manually set description - don't do this any more"
    ), "Without a coalesce, this can put you in a weird state..."
    tell.coalesce()
    assert tell.description == "first-source description"
    assert tell.go_url == "third_source.gov"
    assert tell.tags == [
        "chartreuse"
    ], "Note that because of the way coalesce() handles tags, this is the only tag"
    assert tell.property_sources == {
        "description": ["first-source", "second-source"],
        "go_url": ["a_third_source", "second-source"],
    }, "Manual property updates don't work any more.  And note there are no sources for tags."

    ui_update = {
        Tell.DESCRIPTION: "Description from a human",
        Tell.TAGS: "quislet",
    }
    tell.update_data_from_source(TELLUS_USER_MODIFIED, ui_update)

    sorted_sources = tell.prioritized_sources()
    assert sorted_sources == [
        TELLUS_USER_MODIFIED,
        "a_third_source",
        "first-source",
        "second-source",
    ]

    fourth_source = {
        "source_id": "fourth-source",
        Tell.DESCRIPTION: "may the fourth be with you",
        Tell.GO_URL: "the-fourth.net",
        "randomness": "something else",
        "category": TELLUS_USER_MODIFIED,
        "group": "tellus",
    }
    tell.update_data_from_source(fourth_source["source_id"], fourth_source)

    # tell.coalesce() - now called in update_data_from_source
    assert tell.description == "Description from a human"
    assert tell.go_url == "third_source.gov"
    assert tell.tags == ["chartreuse", "quislet"]
    assert tell.property_sources == {
        "description": [
            "tellus-user",
            "first-source",
            "fourth-source",
            "second-source",
        ],
        "go_url": ["a_third_source", "fourth-source", "second-source"],
    }


def test_prioritized_sources():
    tell = Tell("test-prioritized-sources", TELLUS_TESTING)
    tell.update_datum_from_source("1-source", Tell.DESCRIPTION, "Source Number 1")
    tell.update_datum_from_source("5-source", Tell.DESCRIPTION, "Source Number 5")
    tell.update_datum_from_source(TELLUS_GO, Tell.DESCRIPTION, "Go")
    tell.update_datum_from_source(
        TELLUS_USER_MODIFIED, Tell.DESCRIPTION, "User Modified"
    )
    tell.update_datum_from_source("2-source", Tell.DESCRIPTION, "Source Number 2")
    tell.update_datum_from_source("9-source", Tell.DESCRIPTION, "Source Number 9")

    prioritized = tell.prioritized_sources()
    assert prioritized == [
        TELLUS_USER_MODIFIED,
        TELLUS_GO,
        "1-source",
        "2-source",
        "5-source",
        "9-source",
    ]

    prioritized = tell.prioritized_sources(True)
    assert prioritized == [
        "9-source",
        "5-source",
        "2-source",
        "1-source",
        TELLUS_GO,
        TELLUS_USER_MODIFIED,
    ]


def test_tellus_info():
    tell = Tell("test-tellus-info", TELLUS_TESTING)
    assert tell.tellus_info() == {}
    assert tell.minimal_tell_dict() == {
        "alias": "test-tellus-info",
        "categories": ["tellus-unit-testing-only"],
        "description": None,
        "go_url": None,
        "tags": [],
    }, "Tellus Info will not appear at all unless there is some"

    timestamp = now_string()
    tell.update_tellus_info("source-one", {"inactive-since": timestamp})
    assert tell.tellus_info() == {"source-one": {"inactive-since": timestamp}}

    tell.update_tellus_info("source-two", {"inactive-since": "thursday"})
    tell.update_datum_from_source("source-two", "tellus", "irrelevant!")
    assert tell.tellus_info() == {
        "source-one": {"inactive-since": timestamp},
        "source-two": {"inactive-since": "thursday"},
    }

    tell.update_tellus_info("source-three", "also-wik")
    assert tell.tellus_info() == {
        "source-one": {"inactive-since": timestamp},
        "source-two": {"inactive-since": "thursday"},
        "source-three": "also-wik",
    }

    assert tell.minimal_tell_dict() == {
        "alias": "test-tellus-info",
        "categories": ["tellus-unit-testing-only"],
        "description": None,
        "go_url": None,
        "tags": [],
        Tell.TELLUS_INFO: {
            "source-one": {"inactive-since": timestamp},
            "source-two": {"inactive-since": "thursday"},
            "source-three": "also-wik",
        },
    }

    tell.update_tellus_info("source-two", None)
    assert tell.tellus_info() == {
        "source-one": {"inactive-since": timestamp},
        "source-three": "also-wik",
    }

    tell.update_tellus_info(
        "source-forty-two", None
    )  # This should do nothing, but still work
    assert tell.tellus_info() == {
        "source-one": {"inactive-since": timestamp},
        "source-three": "also-wik",
    }
