# NOTE: this file is suite of tests for various Tellus Sources, vs the actual test of the Source
# functionality, which is in sources_test

# from tellus.creds import get_credentials_from_vault
import os

import pytest
from sortedcontainers import SortedSet

from tellus.configuration import (
    TELLUS_INTERNAL,
    TELLUS_TOOL,
    TELLUS_TOOL_RELATED,
    TELLUS_LINK,
    TELLUS_USER_MODIFIED,
)
from tellus.tell import Tell
from tellus.tellus_sources.tellus_yaml_source import (
    TellusYMLSource,
    GITHUB_REPO_DATUM,
    TELLUS_CONFIG_TOOLS,
    ToolConfig,
)
from test.tells_test import create_test_teller

TELLUS_YML = """
alias: tellus
description: O HAI I AM TELLUS
"""

QUISLET_YML = """
alias: quislet
description: O HAI I AM QUISLET
tags: yo
"""

LEGION_YML = """
alias: legion
description: Legion of Super-Heroes
tags: earth, dc
---
alias: saturn-girl
description: 'Unknown'
tags: earth
colors: none
---
alias: saturn-girl
description: 'Imra Ardeen'
tags: saturn
colors: red and white
---
alias: lightning lad
description: 'Garth Ranzz'
tags: winath
colors: blue and yellow
---
alias: cosmic_boy
description: 'Rokk Krinn'
tags: 'braal, magnets *'
colors: purple and grey
---
alias: quislet
description: Overridden description
tags: additive tags
---
alias: -history
description: 'Legion history'
go_url: 'https://en.wikipedia.org/wiki/Legion_of_Super-Heroes'
tags: 'history, comics'
colors: 'yellow and gold'

"""
LEGION_EXPECTED_ALIASES = [
    "legion",
    "saturn-girl",
    "lightning-lad",
    "cosmic-boy",
    "quislet",
    "legion-history",
]
GITHUB_SEARCH_URL_1 = "https://github.com:443/api/v3/search/code?order=desc&q=filename%3Atellus.yml&per_page=1"
GITHUB_SEARCH_URL_2 = (
    "https://github.com:443/api/v3/search/code?order=desc&q=filename%3Atellus.yml"
)


def test_load_tellus_files():
    teller = create_test_teller()
    handler = TellusYMLSource(teller)

    teller.create_tell("tellus", TELLUS_INTERNAL, "sources_test", url="/tellus")

    handler.parse_tellus_file(TELLUS_YML, "aTellusRepo", "aTellusRepo")
    handler.parse_tellus_file(QUISLET_YML, "aQuisletRepo", "aQuisletRepo")

    # Quislet did not already exist
    quislet_tell = teller.get("quislet")
    assert quislet_tell is not None
    assert quislet_tell.categories == [TELLUS_TOOL]
    assert quislet_tell.description == "O HAI I AM QUISLET"
    assert quislet_tell.audit_info.created_by == handler.source_id
    assert quislet_tell.audit_info.last_modified_by == handler.source_id

    # Tellus Already existed
    tellus_tell = teller.get("tellus")
    assert tellus_tell is not None
    assert tellus_tell.in_all_categories([TELLUS_TOOL, TELLUS_INTERNAL])
    assert tellus_tell.description == "O HAI I AM TELLUS"
    assert tellus_tell.audit_info.last_modified_by == handler.source_id


