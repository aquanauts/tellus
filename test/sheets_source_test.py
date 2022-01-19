# pylint: skip-file
#   lots of stuff pylint doesn't like in here that is particular to these tests
import io
import pytest
from unittest import mock

from sortedcontainers import SortedSet

from tellus.tell import InvalidAliasException, Tell
from tellus.configuration import TELLUS_INTERNAL, TELLUS_SHEET_SPEC, TELLUS_SOURCED
from tellus.tells import DuplicateTellException
from tellus.tellus_sources.google_sheets_source import (
    Sheet,
    GoogleSheetsSource,
    SheetParser,
)
from test.tellus_test_utils import this_test_name
from test.tells_test import create_test_teller
import pandas as pd

# The names of the Tellus test sheets, which map to a real sheet - see test_real_api_interaction.py
# These names are short too make the CSVs below a little easier to work with
TELLUS_TEST_TAB_0 = "TTest0"
TELLUS_TEST_TAB_1 = "TTest1"
TELLUS_TEST_TAB_2 = "TTest2"

# A fairly basic sheet, both here and for reals
TELLUS_TEST_TAB_1_DATA = """
Name,Summary,User 1,User 2,Secret Identity,Website,Tags,Start Date,End Date,Other URL
saturn girl,A founder,Imra Ardeen,,,http://saturngirl.com,"saturn, founder",,,
cosmic boy,A founder,Rokk Krinn,,,http://thelegion.org,founder,,,
lightning_lad,A founder,gganzz,,,http://thelegion.org,founder,,,
quislet,A little weird ship,,,,http://thelegion.org,"mysterious, little ship",,,
,A horse with no name,,,,,bad horse,,,
"""

# This sheet may look basic here as a csv, but it will have more complex stuff going on in the real one,
# to validate that we can handle any weirdnesses coming back from the sheets API
VALID = MORDRU = "mordru"
VALID_GROUPING = FATAL_FIVE = "fatal-five"
TELLUS_TEST_TAB_2_DATA = """
Record Name,Some Column,Some Other Column,Tellus Alias,Villain Powers,Description,URL,Alias,Comments/Invalidity
Valid Record,Some Data,Some Other Data,Mordru,Magic,Bad Sorcerer,http://www.badsorcerer.com,Wrynn,
Valid Grouping,Also Some Data,Also Some Other Data,Fatal Five,Various,Evil League of Evil,,,
Invalid No Alias,Also Also Some Data,Also Also Some Other Data,,Unknown,Thoroughbred of Sin,,Bad Horse,No mapped Tellus Alias
Invalid Duplicate,Also Also Also Some Data,Also Also Also Some Other Data,          mordru       ,Magic,Also also a bad sorcerer,http://nottheone.com,,A duplicate alias
Invalid Empty,,,,,,,,A mostly empty row
"""
INVALID_RECORDS = 3
VALID_RECORDS = 2

# Our config.  Will get all columns into data
TELLUS_TEST_SHEET_CONFIG_NORMAL = """
Sheet,Column,TellusProperty,TellusType,,Comments,,,,,GENERAL NOTES
TTest1,Name,alias,,,Note the lack of type - it will be ignored for Tellus properties other than data,,,,,"Note also in this sheet, anything other than the ""main"" columns will be ignored (like this comments column)"
TTest1,Summary,description,,,Note the lack of type - it will be ignored for Tellus properties other than data,,,,,"Also, note the data validation trick for the columns."
TTest1,User 1,data,user,,"This goes into the data block, but Tellus will try to turn it into a User",,,,,ORDER MATTERS - once Tellus finds a value for a property (other than Data) it will shove everything else into Data
TTest1,User 2,data,user,,"This goes into the data block, but Tellus will try to turn it into a User",,,,,
TTest1,Website,go-url,,,,,,,,
TTest1,Start Date,data,date,,,,,,,
TTest1,End Date,data,date,,,,,,,
TTest1,Other URL,,,,"Technically if this just contains URL as a text, this should work (Tellus will later try to turn it into a link)",,,,,
TTest1,,,,,This row intentionally left blank,,,,,
TTest1,Name,go-url,linked-text,,[NOT IMPLEMENTED YET] This is a special Tellus Type that tries to extract a URL from linked text. ,,,,,
TTest2,Tellus Alias,alias,,,,,,,,
TTest2,Description,description,text,,,,,,,
TTest2,Tellus Alias,alias,,,An intentional duplicate  - should basically be ignored?,,,,,
TTest2,URL,go-url,text,,,,,,,"""

