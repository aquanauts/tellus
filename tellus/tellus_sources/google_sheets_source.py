from tellus.google_api_utils import get_spreadsheet_by_url
from tellus.sources import Source
from tellus.tell import Tell, TellWrapper, InvalidAliasException
from tellus.tells import Teller
from tellus.configuration import (
    TELLUS_APP_USERNAME,
    TELLUS_SHEET_SPEC,
    TELLUS_SOURCED,
)
import pandas as pd

from tellus.tellus_utils import TellusException


class InvalidSheetConfig(TellusException):
    def __init__(self, sheet_alias, additional_message=""):
        TellusException.__init__(
            self,
            f"There was an error processing sheet '{sheet_alias}'. {additional_message}",
        )


class Sheet(TellWrapper):
    """
    A convenience wrapper around a Tell that represents a Google Sheet with more semantically clear names inside Tellus.
    It is intentionally READ ONLY to prevent risk of writing dta back to the sheet unintentionally.
    """

    _TAB_NAME = "tab-name"
    _DEFAULT_TELLUS_ALIAS_COLUMN = "Tellus Alias"

    _CONFIG_SHEET = "tellus-sheet-config"
    _CONFIG_COLUMNS = ["Sheet", "Column", "TellusProperty", "TellusType"]

    INVALID_RECORD = "record"
    INVALID_ERROR = "error"

    @staticmethod
    def create(teller, alias, *, sheet_url):
        sheet = Sheet(
            teller.create_tell(
                alias, TELLUS_SHEET_SPEC, TELLUS_APP_USERNAME, url=sheet_url
            ),
        )

        return sheet

    def __init__(self, sheet_tell):
        super().__init__(sheet_tell, "Sheet", GoogleSheetsSource.SOURCE_ID)

        self._spreadsheet = None

    @property
    def sheet_url(self):
        return self._tell.go_url

    @property
    def _gsheet(self):
        """
        Create the google sheet representation for us - lazily loaded, will cache it after the first retrieval.
        """
        if self._spreadsheet is None:
            self._spreadsheet = get_spreadsheet_by_url(self.sheet_url)
        return self._spreadsheet

    def _retrieve_records_for_tab(self, sheet_tab):
        tab = self._gsheet.worksheet(sheet_tab)
        return tab.get_all_records()

    def retrieve_sheet_config(self):
        """
        :return: a Pandas Dataframe of the config sheet.
        """
        return self._retrieve_records_for_tab(Sheet._CONFIG_SHEET)

    @staticmethod
    def tab_config(tab, config_df):
        return config_df.loc[config_df.Sheet == tab][Sheet._CONFIG_COLUMNS[1:]]

    def load_from_google_sheet(self, teller, specific_tab=None):
        """
        The main loading method for the Sheet.  Loads all data from the Google Sheet into the specified Teller.
        """
        config_df = pd.DataFrame(self.retrieve_sheet_config())
        tab_dfs = {}
        specified_tabs = config_df.Sheet.unique()
        for tab_name in specified_tabs:
            if specific_tab is None or tab_name == specific_tab:
                tab_dfs[tab_name] = pd.DataFrame(
                    self._retrieve_records_for_tab(tab_name)
                )

        return self.load_all_tabs(teller, tab_dfs, config_df, self._tell.alias)

    def load_all_tabs(self, teller, tab_dfs, config_df, source_id):
        all_tab_invalid_records = {}

        for tab_name, tab_df in tab_dfs.items():
            tab_config_df = self.tab_config(tab_name, config_df)
            invalid_records = self.load_tab(
                teller, tab_name, tab_df, tab_config_df, source_id
            )
            if len(invalid_records) > 0:
                all_tab_invalid_records[tab_name] = invalid_records

        return all_tab_invalid_records

    @staticmethod
    def load_tab(teller, tab_name, tab_df, tab_config_df, source_id):
        parser = SheetParser(tab_config_df)
        invalid_records = []

        for index, tell_row in tab_df.iterrows():
            try:
                tell_dict = parser.parse(tell_row, tab_name)
                if Tell.ALIAS not in tell_dict.keys():
                    # Mostly to ensure a more useful exception.
                    raise InvalidAliasException(
                        "[No Alias]", "No alias was parsed from this record."
                    )
                teller.create_tell_from_dict(TELLUS_SOURCED, tell_dict, source_id)
            except Exception as e:
                invalid_records.append(
                    {Sheet.INVALID_RECORD: tell_row.to_dict(), Sheet.INVALID_ERROR: e}
                )

        return invalid_records