def test_update_tellus_files():
    teller = create_test_teller()
    handler = TellusYMLSource(teller)

    tell = teller.create_tell("tellus", TELLUS_INTERNAL, "sources_test", url="/tellus")

    handler.parse_tellus_file(TELLUS_YML, "aTellusRepo", "aTellusRepo")
    assert tell.tags == [], "Sanity check."
    assert tell.get_data_dict() == {
        TELLUS_TOOL: {
            "alias": "tellus",
            "description": "O HAI I AM TELLUS",
            GITHUB_REPO_DATUM: "https://github.com/aTellusRepo",
        },
        TELLUS_INTERNAL: {"go_url": "/tellus"},
    }

    tellus_updated_yml = """
    alias: tellus

    description: I am Tellus, hear me roar.  Telepathically.
    go_url: https://en.wikipedia.org/wiki/Tellus
    tags: tellus, tell, us, more also spaces are weird NOBIGWORDS!!!
    something-else:  some values here!!!

    """
    handler.parse_tellus_file(tellus_updated_yml, "aNewTellusRepo", "aNewTellusRepo")
    assert tell.tags == [
        "also",
        "are",
        "more",
        "nobigwords",
        "spaces",
        "tell",
        "tellus",
        "us",
        "weird",
    ]
    assert tell.description == "I am Tellus, hear me roar.  Telepathically."
    assert tell.go_url == "https://en.wikipedia.org/wiki/Tellus"
    assert tell.get_data_dict() == {
        TellusYMLSource.SOURCE_ID: {
            "alias": "tellus",
            "description": "I am Tellus, hear me roar.  Telepathically.",
            "go_url": "https://en.wikipedia.org/wiki/Tellus",
            GITHUB_REPO_DATUM: "https://github.com/aNewTellusRepo",
            "something-else": "some values here!!!",
            "source-tags": "tellus, tell, us, more also spaces are weird NOBIGWORDS!!!",
        },
        TELLUS_INTERNAL: {"go_url": "/tellus"},
    }

    tell.make_user_modified()
    tell.update_datum_from_source(
        TELLUS_USER_MODIFIED, Tell.DESCRIPTION, "Tellus User Modified description"
    )
    tellus_updated_yml = """
    alias: tellus
    description: Test description
    go_url: https://en.wikipedia.org/wiki/Tellus
    source-tags: human-updated
    something-else:  should update this
    """

    handler.parse_tellus_file(
        tellus_updated_yml, "anotherNewTellusRepo", "anotherNewTellusRepo"
    )
    assert tell.tags == [
        "also",
        "are",
        "more",
        "nobigwords",
        "spaces",
        "tell",
        "tellus",
        "us",
        "weird",
    ]
    assert tell.go_url == "https://en.wikipedia.org/wiki/Tellus"
    assert (
        tell.description == "Tellus User Modified description"
    ), "Will not override description if human-updated"
    print(tell.get_data_dict())
    assert tell.get_data_dict() == {
        TellusYMLSource.SOURCE_ID: {
            "alias": "tellus",
            "description": "Test description",
            "go_url": "https://en.wikipedia.org/wiki/Tellus",
            GITHUB_REPO_DATUM: "https://github.com/anotherNewTellusRepo",
            "something-else": "should update this",
            "source-tags": "human-updated",
        },
        "tellus-internal": {"go_url": "/tellus"},
        "tellus-user": {"description": "Tellus User Modified description"},
    }, "If human updated, source property updates get shoved into the data map"

    # Test removing an element from the yml
    tellus_updated_yml = """
        alias: tellus
        description: Test description
        go_url: https://en.wikipedia.org/wiki/Tellus
        source-tags: human-updated
        """  # Note 'something-else' has been removed
    handler.parse_tellus_file(
        tellus_updated_yml, "testingRemoveValue", "testingRemoveValue"
    )
    assert tell.get_data_dict() == {
        TellusYMLSource.SOURCE_ID: {
            "alias": "tellus",
            "description": "Test description",
            "go_url": "https://en.wikipedia.org/wiki/Tellus",
            GITHUB_REPO_DATUM: "https://github.com/testingRemoveValue",
            "source-tags": "human-updated",
        },
        "tellus-internal": {"go_url": "/tellus"},
        "tellus-user": {"description": "Tellus User Modified description"},
    }, "If human updated, source property updates get shoved into the data map"


