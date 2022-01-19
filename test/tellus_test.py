# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests

import asyncio
import json
import pathlib
import re
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from yarl import URL

import tellus.wiring
from tellus.wiring import STATIC_FILES
from tellus import routes as routes
from tellus.main import _create_and_load_webapp
from tellus.sources import Sourcer
from tellus.tell import Tell
from tellus.configuration import (
    TELLUS_INTERNAL,
    TELLUS_GO,
    TELLUS_LINK,
    TELLUS_DNS,
    TELLUS_DNS_OTHER,
    TELLUS_ABOUT_TELL,
)
from tellus.tells import TheresNoTellingException
from tellus.tells_handler import TellsHandler, ALL_TELLS
from tellus.tellus_sources.tellus_yaml_source import TellusYMLSource
from tellus.users import UserManager
from tellus.wiring import R_LINKS, FAIL, R_GO, R_TELL, R_SOURCES, R_SEARCH
from test.tellus_test_utils import (
    make_mock_response,
)  # NOTE: mock_session must be imported
from test.sources_test import FakeSource
from test.tells_test import (
    create_test_teller,
    create_current_save_file,
    TELLUS_TEST_USER,
    create_search_tells,
    SEARCH_TERM_MATCHES,
)
from tellus import __version__

# noinspection PyUnresolvedReferences
from test.tellus_test_utils import (
    mock_session,
    this_test_name,
)  # No Realli Pycharm - we need this

class DNSHandler:
    pass
    # TODO

STATIC_DIR = pathlib.Path.cwd() / routes.STATIC_DIR


@pytest.fixture
def test_fs(fs):
    # SUUUUUPER hacky - but I haven't figured out a better way yet...
    # For some reason all methods I have come up with to determine the actual file path
    # result in an exception either running a single test locally or running all tests.
    # This fixes it, and allows tests to run successfully in both PyCharm and pytest/make test
    try:
        fs.add_real_directory(routes.STATIC_DIR)
    except FileNotFoundError:
        fs.add_real_directory(f"../{routes.STATIC_DIR}")

    return fs


def create_and_load_test_webapp(teller, sourcer=None, user_manager=None):
    # Create a testing version of the web app
    # Allows for disabling of source loading during testing, primarily

    if sourcer is None:
        # This should really just be for testing - will disable all sources
        sourcer = Sourcer(teller, enabled_sources=[])

    if user_manager is None:
        user_manager = UserManager(teller)

    return _create_and_load_webapp(teller, sourcer, user_manager)


async def assert_response_text(
    client, query, expected, message="Response did not match expected."
):
    response = await client.get(query)
    assert response.status == 200, "If we're getting text we always expect a 200"
    text = await response.text()
    assert text == expected, message


async def test_route_fail(test_fs, aiohttp_client):
    app = create_and_load_test_webapp(create_test_teller())
    client = await aiohttp_client(app)
    response = await client.get(FAIL)
    assert response.status == 500


async def test_adds_cache_control_header(test_fs, aiohttp_client):
    app = create_and_load_test_webapp(create_test_teller())
    client = await aiohttp_client(app)
    response = await client.get("/index.html")
    assert response.headers["cache-control"] == "no-cache"
    response = await client.get(f"/{STATIC_FILES}/tellus.html")
    assert (
        response.headers["cache-control"] == "no-cache"
    ), "Should work no matter which page we call"


async def test_route_tellus_status(test_fs, aiohttp_client):
    app = create_and_load_test_webapp(create_test_teller())
    client = await aiohttp_client(app)
    response = await client.get(routes.TELLUS_STATUS)
    assert response.status == 200
    text = await response.text()
    status_dict = json.loads(text)
    assert status_dict["localPersistence"] is True
    assert status_dict["tellusVersion"] == __version__
    assert status_dict["whoami"] is None, "No User, no cry"
    # assert "/img/tellus.png" in text