# Restrict to only specified columns
TELLUS_TEST_SHEET_CONFIG_RESTRICTED = (
    TELLUS_TEST_SHEET_CONFIG_NORMAL
    + f"""
TTest1,Get All Data,data,only-specified
TTest2,Get All Data,data,only-specified
"""
)

TELLUS_TEST_SHEET_CONFIG_BAD = """
Sheet,Column,Tellus Property,Tellus Type
Tellus Test,Name,alias,
Tellus Test,Summary,description,
Tellus Test,User 1,data,user
Tellus Test,User 2,data,user
Tellus Test,Website,go-url,
Tellus Test,Start Date,data,date
Tellus Test,End Date,data,date
Tellus Test,Other URL,,
Tellus Test,,,
Tellus Test,,data,only-specified
Tellus Test,Name,go-url,linked-text
"""  # TODO: make worse for testing


def test_create_sheet():
    teller = create_test_teller()
    sheet = Sheet.create(teller, "test", sheet_url="test-id")
    assert sheet.alias == "test"
    assert sheet.sheet_url == "test-id"


def test_get_sheet_tells(this_test_name):
    teller = create_test_teller()
    teller.create_tell("test-not-sheet", TELLUS_INTERNAL, this_test_name)
    sheet_tell = teller.create_tell("test-sheet", TELLUS_SHEET_SPEC, this_test_name)

    sheet_source = GoogleSheetsSource(teller)
    sheets = sheet_source.get_sheets()
    assert len(sheets) == 1
    assert sheets[0].tell == sheet_tell

    # tools_sheet = construct_tools_sheet(teller)
    # sheets = sheet_source.get_sheets()
    # assert len(sheets) == 2
    # assert tools_sheet.sheet_url == GoogleSheetsSource.TOOLS_SHEET_URL
    # assert tools_sheet.tab == GoogleSheetsSource.TOOLS_MAIN_TAB


@pytest.mark.skip(
    reason="Need to rework these with revised tests from the smoke tests."
)
def test_construct_tell_basic():
    teller = create_test_teller()
    sheet = Sheet.create(teller, "minimal-sheet-tell-for-now", sheet_url="fake")
    record = TELLUS_TEST_TAB_2_DATA[VALID]

    constructed_tell = sheet.construct_tell(record, teller)
    assert teller.get(MORDRU) == constructed_tell
    assert constructed_tell.get_data(GoogleSheetsSource.SOURCE_ID) == record
    assert (
        constructed_tell.has_no_properties()
    ), "By default, Tellus will not map any data to properties, even if they have the same names"

    try:
        sheet.construct_tell(TELLUS_TEST_TAB_2_DATA["Invalid Empty"], teller)
        pytest.fail(
            "Trying to construct Tell from a blank record will result in an Invalid Alias exception"
        )
    except InvalidAliasException:
        pass

    try:
        sheet.construct_tell(TELLUS_TEST_TAB_2_DATA["Invalid No Alias"], teller)
        pytest.fail(
            "Trying to construct Tell from a record without the mapped alias column "
            "will result in an Invalid Alias exception"
        )
    except InvalidAliasException:
        pass

    try:
        sheet.construct_tell(TELLUS_TEST_TAB_2_DATA["Invalid Duplicate"], teller)
        pytest.fail(
            "Trying to construct Tell with a duplicate alias will fail with a Duplicate Tell Exception"
        )
    except DuplicateTellException:
        pass


@pytest.mark.skip(
    reason="Need to rework these with revised tests from the smoke tests."
)
async def test_test_sheet_load():
    teller = create_test_teller()
    sheet = Sheet.create(teller, "test-sheet", sheet_url="Test")
    source = GoogleSheetsSource(teller)
    with mock.patch.object(Sheet, "retrieve_records") as mocked_retrieve:
        mocked_retrieve.return_value = TELLUS_TEST_TAB_2_DATA.values()

        assert teller.tells_count() == 1
        results = source.test_sheet_load(sheet)
        assert len(results) == VALID_RECORDS
        assert teller.tells_count() == 1