def test_complex_tellus_file():
    teller = create_test_teller()
    handler = TellusYMLSource(teller)

    superboy = teller.create_tell(
        "superboy",
        TELLUS_INTERNAL,
        "sources_test",
        url="https://en.wikipedia.org/wiki/Superboy_(Kal-El)",
    )
    quislet = teller.create_tell(
        "quislet", TELLUS_INTERNAL, "sources_test", url="/quislet"
    )

    handler.parse_tellus_file(QUISLET_YML, "theQuisletRepo", "theQuisletRepo")
    assert quislet == teller.get("quislet")
    assert quislet.tags == ["yo"], "Should have added tags to Quislet"
    assert (
        quislet.description == "O HAI I AM QUISLET"
    ), "Should have updated the description."
    assert teller.tells_count() == 3, "2 new tells, plus the tools config tell"

    handler.parse_tellus_file(LEGION_YML, "theLegionRepo", "theLegionRepo")
    assert teller.tells_count() == 8
    legion = teller.get("legion")
    assert legion.categories == [TELLUS_TOOL]

    current_aliases = list(
        SortedSet(LEGION_EXPECTED_ALIASES + ["superboy", "tellus-config-tools"])
    )
    assert teller.aliases == current_aliases

    # tellus-task: revisit this:
    assert (
        quislet.description == "Overridden description"
    ), "Duplicate tells will overlay each other."
    assert quislet.tags == [
        "additive",
        "legion",
        "tags",
        "yo",
    ], "Tags are additive here, and include the primary alias"
    assert quislet.categories == [
        TELLUS_TOOL,
        TELLUS_TOOL_RELATED,
        TELLUS_INTERNAL,
    ]

    assert superboy.tags == [], "Superboy is not yet in the legion"

    assert not teller.has_tell("-history"), "Should have only added sub-tell"
    assert not teller.has_tell("history"), "Should have only added sub-tell"
    assert teller.has_tell(
        "legion-history"
    ), "sub-tell alias is created by prepending the alias of the parent."
    history = teller.get("legion-history")
    assert history.tags == ["comics", "history", "legion"]
    assert history.go_url == "https://en.wikipedia.org/wiki/Legion_of_Super-Heroes"
    assert history.categories == [TELLUS_TOOL, TELLUS_TOOL_RELATED]

    assert teller.get("cosmic-boy").tags == [
        "braal",
        "dc",
        "earth",
        "legion",
        "magnets",
    ], "A * in the tag field causes tell to inherit all parent tags"

    saturn_girl = teller.get("saturn-girl")
    assert (
        saturn_girl.description == "Imra Ardeen"
    ), "Duplicate sub-tells will overlay each other..."
    assert saturn_girl.get_data_dict() == {
        "tellus-aq-tool": {
            "alias": "saturn-girl",
            "colors": "red and white",
            "description": "Imra Ardeen",
            "github-repo": "https://github.com/theLegionRepo",
            "source-tags": "saturn",
        },
    }
    assert saturn_girl.in_group("legion")

    assert legion.has_tag("legion")
    assert legion.tags == [
        "dc",
        "earth",
        "legion",
    ], "If a Tellus has related tells, it gets its alias as a tag"


BAD_YML = """
I AM A BAD BAD YML FILE
NO SRSLY - I have werid stuff like this in me which totally breaks parsing:

import logging

import yaml
from aiohttp import web
from github import Github

from tellus.configuration import GITHUB_ACCESS_TOKEN, GITHUB_API_URL, GITHUB_URL
from tellus.github_helper import download_github_file
from tellus.sources import Source
from tellus.tell import TELLUS_TOOL, Tell, TELLUS_TOOL_RELATED, TELLUS_PREFIX

SRC_TELLUS_YML = TELLUS_TOOL
GITHUB_REPO_DATUM = "github-repo"

TELLUS_CONFIG_TOOLS = TELLUS_PREFIX + "config-tools"
MAGIC_WORDS = {"builds": "Builds", "deploy": "Deploy", "github": "Github Repo"}


class TellusYMLSource(Source):
    def __init__(self, teller):
        super().__init__(TELLUS_TOOL, "tellus.yml files")
        self._teller = teller



"""

MINIMAL_YML = """
alias: tellus
---
alias: -helmet
"""

UNEXPECTED_YML = """
alias: Prod-View
description: Viewport
go_url: prodserver.github.com:8080
---
alias: Cert-View
description: Viewport
go_url: someserver.github.com:8080
---
alias: Cart View
description: Viewport
go_url: other-server.github.com:8080
---
alias: tellus-ignore
description: Just as a subtle check on tellus-ignore
go_url: something
---
tellus-ignore: True
alias: the-thing-that-should-not-be
description: This one should actually be ignored
go_url: something
---
alias: config.json
description: Configuration values
go_url: https://github.com/config.json
---
foo: bar
---
huh?
"""