async def test_route_alive_check(test_fs, aiohttp_client):
    app = create_and_load_test_webapp(create_test_teller())
    client = await aiohttp_client(app)
    response = await client.get(routes.CONSUL_CHECK)
    assert response.status == 200
    text = await response.text()
    status_dict = json.loads(text)
    assert status_dict["localPersistence"] is True
    assert status_dict["tellusVersion"] == __version__
    assert (
        status_dict["whoami"] == TellsHandler.WHOAMI_API_NO_USER
    ), "The Consul check is expected to be identified as a no-User call"
    # assert "/img/tellus.png" in text


async def test_route_home(aiohttp_client):
    # For reasons I don't entirely understand, using test_fs here causes an Exception
    # Which means this test cannot successfully run in PyCharm (works under pytest though)
    app = create_and_load_test_webapp(create_test_teller())
    client = await aiohttp_client(app)
    response = await client.get("/")
    assert response.status == 200
    text = await response.text()
    assert "Tellus" in text


# Test some invalid go link submissions
async def test_route_go_errors(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)
    response = await client.post(R_GO)
    assert response.status == 200, "Should be able to hit /go"
    # Not sure how to test the redirect

    response = await client.post(R_GO, data={"alias": "", "go_url": "whatever"})
    assert response.status == 500, "Should blow up with a blank alias"
    text = await response.text()
    # assert "{\"vfh\": \"http://veryfinehat.com\"}" in text

    response = await client.post(
        R_GO, data={"alias": "BOrked   alias !!#", "go_url": "whatever"}
    )
    assert (
        response.status == 200
    ), "Should be trying to clean up the Alias (maybe overly so?)"
    text = await response.text()
    assert '{"borked-alias": "whatever"}' in text
    assert (
        teller.get("borked-alias").alias == "borked-alias"
    )  # to catch errors on dict insertion upstream


async def test_route_go_with_parameters(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)
    alias = "vfh"
    url = "http://veryfinehat.com"
    response = await client.post(R_GO, data={"alias": alias, "go_url": url})
    assert response.status == 200
    text = await response.text()
    assert '{"vfh": "http://veryfinehat.com"}' in text
    tell = teller.get(alias)
    assert tell.in_category(
        TELLUS_GO
    ), f"These should always end up as a GO Tell: {tell.categories}"
    assert tell.alias == alias
    assert tell.go_url == url


async def test_route_go_links(test_fs, aiohttp_client):
    teller = create_test_teller()

    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)
    response = await client.get(routes.URL_ALL_GO_LINKS)
    assert response.status == 200
    text = await response.text()
    assert text == "{}"

    teller.create_tell("something", TELLUS_INTERNAL, "test_route_go_links")

    alias = "tellus"
    url = "/tellus"
    response = await client.post(R_GO, data={"alias": alias, "go_url": url})
    assert response.status == 200
    text = await response.text()
    assert "tellus" in text
    assert "/tellus" in text
    links = json.loads(text)
    assert links["tellus"] == "/tellus", "This should ONLY return Go links."


async def test_route_tell(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller, Sourcer(teller, [DNSHandler(teller)]))
    tellus_tell = teller.create_tell("tellus", TELLUS_GO, "tellus_test", url="/tellus")

    client = await aiohttp_client(app)
    response = await client.get(f"/{R_TELL}/tellus")
    assert response.status == 200
    text = await response.text()
    assert (
        text
        == '{"alias": "tellus", "go_url": "/tellus", "description": null, "categories": ["tellus-go"], '
        '"tags": [], "groups": [], "data": {"tellus-go": {"go_url": "/tellus"}}, "read-only": false, "z-audit-info": '
        + tellus_tell.audit_info.to_simple_json()
        + "}"
    )

    client = await aiohttp_client(app)
    response = await client.get(f"/{R_TELL}{tellus.wiring.PARAM_SEPARATOR}tellus")
    assert response.status == 200
    new_text = await response.text()
    assert new_text == text, "+ is a valid separator for Tells for debugging purposes."