class SheetParser:
    """
    Wraps a config dataframe, and then uses it to parse out a row of data into a Tell.
    """

    _ONLY_SPECIFIED = "only-specified"
    _USER = "user"
    _DATE = "date"
    _LINKED_TEXT = "linked-text"
    _PARSERS = []  # _USER, _DATE, _LINKED_TEXT]
    _TEXT = "text"

    _DATA = "data"
    _SEPARATOR = " | "

    def __init__(self, config_columns_df):
        self._config_df = config_columns_df
        self._config_df.set_index("Column", inplace=True)

        self._all_data = (
            SheetParser._ONLY_SPECIFIED not in config_columns_df.TellusType.unique()
        )

    @property
    def should_load_all_data(self):
        return self._all_data

    def parse(self, row_series, tab_name):
        """
        Parsing rules:
            - If the column has property specs iterate through them until you find a valid value, and use that.
            - If more than one value for a property, shove it in the data map with information on it being a dupe
            - If _all_data is false, ignore anything else that does not have an explicit spec.
            - If it is True...
            - If there are no property specs BUT a cell's name matches a property (e.g., Description, Tags)
                treat the value as that property.
            - Otherwise, it goes in the data block.
        """
        tell_dict = {}

        for cell in row_series.iteritems():
            column_name = cell[0]
            cell_value = cell[1]

            if SheetParser._valid_value(cell_value):
                # todo: suppress if not all data
                datum_name = f"{tab_name}{SheetParser._SEPARATOR}{column_name}"
                tell_dict[datum_name] = cell_value

                try:
                    property_specs = self._config_df.loc[[column_name]].to_dict(
                        "records"
                    )
                except KeyError:
                    property_specs = (
                        []
                    )  # We'll ignore everything else, if we don't have a specific spec

                for property_spec in property_specs:
                    tell_property = property_spec["TellusProperty"]

                    # todo: check is a property, handle go-url junk

                    if (
                        tell_property == Tell.ALIAS
                    ):  # Aliases are always a little special
                        cell_value = Tell.clean_alias(cell_value)

                    # todo: handle other properties...tags, mostly

                    if tell_dict.get(tell_property, None) is None:
                        tell_dict[tell_property] = cell_value
                    else:
                        tell_dict[
                            SheetParser.duplicate_key(tell_property, column_name)
                        ] = cell_value

        return tell_dict

    @staticmethod
    def _valid_value(cell_value):
        """
        Is the value of this cell one that Tellus would consider valid for grabbing?
        """
        return cell_value is not None and (not pd.isna(cell_value)) and cell_value != ""

    @staticmethod
    def duplicate_key(datum_name, column_name):
        return f"{datum_name} [DUPLICATE VALUE FROM COLUMN '{column_name}']"


class GoogleSheetsSource(Source):
    SOURCE_ID = "google-sheets"
    SHEET_ID = "sheet-id"

    def __init__(self, teller: Teller):
        super().__init__(
            teller, source_id=GoogleSheetsSource.SOURCE_ID, description="Google Sheets"
        )

    async def load_source(self):
        sheets = self.get_sheets()
        for sheet in sheets:
            sheet.load_from_google_sheet(self.teller, self.source_id)

    @staticmethod
    def construct_tells(sheet, records, teller):
        invalid_records = []
        for record in records:
            try:
                sheet.construct_tell(record, teller)
            except RuntimeError as e:
                invalid_records.append({"record": record, "exception": repr(e)})
        return invalid_records

    def _sheet_load(self, sheet, teller):
        records = sheet.retrieve_records()
        self.construct_tells(sheet, records, teller)

    def test_sheet_load(self, sheet):
        """
        Do a test run of parsing a sheet and return the collection of Tells it would create.  This is used
        for initial sheet specification and testing of the results.

        :param sheet:  the sheet to load
        :return: a collection of *transient* tells that the sheet would construct if it were really loaded.
        """
        transient_teller = Teller(None)  # Kids, don't try this at home...
        self._sheet_load(sheet, transient_teller)
        return transient_teller.tells()

    def get_sheets(self) -> [Sheet]:
        return [
            Sheet(sheet_spec) for sheet_spec in self.teller.tells(TELLUS_SHEET_SPEC)
        ]