EMPTY_YML = """
# I am an empty yml other than a comment
"""

TESTING_YML = f"""
# I am a YAML generally used for testing (probably testing Tellus)
# Anything after tellus-ignore will...be ignored.
{TellusYMLSource.IGNORE_MARKER}: True
---
alias: should-be-ignored
description: This Tell should be skipped because of the ignore marker in the Primary Tell
go_url: whatever
"""


def test_assorted_tellus_yml():
    teller = create_test_teller()
    handler = TellusYMLSource(teller)
    expected_tells_count = 0

    try:
        assert not handler.parse_tellus_file(BAD_YML, "bad yml", "bad file")
    # pylint: disable=broad-except
    except Exception as exception:
        pytest.fail(
            f"Tellus should not fail on exception during processing a yml file: {repr(exception)}"
        )
    assert teller.tells_count() == 0, "Should not have created Tells for bad YML."

    assert handler.parse_tellus_file(MINIMAL_YML, "minimal yml", "minimal file")
    expected_tells_count += 3
    assert (
        teller.tells_count() == expected_tells_count
    ), "This minimal yml file should work and add 3 tells"

    assert not handler.parse_tellus_file(
        UNEXPECTED_YML, "unexpected yml", "unexpected file"
    )
    assert not teller.has_tell(
        "the-thing-that-should-not-be"
    ), "This one should have been ignored"
    expected_tells_count += 5
    assert (
        teller.tells_count() == expected_tells_count
    ), "With a partially unexpected yml, we may create some Tells and not others..."

    assert not handler.parse_tellus_file(EMPTY_YML, "empty yml", "empty yml")
    assert teller.tells_count() == expected_tells_count

    assert handler.parse_tellus_file(TESTING_YML, "testing yml", "testing yml")
    assert teller.tells_count() == expected_tells_count


def test_main_tellus_yml():
    # This test is to dog food the main tellus.yml file, which has some special
    # behaviors and tells, and changing this can have an impact on Tellus functionality.
    teller = create_test_teller()
    handler = TellusYMLSource(teller)

    tellus_yml_file = open(
        f"{os.path.dirname(os.path.abspath(__file__))}/../tellus.yml", "r"
    )  # Yes, this assumes we have a local tellus.yml file in a particular relative path.
    tellus_yml = tellus_yml_file.read()

    handler.parse_tellus_file(tellus_yml, "tellus", "fake/tellus.yml")
    assert teller.tells_count() == 2, "Tellus currently generates two tells for itself."
    tellus = teller.get("tellus")

    assert tellus.go_url == "https://github.com"
    assert (
        tellus.description is not None
    ), "Don't care what it is, as long as Tellus has a description"
    assert tellus.get_data_dict() == {
        "tellus-aq-tool": {
            "about": "https://github.com/tellusstaticfiles/tellus.html",
            "alias": "tellus",
            "builds": "https://build.github.com/#/builders?tags=%2Btellus",
            "colors": "yellow and purple",
            "description": "Tellus is our central portal/hub, living "
            "at github.com - you are, probably, here.",
            "github-repo": "https://github.com/tellus",
            "go_url": "https://github.com",
            "deploy": "https://deploy.github.com",
            "source-tags": "tellus, tools",
        },
    }

    tellus_config_tools = teller.get(TELLUS_CONFIG_TOOLS)
    assert tellus_config_tools


def test_setup_tools():
    teller = create_test_teller()
    source = TellusYMLSource(teller)

    config = source.tool_config()  # Will lazily create the Tell.
    config.enable()

    config_tell = teller.get(TELLUS_CONFIG_TOOLS)
    source.set_up_tools()
    assert config_tell.in_category(TELLUS_INTERNAL)
    for keyword in ToolConfig.KEYWORDS:
        magic_tell = teller.get(ToolConfig.PREFIX + keyword)
        assert magic_tell.in_category(TELLUS_INTERNAL)
        assert not magic_tell.in_group(keyword)
        assert magic_tell.has_tag(keyword)

        teller.create_tell(
            keyword,
            TELLUS_LINK,
            "Simulating a things like docs.github.com etc. existing for round 2...",
        )

    source.set_up_tools()
    for keyword in ToolConfig.KEYWORDS:
        magic_tell = teller.get(ToolConfig.PREFIX + keyword)
        assert magic_tell.in_category(TELLUS_INTERNAL)
        assert magic_tell.has_tag(keyword)
        assert magic_tell.in_group(
            keyword
        ), "Because a Tell exists for this keyword, it should be grouped with it"


