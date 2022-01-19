import logging

import yaml

from tellus.configuration import (
    GITHUB_URL,
    TELLUS_PREFIX,
    TELLUS_INTERNAL,
    TELLUS_TOOL,
    TELLUS_TOOL_RELATED,
)
from tellus.tellus_sources.github_helper import download_github_file, gethub
from tellus.sources import Source
from tellus.tell import Tell
from tellus.tellus_utils import TellusException

GITHUB_REPO_DATUM = "github-repo"

TELLUS_CONFIG_TOOLS = TELLUS_PREFIX + "config-tools"


class TellusYMLSource(Source):
    SOURCE_ID = TELLUS_TOOL
    VALID_TELLUS_FILE_NAMES = [
        "tellus.yml",
        ".tellus.yml",
        "tellus.yaml",
        ".tellus.yaml",
    ]
    IGNORE_MARKER = "tellus-ignore"

    def __init__(self, teller):
        super().__init__(
            teller, source_id=TellusYMLSource.SOURCE_ID, description="tellus.yml files"
        )
        self._tool_config = None  # This guy is lazy loaded..

    def _handle_secondary_yml_tell(self, yml_dict, repo_path_name, primary_tell):
        alias = yml_dict[Tell.ALIAS]
        if alias.startswith("-"):
            alias = primary_tell.alias + alias
            yml_dict[Tell.ALIAS] = alias

        return self._handle_yml_tell(
            alias, yml_dict, repo_path_name, TELLUS_TOOL_RELATED, primary_tell
        )

    def _handle_yml_tell(
        self, alias, yml_dict, repo_path_name, category, primary_tell=None
    ):
        if yml_dict.get(self.IGNORE_MARKER):
            logging.info(
                "Yaml entry was marked to be ignored.  Skipping it.  Data: %s",
                yml_dict,
            )
            return None

        tell = self.teller.get_or_create_tell(
            raw_alias=alias, category=category, created_by=self.source_id
        )
        tell.update_from_dict_representation(
            values_dict=yml_dict,
            source_id=self.source_id,
            modified_by=self.source_id,
            replace_tags=False,
            replace_data=True,
        )
        if primary_tell:
            tell.add_to_tell_group(primary_tell)
            if "*" in yml_dict.get(Tell.TAGS, []):
                tell.add_tags(primary_tell.tags)

        repo_url = f"{GITHUB_URL}/{repo_path_name}"
        self.update_from_source(tell, GITHUB_REPO_DATUM, repo_url)

        self._check_tool_keywords(tell)

        return tell

    def _check_tool_keywords(self, tell):
        tool_config = self.tool_config()
        if tool_config.is_disabled():
            return

        for keyword in ToolConfig.KEYWORDS:
            datum = tool_config.data_for_keyword(keyword, tell)
            if datum:
                tools_tell = self.teller.get(ToolConfig.tool_tell_alias(keyword))
                tools_tell.update_datum_from_source(
                    tools_tell.alias, tell.alias, datum
                )  # Maybe move this to TellusTool

    def parse_tellus_file(self, tellus_yml, repo_name, file_url):
        """
        :param tellus_yml:  the file to parse
        :param repo_name: the name of the github repo it came from
        :param file_url: the download URL of the file
        :return: True if parsing was wholly successful, False otherwise (mostly for testing)
        """
        logging.info("Parsing: %s", file_url)
        current_yml = tellus_yml  # So in case of exception we see the whole file
        try:
            primary_yml, *related = yaml.load_all(tellus_yml, Loader=yaml.FullLoader)
            if primary_yml.get(self.IGNORE_MARKER):
                logging.info(
                    "Tellus yaml file at [%s] is marked to be ignored with %s.  Doing that.",
                    file_url,
                    self.IGNORE_MARKER,
                )
                return True

            current_yml = primary_yml  # In case of an exception
            primary_tell = self._handle_yml_tell(
                primary_yml[Tell.ALIAS], primary_yml, repo_name, TELLUS_TOOL
            )
            aliases = [primary_tell.alias]

            for current_yml in related:
                secondary = self._handle_secondary_yml_tell(
                    current_yml, repo_name, primary_tell
                )
                if secondary:
                    aliases.append(secondary.alias)

            logging.info(
                "Loaded tellus.yml for %s.  Tells added/updated: %s",
                primary_tell.alias,
                repr(aliases),
            )
            return True
        # pylint: disable=broad-except
        except Exception as exception:
            logging.error(
                "Exception hit while trying to parse tellus.yml file '%s' (file not completely parsed): %s [%s]\n"
                "YML: \n"
                "%s",
                file_url,
                exception,
                exception.__class__,
                current_yml,
            )
            return False

    def tool_config(self):
        if self._tool_config is None:
            config_tell = self.teller.get_or_create_tell(
                TELLUS_CONFIG_TOOLS, TELLUS_INTERNAL, self.source_id
            )
            config_tell.make_user_modified()
            self._tool_config = ToolConfig(config_tell)

        return self._tool_config

    def set_up_tools(self):
        """
        Make sure all the special Tells and such that this source uses are correctly set up.
        """
        if self.tool_config().is_disabled():
            logging.info("Tool Keywords currently disabled.")
            return

        for keyword in ToolConfig.KEYWORDS:
            tools_tell = self.teller.get_or_create_tell(
                ToolConfig.PREFIX + keyword, TELLUS_INTERNAL, self.source_id
            )
            tools_tell.add_tag(keyword)
            if self.teller.has_tell(keyword):
                # This (hopefully rightly) ensures that if a Tell exists
                # Tellus will associate this keyword Tell with that Tell
                keyword_tell = self.teller.get(keyword)
                tools_tell.add_to_tell_group(keyword_tell)

    @staticmethod
    def query_for_files(github):
        found_files = github.search_code(
            "filename:tellus.yml filename:tellus.yaml", order="desc"
        )
        return found_files

    @staticmethod
    def is_tellus_file(github_file):
        return github_file.name in TellusYMLSource.VALID_TELLUS_FILE_NAMES

    async def load_source(self):
        try:
            self.set_up_tools()
            logging.info("Retrieving and loading tellus.yml files...")
            found_files = self.query_for_files(gethub())
            logging.info("Found %d files.", found_files.totalCount)
            for github_file in found_files:
                if self.is_tellus_file(github_file):
                    self.parse_tellus_file(
                        download_github_file(github_file.download_url),
                        github_file.repository.full_name,
                        github_file.download_url,
                    )

            self.teller.persist()
            message = f"Success! {found_files.totalCount} tellus.yaml files processed."
        except (ConnectionError, OSError) as exception:
            message = f"Unable to load tellus.yml files: {str(exception)}"
            logging.error(message)
        return message


class ToolConfig:
    """
    A wrapper around the Tool Config to make it more useful.
    """

    PREFIX = TELLUS_PREFIX + "tools-"
    KEYWORDS = {
        "docs": "Docs",
        "builds": "Builds",
        "github": "Github Repo",
        "tailus": "Tailus",
    }
    ENABLED = "enabled"

    def __init__(self, tool_config_tell):
        if tool_config_tell.alias != TELLUS_CONFIG_TOOLS:
            raise TellusException(
                f"Should only ever try to create a ToolConfig with the Tool Config Tell:  {tool_config_tell.to_simple_json()}"
            )

        self._tell = tool_config_tell

    @staticmethod
    def tool_tell_alias(keyword):
        return ToolConfig.PREFIX + keyword

    def is_disabled(self):
        return not self._tell.has_tag(self.ENABLED)

    def enable(self):
        self._tell.add_tag(self.ENABLED)

    def data_for_keyword(self, keyword, tell):
        if keyword not in self.KEYWORDS:
            raise TellusException(f"'{keyword}' is not a recognized tool keyword")

        return tell.get_datum(TellusYMLSource.SOURCE_ID, keyword)