async def test_route_goto(test_fs, aiohttp_client):
    build_url = "https://build.github.com/#/builders?tags=%2Bresearch&tags=%2Bmaster"
    tellus_url = "https://github.com/"
    # yes, this ends up hitting an external site because of the redirection, for now

    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    teller.create_tell("tellus", TELLUS_GO, "tellus_test", url=tellus_url)

    # try:
    client = await aiohttp_client(app)
    response = await client.get(f"/{R_GO}/tellus")
    assert len(response.history) == 1
    assert response.history[0].status == 302
    assert response.url == URL(
        tellus_url
    ), "Works with an URL without escaped characters..."

    tell = teller.create_tell(
        "research-builds", TELLUS_GO, "tellus_test", url=build_url
    )
    assert tell.go_url == build_url
    response = await client.get(f"/{R_GO}/research-builds")
    assert len(response.history) == 1
    assert response.history[0].status == 302
    assert response.url == URL("https://build.github.com"), (
        "Note this works as we are passing back a location header, "
        "but this will be the URL."
    )
    assert (
        response.history[0].headers["location"] == build_url
    ), "Should retain escaped URL"

    client = await aiohttp_client(app)
    response = await client.get(f"/{R_GO}/nope-nope-nope")
    assert len(response.history) == 1
    assert (
        response.history[0].status == 302
    ), "Retrieving a non-existent Tell should route to #go rather than error out"
    assert response.history[0].headers["location"] == "/#go.nope-nope-nope"

    # Shortcuts!
    assert TellsHandler.retrieve_redirection_url(teller, "tellus", "t") == "/#t.tellus"
    response = await client.get(f"/{R_GO}/crandazzo")


async def test_route_toggle_tag(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)

    response = await client.post(
        routes.TELL_TOGGLE_TAG,
        data={"alias": "notelling", TellsHandler.TELLUS_TOGGLE_TAG: "any-tag"},
    )
    assert response.status == 200
    assert (
        await response.text() == "false"
    ), "Toggling a tag for a non-existent Tell just returns false"

    tell = teller.create_tell("tellus", TELLUS_GO, "tellus_test")

    response = await client.post(
        routes.TELL_TOGGLE_TAG,
        data={"alias": "tellus", TellsHandler.TELLUS_TOGGLE_TAG: "test-tag"},
    )
    assert response.status == 200
    assert tell.has_tag("test-tag")
    assert await response.text() == '{"tellus": ["test-tag", true]}'

    response = await client.post(
        routes.TELL_TOGGLE_TAG,
        data={"alias": "tellus", TellsHandler.TELLUS_TOGGLE_TAG: "test-tag"},
    )
    assert response.status == 200
    assert not tell.has_tag("test-tag")
    assert await response.text() == '{"tellus": ["test-tag", false]}'


async def test_route_links(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)

    teller.create_tell("tellus", TELLUS_GO, "tellus_test", url="/tellus")
    teller.create_tell("dray", TELLUS_LINK, "tellus_test")
    teller.create_tell("some-random-machine", TELLUS_DNS_OTHER, "tellus_test")

    response = await client.get(f"/{R_LINKS}/go")
    assert response.status == 200
    text = await response.text()
    assert text == '{"tellus": "/tellus"}'

    response = await client.get(f"/{R_LINKS}/{ALL_TELLS}")
    assert response.status == 200
    text = await response.text()
    assert text == '{"tellus": "/tellus", "dray": "http://dray.github.com"}'

    # Queries...
    quislet = teller.create_tell("quislet", TELLUS_GO, "tellus_test", url="/quislet")
    quislet.add_tags(["tellus", "spaceship"])

    await assert_response_text(
        client, f"/{R_LINKS}/aq-link", '{"dray": "http://dray.github.com"}'
    )
    await assert_response_text(
        client, f"/{R_LINKS}/go", '{"quislet": "/quislet", "tellus": "/tellus"}'
    )
    await assert_response_text(
        client,
        f"/{R_LINKS}/{TELLUS_GO}",
        '{"quislet": "/quislet", "tellus": "/tellus"}',
    )
    await assert_response_text(
        client, f"/{R_LINKS}/.spaceship", '{"quislet": "/quislet"}'
    )
    await assert_response_text(
        client, f"/{R_LINKS}/tellus", '{"quislet": "/quislet", "tellus": "/tellus"}'
    ), "Note - you are searching by tags, which includes aliases"
    await assert_response_text(
        client, f"/{R_LINKS}/{TELLUS_GO}.spaceship", '{"quislet": "/quislet"}'
    )

    all_non_dns_tells = (
        '{"quislet": "/quislet", "tellus": "/tellus", "dray": "http://dray.github.com"}'
    )
    await assert_response_text(client, f"{R_LINKS}/", all_non_dns_tells)
    await assert_response_text(client, f"{R_LINKS}/.", all_non_dns_tells)