def test_tools_keywords():
    teller = create_test_teller()
    source = TellusYMLSource(teller)
    tellus_yml = f"""
alias: tellus
description: O HAI I AM TELLUS
go_url: https://github.com
docs: http://some.docs.for.tellus
builds:  https://build.github.com/#/builders/somenumber
---
alias: {TELLUS_CONFIG_TOOLS}
description:  A configuration Tell for Tellus - configures certain "magic word" URLs for the tellus.yml files.
tags: tellus, tools, tellus-config
builds: https://build.github.com/#/builders/<ID>
deploy: https://deploy.github.com/ui/jobs/<alias>
github-repo: https://github.com/<org>/<alias>
    """

    source.set_up_tools()
    assert teller.tells_count() == 1, "Should have ONLY set up the config tells."

    source.tool_config().enable()
    source.set_up_tools()
    assert teller.tells_count() == 6, "Should have set up the tools tells."

    source.parse_tellus_file(tellus_yml, "tellus_magic_words", "fake.yml")
    assert (
        teller.tells_count() == 7
    ), "Should have created a single new Tell (since the config tell already exists)"
    tellus = teller.get("tellus")
    config = source.tool_config()

    assert (
        config.data_for_keyword("builds", tellus)
        == "https://build.github.com/#/builders/somenumber"
    )
    assert config.data_for_keyword("build", tellus) is None
    assert config.data_for_keyword("docs", tellus) == "http://some.docs.for.tellus"
    assert (
        config.data_for_keyword("github", tellus) is None
    ), "github-repo != github here"

    docs_tell = teller.get(ToolConfig.tool_tell_alias("docs"))
    assert (
        docs_tell.get_datum(docs_tell.alias, "tellus") == "http://some.docs.for.tellus"
    )

    docs_tell = teller.get(ToolConfig.tool_tell_alias("builds"))
    assert (
        docs_tell.get_datum(docs_tell.alias, "tellus")
        == "https://build.github.com/#/builders/somenumber"
    )

    # assert tell.get_datum(source.source_id, "github") == "another github URL"
    # assert tell.get_datum(handler.source_id, 'about') == "https://github.com/tellusstaticfiles/tellus.html"
    # assert tell.get_datum(handler.source_id, 'builds-id*') == "https://build.github.com/#/builders/2318"


def test_tools_keywords_disabled():
    teller = create_test_teller()
    source = TellusYMLSource(teller)
    tellus_yml = f"""
alias: tellus
description: O HAI I AM TELLUS
go_url: https://github.com
docs: http://some.docs.for.tellus
builds:  https://build.github.com/#/builders/somenumber
---
alias: {TELLUS_CONFIG_TOOLS}
description:  A configuration Tell for Tellus - configures certain "magic word" URLs for the tellus.yml files.
tags: tellus, tools, tellus-config
builds: https://build.github.com/#/builders/<ID>
build: https://build.github.com/ui/jobs/<alias>
github-repo: https://github.com/<org>/<alias>
    """

    source.set_up_tools()
    assert (
        teller.tells_count() == 1
    ), "Should have set up only the config Tell if not enabled yet."

    source.parse_tellus_file(tellus_yml, "tellus_magic_words", "fake.yml")
    assert (
        teller.tells_count() == 2
    ), "Should have created a single new Tell (since the config tell already exists)"
    tellus = teller.get("tellus")
    config = source.tool_config()

    # this should all work the same
    assert (
        config.data_for_keyword("builds", tellus)
        == "https://build.github.com/#/builders/somenumber"
    )
    assert config.data_for_keyword("build", tellus) is None
    assert config.data_for_keyword("docs", tellus) == "http://some.docs.for.tellus"
    assert (
        config.data_for_keyword("github", tellus) is None
    ), "github-repo != github here"