# async def test_google_sheet_source():
#     teller = create_test_teller()
#     sheet = Sheet.create(teller, "test-sheet", sheet_url="Test")
#     source = GoogleSheetsSource(teller)
#     with mock.patch.object(Sheet, "retrieve_records") as mocked_retrieve:
#         mocked_retrieve.return_value = TEST_RECORDS.values()
#
#         assert teller.tells_count() == 1
#         await source.load_source()
#         assert list(teller.query_tells().keys()) == [
#             "fatal-five",
#             "mordru",
#             "test-sheet",
#         ]


def configify(tab_name, config_data):
    df = pd.read_csv(io.StringIO(config_data))
    column_config = Sheet.tab_config(tab_name, df)
    return column_config


@pytest.mark.skip(
    reason="Need to rework these with revised tests from the smoke tests."
)
def test_sheet_parser():
    parser = SheetParser(configify(TELLUS_TEST_TAB_1, TELLUS_TEST_SHEET_CONFIG_NORMAL))
    assert not parser.should_load_all_data

    parser = SheetParser(
        configify(TELLUS_TEST_TAB_1, TELLUS_TEST_SHEET_CONFIG_RESTRICTED)
    )
    assert parser.should_load_all_data

    tab_df = pd.read_csv(io.StringIO(TELLUS_TEST_TAB_1_DATA))
    asserts_test_sheet_parser(tab_df, parser)


def asserts_test_sheet_parser(tab_df, parser):
    saturn_girl = tab_df.iloc[0]
    tell_dict = parser.parse(saturn_girl)
    assert tell_dict == {
        Tell.ALIAS: "saturn-girl",
        Tell.DESCRIPTION: "A founder",
        Tell.GO_URL: "saturn-girl",
        Tell.TAGS: "saturn, founder",
        "User 1": "Imra Ardeen",
        SheetParser.duplicate_key(Tell.GO_URL, "Website"): "http://saturngirl.com",
    }
    # Note with "Website" that the order in which things make it in are dependent on the COLUMN
    # order, not the order in the config sheet


@pytest.mark.skip(
    reason="Need to rework these with revised tests from the smoke tests."
)
def test_load_tab_basics():
    config = configify("Tellus Test", TELLUS_TEST_SHEET_CONFIG_RESTRICTED)
    data = pd.read_csv(io.StringIO(TELLUS_TEST_TAB_1_DATA))

    teller = create_test_teller()

    invalid_records = Sheet.load_tab(
        teller, TELLUS_TEST_TAB_1, data, config, "test_load_tab"
    )

    assert len(invalid_records) == 1

    assert teller.tells_count() == 4
    assert teller.aliases == ["cosmic-boy", "lightning-lad", "quislet", "saturn-girl"]
    saturn_girl = teller.get("saturn-girl")
    assert saturn_girl.categories == [TELLUS_SOURCED]


# def test_load_tab_complex():
#     teller = create_test_teller()
#     sheet = Sheet.create(teller, "test-sheet", sheet_url="Test")
#     test_df = pd.DataFrame(TELLUS_TEST_TAB_2_DATA)
#     test_config_df = configify("Tellus Test Complex", TEST_RECORDS_COMPLEX_CONFIG)
#     invalid_records = Sheet.load_tab(
#         teller, TELLUS_TEST_TAB_2, test_df, test_config_df, "test_load_tab_complex"
#     )  # Should pass even with invalid records
#
#     assert (
#         len(invalid_records) == INVALID_RECORDS
#     ), f"TEST_RECORDS currently contains {INVALID_RECORDS} invalid records."
#     assert (
#         teller.tells_count() - 1 == VALID_RECORDS  # -1 for the Sheet
#     ), f"TEST_RECORDS should generate {VALID_RECORDS} tells."
#
#     mordru = teller.get(MORDRU)
#     assert (
#         mordru.get_data(GoogleSheetsSource.SOURCE_ID) == TELLUS_TEST_TAB_2_DATA[MORDRU]
#     )
#
#     fatal_five = teller.get(FATAL_FIVE)
#     assert (
#         fatal_five.get_data(GoogleSheetsSource.SOURCE_ID)
#         == TELLUS_TEST_TAB_2_DATA[FATAL_FIVE]
#     )