async def test_route_tell_delete(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    tellus_tell = teller.create_tell("tellus", TELLUS_GO, "tellus_test", url="/tellus")
    quislet_tell = teller.create_tell(
        "quislet", TELLUS_GO, "tellus_test", url="http://quislet.com"
    )

    assert teller.tells_count() == 2

    client = await aiohttp_client(app)
    response = await client.get(f"/{R_TELL}/quislet/{tellus.wiring.TELL_DELETE}")
    assert response.status == 200
    text = await response.text()
    assert (
        text
        == 'DELETED TELL \'quislet\': {"alias": "quislet", "go_url": "http://quislet.com", "description": null, "categories": ["tellus-go"], "tags": [], "groups": [], "data": {"tellus-go": {"go_url": "http://quislet.com"}}, "read-only": false, "z-audit-info": '
        + quislet_tell.audit_info.to_simple_json()
        + "}"
    )

    assert teller.tells_count() == 1
    try:
        teller.get("quislet")
        pytest.fail("Quislet should be no more.")
    except TheresNoTellingException:
        pass
    assert teller.get("tellus") == tellus_tell

    response = await client.get(f"/{R_TELL}/tellus/{tellus.wiring.TELL_DELETE}")
    assert response.status == 200
    text = await response.text()
    assert (
        text
        == 'DELETED TELL \'tellus\': {"alias": "tellus", "go_url": "/tellus", "description": null, "categories": ["tellus-go"], "tags": [], "groups": [], "data": {"tellus-go": {"go_url": "/tellus"}}, "read-only": false, "z-audit-info": '
        + tellus_tell.audit_info.to_simple_json()
        + "}"
    )


async def test_route_tell_update(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)

    response = await client.post(routes.URL_TELL_UPDATE, data={"alias": "notelling"})
    assert response.status == 500

    tellus_tell = teller.create_tell("tellus", TELLUS_GO, "tellus_test", url="/tellus")
    teller.create_tell("quislet", TELLUS_GO, "tellus_test", url="http://quislet.com")

    assert teller.tells_count() == 2

    update_data = {
        Tell.ALIAS: "tellus",
        Tell.DESCRIPTION: "I am Tellus, hear me roar.",
        Tell.TAGS: "dc, tellus",
        Tell.GO_URL: "http://tellus.github.com",
    }
    response = await client.post(routes.URL_TELL_UPDATE, data=update_data)
    assert response.status == 200
    text = await response.text()
    tell_dict = json.loads(text)
    assert (
        tell_dict.pop("z-audit-info") is not None
    ), "Just verifying the audit info is there but not the actual data"
    assert tell_dict == {
        "alias": "tellus",
        "categories": ["tellus-go", "tellus-user"],
        "data": {
            "tellus-go": {"go_url": "/tellus"},
            "tellus-user": {
                "alias": "tellus",
                "description": "I am Tellus, hear me roar.",
                "go_url": "http://tellus.github.com",
                "source-tags": "dc, tellus",
            },
        },
        "description": "I am Tellus, hear me roar.",
        "go_url": "http://tellus.github.com",
        "groups": [],
        "read-only": False,
        "tags": ["dc", "tellus"],
    }
    assert tellus_tell.description == "I am Tellus, hear me roar."
    assert tellus_tell.tags == ["dc", "tellus"]
    assert tellus_tell.go_url == "http://tellus.github.com"

    update_data = {
        Tell.ALIAS: "tellus",
        Tell.GO_URL: "/tellus/again",
        Tell.TAGS: "dc",
    }
    response = await client.post(routes.URL_TELL_UPDATE, data=update_data)
    assert response.status == 200
    text = await response.text()
    assert (
        tellus_tell.description == "I am Tellus, hear me roar."
    ), "Not passing an attribute should leave it alone."
    assert tellus_tell.go_url == "/tellus/again"
    assert tellus_tell.tags == [
        "dc"
    ], "Passing a shorter tag list should remove the other tags."


async def test_route_sources(test_fs, aiohttp_client):
    teller = create_test_teller()
    sourcer = Sourcer(
        teller, [DNSHandler(teller), TellusYMLSource(teller), FakeSource()]
    )
    app = create_and_load_test_webapp(teller, sourcer)

    client = await aiohttp_client(app)
    response = await client.get(f"/sources")
    assert response.status == 200
    text = await response.text()
    sources = json.loads(text)
    assert len(sources) == 3
    assert list(sources.keys()) == [
        "tellus-aq-dns",
        "tellus-aq-tool",
        "testing-source",
    ], "Should have these three sources - note the order is preserved."


async def test_route_dns_links(test_fs, aiohttp_client):
    teller = create_test_teller()

    app = create_and_load_test_webapp(teller)
    client = await aiohttp_client(app)
    response = await client.get(f"{R_LINKS}/" + TELLUS_LINK)
    assert response.status == 200
    text = await response.text()
    assert text == "{}"


async def test_dns_links(test_fs, aiohttp_client, mock_session):
    def mock_get(url, **kwargs):
        matcher = re.compile("http://(.*).github.com")
        if matcher.match(url):
            return make_mock_response("YAY", 200)
        return make_mock_response(SAMPLE_SHORT_DNS_FILE, 200)

    mock_session.get.side_effect = mock_get

    teller = create_test_teller()
    teller.persist()  # Just to ensure we have an empty file.

    app = create_and_load_test_webapp(teller, Sourcer(teller, [DNSHandler(teller)]))
    # This is obviously terrible, but has been the best approach to getting this to run:
    await asyncio.sleep(4)

    assert teller.tells_count() == 4, "Only Links should have been added..."
    assert teller.tells_count(TELLUS_DNS) == 4, "Everything added to DNS"
    assert teller.tells_count(TELLUS_DNS_OTHER) == 0, "No longer adding DNS_OTHER"
    assert teller.tells_count(TELLUS_LINK) == 4, "4 are active internal links"

    client = await aiohttp_client(app)
    response = await client.get(f"{R_LINKS}/aq-link")
    assert response.status == 200
    dns_links = await response.text()
    added_links = '{"docs": "http://docs.github.com", "drone": "http://drone.github.com", "home": "http://home.github.com", "dray": "http://dray.github.com"}'
    assert dns_links == added_links


async def test_route_run_source(aiohttp_client):
    teller = create_test_teller()
    source = FakeSource("test-route-run-source", "Testing the run_source route")
    sourcer = Sourcer(teller, [source])
    app = create_and_load_test_webapp(teller, sourcer)

    client = await aiohttp_client(app)
    response = await client.get(f"{R_SOURCES}/test-route-run-source/load")
    assert response.status == 200
    response = await response.text()
    assert response == "Load started for source test-route-run-source"

    client = await aiohttp_client(app)
    response = await client.get(f"{R_SOURCES}/not_a_source/load")
    assert response.status == 500


###
# Test Tell Handler
###
def create_test_tellus_handler(teller=None, user_manager=None):
    if teller is None:
        teller = create_test_teller()

    if user_manager is None:
        user_manager = UserManager(teller, [TELLUS_TEST_USER])

    return TellsHandler(teller, user_manager)


def assert_query_results(handler, results_dicts, query_string):
    mock_request = MagicMock(web.Request)
    mock_request.match_info = {TellsHandler.PARAM_QUERY_STRING: query_string}

    tells_result = {tell_dict["alias"]: tell_dict for tell_dict in results_dicts}
    links_result = {alias: tells_result[alias]["go_url"] for alias in tells_result}

    # These all return ~equivalent results
    assert json.loads(handler.query_links(mock_request).text) == links_result
    assert (
        handler.query_for(request=mock_request, tell_repr_method="go_url")
        == links_result
    )

    # As do these...
    assert json.loads(handler.query_tells(mock_request).text) == tells_result
    assert handler.query_for(request=mock_request) == tells_result


def test_query_for():
    teller = create_test_teller()
    handler = create_test_tellus_handler(teller)

    tell_alias = teller.create_tell(
        "alias investigations",
        tellus.configuration.TELLUS_INTERNAL,
        "tells_test",
        url="https://marvel.fandom.com/wiki/Alias_Investigations_(Earth-616)",
    )
    tell_alias.add_tag("marvel")
    alias_dict = {
        "alias": "alias-investigations",
        "go_url": "https://marvel.fandom.com/wiki/Alias_Investigations_(Earth-616)",
        "description": None,
        "categories": [TELLUS_INTERNAL],
        "tags": ["marvel"],
    }

    tell_quislet = teller.create_tell(
        "quislet",
        tellus.configuration.TELLUS_INTERNAL,
        "tells_test",
        url="http://something.com",
        description="Quislet!",
    )
    tell_quislet.add_tag("dc")
    quislet_dict = {
        "alias": "quislet",
        "go_url": "http://something.com",
        "description": "Quislet!",
        "categories": [TELLUS_INTERNAL],
        "tags": ["dc"],
    }

    tell_tellus = teller.create_tell(
        "tellus", TELLUS_GO, "tells_test", url="/tellus", description="I am Tellus."
    )
    tell_tellus.add_tags(["dc", "tellus"])
    tellus_dict = {
        "alias": "tellus",
        "go_url": "/tellus",
        "description": "I am Tellus.",
        "categories": [TELLUS_GO],
        "tags": ["dc", "tellus"],
    }

    tell_dray = teller.create_tell("dray", TELLUS_LINK, "tells_test")
    tell_dray.add_tags(["othertag"])
    dray_dict = {
        "alias": "dray",
        "go_url": "http://dray.github.com",  # Derived...
        "description": None,
        "categories": [TELLUS_LINK],
        "tags": ["othertag"],
    }

    all_tells_result = [
        alias_dict,
        quislet_dict,
        tellus_dict,
        dray_dict,
    ]
    assert_query_results(handler, all_tells_result, None)

    # categories
    assert_query_results(handler, [tellus_dict], TELLUS_GO)
    assert_query_results(handler, [tellus_dict], "go")

    assert_query_results(handler, [dray_dict], TELLUS_LINK)
    assert_query_results(handler, [dray_dict], "aq-link")

    # tags
    assert_query_results(handler, [tellus_dict], "tellus")
    assert_query_results(handler, [tellus_dict], ".tellus")
    assert_query_results(handler, [quislet_dict, tellus_dict], "dc")
    assert_query_results(handler, [quislet_dict, tellus_dict], ".dc")
    assert_query_results(handler, [tellus_dict], f".dc.{TELLUS_GO}")

    # Checking alias cleaning
    assert_query_results(handler, [alias_dict], f"alias-investigations")
    assert_query_results(handler, [alias_dict], f"alias+investigations")


def test_search_for():
    teller = create_test_teller()
    handler = create_test_tellus_handler(teller)
    create_search_tells(teller, "test_search_for")

    mock_request = MagicMock(web.Request)

    for search_term in SEARCH_TERM_MATCHES:
        expected_aliases = SEARCH_TERM_MATCHES[search_term]
        mock_request.match_info = {TellsHandler.PARAM_SEARCH_STRING: search_term}

        results = handler.search_for(mock_request)
        assert len(json.loads(results.text)) == len(expected_aliases)

    # Cheating.  But easier than getting Mock to raise an exception:
    mock_request.match_info = {}
    results = handler.search_for(mock_request)
    assert (
        len(json.loads(results.text)) == teller.tells_count()
    ), f"Should have returned all Tells but returned: {results.text}"


async def test_route_search(test_fs, aiohttp_client):
    teller = create_test_teller()
    app = create_and_load_test_webapp(teller)
    create_search_tells(teller, "test_search_for")

    client = await aiohttp_client(app)

    response = await client.get(f"/{R_SEARCH}/")
    assert response.status == 200
    text = await response.text()
    assert len(json.loads(text)) == teller.tells_count()

    response = await client.get(f"/{R_SEARCH}/board")
    assert response.status == 200
    text = await response.text()
    assert len(json.loads(text)) == 4  # Yes, fragile


def test_tellus_save_file(fs):
    teller = create_test_teller()
    handler = create_test_tellus_handler(teller)

    assert (
        handler.save_file().text
        == f"No save file currently exists at: {teller.persistence_file()}"
    )

    file = teller.persistence_file()
    save_file = create_current_save_file()
    fs.create_file(file, contents=save_file)

    assert save_file == handler.save_file().text


def test_add_debug_route(this_test_name):
    teller = create_test_teller()
    handler = create_test_tellus_handler(teller)
    router = MagicMock()
    fake_function = MagicMock()

    assert teller.tells_count() == 0
    handler.add_debug_route("No Tell", router, "test url no telling", fake_function)
    assert teller.tells_count() == 0, "This doesn't add Tells."
    router.add_get.assert_called_with(
        "test url no telling", fake_function
    )  # But should have added the route
    assert handler.debug_urls == {"No Tell": "tellus:test url no telling"}

    teller.create_tell("test-tell", TELLUS_INTERNAL, this_test_name)
    tell = teller.get("test-tell")
    assert (
        tell.get_data(handler.TELLUS_DEBUG_SOURCE) is None
    ), "Random Tell should not have debugging data"

    teller.create_tell(TELLUS_ABOUT_TELL, TELLUS_INTERNAL, this_test_name)
    tell = teller.get(TELLUS_ABOUT_TELL)
    assert (
        tell.get_data(handler.TELLUS_DEBUG_SOURCE) is None
    ), "debugging data is transient - so WON'T come from the Teller"

    tell = handler._retrieve_tell(TELLUS_ABOUT_TELL)
    assert (
        tell.get_datum(handler.TELLUS_DEBUG_SOURCE, "No Tell")
        == "tellus:test url no telling"
    ), "Our debugging tell should get decorated with the transient info when retrieved from the Handler."


async def test_toggle_tag(this_test_name):
    teller = create_test_teller()

    try:
        teller.toggle_tag("test", "test_tag")
        pytest.fail("Toggling a tag for a non-existent Tell should throw an exception.")
    except TheresNoTellingException:
        pass

    teller.create_tell("test", TELLUS_INTERNAL, this_test_name)
    result = teller.toggle_tag("test", "test_tag")
    assert result, "Successfully toggling the tag returns a result that equates to true"
    assert result == "test_tag", "Successfully toggling the tag returns the tag"
    assert teller.get("test").tags == ["test-tag"]

    result = teller.toggle_tag("test", "test-tag-2")
    assert result == "test-tag-2", "Successfully toggling the tag returns the tag"
    assert teller.get("test").tags == [
        "test-tag",
        "test-tag-2",
    ], "Toggling a new tag adds it"

    result = teller.toggle_tag("test", "test-tag")
    assert teller.get("test").tags == [
        "test-tag-2"
    ], "Toggling an existing tag removes it"
    assert not result, "Successfully toggling the tag off returns a False equivalent"
    assert result is None, "Successfully toggling the tag off returns None"


async def test_this_test_name(this_test_name):
    # Just gonna leave this here...
    assert this_test_name == "test_this_test_name"
