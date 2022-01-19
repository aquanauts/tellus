import logging

import re
from fuzzywuzzy import process

from sortedcontainers import SortedDict, SortedSet

from tellus.tell import (
    Tell,
    InvalidTellUpdateException,
    SRC_TELLUS_USER,
    InvalidAliasException,
)
from tellus.tellus_utils import TellusException


class DuplicateTellException(TellusException):
    def __init__(self, tell):
        TellusException.__init__(self, f"A Tell for '{tell.alias}' already exists.")


class InvalidTellusQueryException(TellusException):
    def __init__(self, query_string):
        TellusException.__init__(
            self, f"'{query_string}' is not a valid query for Tellus."
        )


class TheresNoTellingException(TellusException):
    def __init__(self, alias):
        TellusException.__init__(
            self, f"A Tell matching alias '{alias}' could not be found."
        )


# Manages our Tells
class Teller(object):
    NEW_ALIAS = "new_alias"

    def __init__(self, persistor):
        self._tells = SortedDict()
        self._persistor = persistor

    @property
    def aliases(self):
        """
        Return all Tell aliases in the Teller.  Mostly to simplify some testing.
        """
        return list(self._tells.keys())

    def tells(self, category=None):
        if category is None:
            return list(self._tells.values())

        return [tell for tell in self._tells.values() if tell.in_category(category)]

    def tells_count(self, category=None):
        if category is None:
            return len(self._tells)
        return len(self.tells(category))

    def create_tell(
        self,
        raw_alias,
        category,
        created_by,
        *,
        url=None,
        description=None,
        tell_dict=None,
        source=None,
    ) -> Tell:
        """
        The main Tell creation method - all new Tell creation should ultimately go through this.
        Create a Tell, and add it to the set of Tells this Teller manages.

        :param raw_alias: a raw alias (will be validated/cleaned if necessary)
        :param category: the category for the Tell
        :param created_by: the user creating the Tell
        :param url: (optional) the go URL for the Tell
        :param description: (optional) the description for the Tell
        :param tell_dict: a dictionary representation of the Tell to create
        :param source:

        :return: the new Tell
        """
        clean_alias = Tell.clean_alias(raw_alias)
        if clean_alias in self._tells:
            raise DuplicateTellException(self._tells[clean_alias])

        tell = Tell(
            clean_alias,
            category=category,
            go_url=url,
            created_by=created_by,
            description=description,
        )

        if tell_dict is not None and source is not None:
            # todo: tell_dict and source should be merged
            tell.update_from_dict_representation(tell_dict, source, created_by)

        self._tells[clean_alias] = tell
        return self._tells[clean_alias]

    def get_or_create_tell(self, raw_alias, category, created_by):
        clean_alias = Tell.clean_alias(raw_alias)
        try:
            tell = self.get(clean_alias)
            if not tell.in_category(category):
                logging.info(
                    "Tell '%s' is being added to category '%s'.", clean_alias, category
                )
                tell.add_category(category)
            return tell
        except TheresNoTellingException:
            logging.info("Creating Tell '%s' in category '%s'.", clean_alias, category)
            return self.create_tell(clean_alias, category, created_by=created_by)

    def create_tell_with_parameters(self, category, params, user):
        """
        Pedantic, but this method is specifically to separate out Tells that came from the UI vs those that could be
        being created by a Source.
        """
        return self.create_tell_from_dict(category, dict(params), SRC_TELLUS_USER, user)

    def create_tell_from_dict(self, category, tell_dict, source, created_by=None):
        """
        Construct a (new) Tell from a dictionary of data.
        :param category: The Category for the new Tell
        :param tell_dict: The dict defining the new Tell.  Must have an alias entry - see code.
        :param source:  The source of this data (either a user or a source ID, usually)
        :param created_by:  Who is making this modification?  If None, will use the source_id.
        :return: the newly created Tell
        """
        if created_by is None:
            created_by = source

        clean_alias = Tell.clean_alias(tell_dict[Tell.ALIAS])
        if clean_alias != tell_dict[Tell.ALIAS]:
            logging.warning(
                "Cleaning alias, changing %s to %s", tell_dict[Tell.ALIAS], clean_alias
            )
            tell_dict[Tell.ALIAS] = clean_alias

        tell = self.create_tell(
            clean_alias,
            category,
            created_by=created_by,
            tell_dict=tell_dict,
            source=source,
        )

        return tell

    def get(self, raw_alias, search_if_no_match=False) -> Tell:
        """
        Get a specific Tell by an alias.
        :param raw_alias: the raw alias of the Tell to look up.  Will be turned into a "clean" alias.
        :param search_if_no_match: Attempt to search for a single match if no specific Tell is found?
        :return:
        """
        try:
            clean_alias = Tell.clean_alias(raw_alias)
        except InvalidAliasException as e:
            # Making this exception more specific
            raise TheresNoTellingException(raw_alias) from e

        try:
            return self._tells[clean_alias]
        except KeyError as e:
            if search_if_no_match:
                search_tells = self.search_tells(clean_alias)
                if len(search_tells) == 1:
                    return search_tells[0]
            # Making this exception more specific
            raise TheresNoTellingException(raw_alias) from e

    def search_tells(self, clean_alias):
        """
        Attempt to do a search on a particular alias.
        :param clean_alias:
        :return: A list of Tells whose aliases match sufficiently closely.
        """
        chars_only_alias = re.sub(r"\W+", "", clean_alias)
        alias_matches = process.extractBests(
            chars_only_alias, self._tells.keys(), score_cutoff=75
        )
        return [self._tells.get(alias_match[0]) for alias_match in alias_matches]

    def _load_tell(self, tell_string):
        try:
            tell = Tell.from_json_pickle(tell_string)
            self._tells[tell.alias] = tell
        except InvalidAliasException as exception:
            logging.error(
                "Tell found in save file with invalid alias [%s]. NOTE:  This tell will be removed from the "
                "save file:\n%s",
                exception,
                tell_string,
            )

    @staticmethod
    def parse_query_string(query_string):
        # A tell query string consists mostly of a bunch of things separated by .s - the first item, though,
        # has special behavior as a possible Tellus category.
        categories = SortedSet()
        tags = SortedSet()
        if query_string is not None:
            category, *items = query_string.split(".")

            possible_category = Tell.ensure_category_prefix(category)
            if Tell.valid_category(possible_category):
                categories.add(possible_category)
            else:
                items.append(category)  # Treat it as a tag

            for item in items:
                if item and Tell.valid_category(item):
                    categories.add(item)
                elif item:
                    tags.add(Tell.slugify(item))

        return categories, tags

    def query_tells(
        self, query_string=None, ignore_categories=None, tell_repr_method="go_url",
    ):
        """
        Query the list of Tells based on a query string - returns only a minimal representation of the Tell.

        :param query_string: the Query string to retrieve on
        :param ignore_categories: Ignore Tells from these categories.
        :param tell_repr_method: The (string) name of the Tell method you'd like to use to Represent the Tell.
            Defaults to go_url.
        :return: a dict of alias: <Tell Representation> - either a minimal Tell Dict, or just the go_url
        """
        tells = {}
        categories, tags = Teller.parse_query_string(query_string)
        for tell in self._tells.values():
            if (
                query_string is None
                or (tell.in_all_categories(categories) and tell.has_all_tags(tags))
            ) and not tell.in_any_categories(ignore_categories):
                tell_attr = getattr(tell, tell_repr_method)
                if callable(tell_attr):
                    tells[tell.alias] = tell_attr()
                else:
                    # This is a bit of a cheat - if it's not callable,
                    # we'll assume it's a property and you just got the value.
                    tells[tell.alias] = tell_attr
        return tells

    def has_tell(self, raw_alias):
        try:
            tell = self.get(raw_alias)
        except TheresNoTellingException:
            return False
        return tell is not None

    def delete_tell(self, alias):
        """
        Delete the Tell with the specified Alias from the Teller.
        Note that this requires a fully correct alias (it will not try to clean it).
        """
        tell = self._tells[alias]
        self._tells.__delitem__(tell.alias)
        return tell

    def toggle_tag(self, alias, tag):
        """
        :param alias:  The alias of the Tell to toggle the tag on
        :param tag: The tag to toggle
        :return: None if the tag was removed, tag if it was added
        """
        tell = self.get(alias)
        if tell.has_tag(tag):
            tell.remove_tag(tag)
            return None
        else:
            tell.add_tag(tag)
            return tag

    def _update_alias(self, tell, new_alias):
        old_alias = tell.alias
        if self.has_tell(new_alias):
            raise InvalidTellUpdateException(
                f"Attempted to rename Tell '{old_alias}' to '{new_alias}', but a Tell with that alias already exists."
            )
        tell.reassign_alias(new_alias)
        self._tells[tell.alias] = tell
        self._tells.pop(old_alias)

    def update_tell_from_ui(self, aiohttp_params, modified_by, replace_tags=False):
        """
        Update the Tell from the UI - this has some different characteristics than any update
        :param aiohttp_params:
        :param modified_by:
        :param replace_tags:
        :return:
        """
        # Because these are a MultiDictProxy coming from aiohttp:
        params = dict(aiohttp_params)
        alias = params[Tell.ALIAS]
        # Accessing _tells directly here to avoid "cleaning" the Alias
        try:
            tell = self._tells[alias]
        except KeyError as e:
            raise InvalidTellUpdateException(
                f"No existing tell with alias '{alias}'.  Updates require a full canonical alias."
            ) from e

        new_alias = params.get(self.NEW_ALIAS, None)
        if new_alias:
            if new_alias != alias:
                logging.info("Updating Tell '%s' to alias '%s'.", alias, new_alias)
                self._update_alias(tell, new_alias)
                # Required, because the request actually passes a MultiDictProxy:
                params = dict(params)
                params[Tell.ALIAS] = tell.alias
            params.pop(self.NEW_ALIAS)

        tell.update_from_dict_representation(
            params, SRC_TELLUS_USER, modified_by, replace_tags=replace_tags
        )
        tell.make_user_modified()  # Updates can only be done by humans here
        return tell

    def load_tells(self):
        self._persistor.load(self._load_tell)

    def persist(self):
        self._persistor.persist(self._tells.values())

    def persistence_file(self):
        return self._persistor.persistence_file()

    def is_local_persistence(self):
        return self._persistor.is_local_persistence()

    def read_file(self):
        return self._persistor.read_file()
