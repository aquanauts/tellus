import copy
import logging
import re
import json
import jsonpickle
from sortedcontainers import SortedSet

from tellus.configuration import (
    TELLUS_PREFIX,
    TELLUS_INTERNAL,
    TELLUS_GO,
    TELLUS_LINK,
    TELLUS_DNS,
    TELLUS_USER_MODIFIED,
    TELLUS_CATEGORIES,
    EDITABLE_CATEGORIES,
    TELLUS_CATEGORY_PRIORITY,
)
from tellus.persistable import Persistable
from tellus.tellus_utils import TellusException
from tellus.wiring import RESERVED_UI_WORDS, TELLUS_UI_INFO


class InvalidAliasException(TellusException):
    def __init__(self, alias, additional_message=""):
        TellusException.__init__(
            self, f"Cannot create a tell with alias '{alias}'. {additional_message}"
        )


class InvalidTagException(TellusException):
    def __init__(self, tag, additional_message=""):
        TellusException.__init__(
            self, f"Cannot create the tag '{tag}'. {additional_message}"
        )


class InvalidTellUpdateException(TellusException):
    def __init__(self, message):
        TellusException.__init__(self, message)


SRC_TELLUS_USER = TELLUS_USER_MODIFIED


class Tell(Persistable):
    ALIAS = "alias"
    DESCRIPTION = "description"
    GO_URL = "go_url"
    TAGS = "tags"

    TELLUS_INFO = TELLUS_UI_INFO

    UPDATEABLE_PROPERTIES = (DESCRIPTION, GO_URL, TAGS)
    CORE_PROPERTIES = (ALIAS, DESCRIPTION, GO_URL, TAGS)
    # A set of aliases which are reserved for internal Tellus use only
    RESERVED_ALIASES = (
        SortedSet(TELLUS_CATEGORIES).update(["all",]).update(RESERVED_UI_WORDS)
    )

    _SRC_TAGS = "source-tags"

    _CATEGORY_LOADING = "tellus-loading-only"

    def __init__(
        self, alias, category, *, created_by=None, go_url=None, description=None
    ):
        super().__init__(created_by)

        self._alias = self._validate_alias(alias, category)

        self._data = {}
        self._tags = SortedSet()
        self._categories = SortedSet()
        self._description = None
        self._go_url = None

        self._groups = SortedSet()
        self._property_sources = {}

        if category == Tell._CATEGORY_LOADING:
            # Special case for unpickling
            return
        elif category is None:
            raise InvalidTellUpdateException(
                "A Tell cannot be created without a Category."
            )

        created_by = self.audit_info.created_by
        if description is not None:
            self.update_datum_from_source(
                category, Tell.DESCRIPTION, description, modified_by=created_by,
            )
        if go_url is not None:
            self.update_datum_from_source(
                category, Tell.GO_URL, go_url, modified_by=created_by
            )
        self.add_category(category)  # todo: this should go away once I fix Categories
        self.coalesce()

    @staticmethod
    def slugify(string):
        """
        Creates a canonical "slug" from a string.  Canonical tags and aliases in Tellus can only contain
        lowercase alphanumeric characters and dashes.

        :param string: any string intended to be an alias or a tag
        :return: a slugified version of the string (generally URL-acceptable)
        """
        slug = string.strip().lower()
        slug = re.sub(r"[^-\w\s]", " ", slug).strip()
        slug = re.sub(r"(\s|\_|\+)+", "-", slug)
        return slug

    @staticmethod
    def string_to_tags(tag_string):
        tags = re.split(r"\s|[,.]", tag_string)
        clean_tags = SortedSet()
        for tag in tags:
            slug = Tell.slugify(tag)
            if slug != "":
                clean_tags.add(slug)
        return clean_tags

    @staticmethod
    def is_slug_reserved(alias_slug, category_override=None):
        """
        Check to see if the slugified string is one of a small number of strings that are reserved by Tellus.
        """
        first = alias_slug.split("-")[0]
        if category_override != TELLUS_INTERNAL and (
            len(first) < 2 or alias_slug in Tell.RESERVED_ALIASES
        ):
            return True

        return False

    @staticmethod
    def clean_alias(alias):
        if not alias or len(alias.strip()) < 2:
            raise InvalidAliasException(
                alias, "Aliases must be two characters or more."
            )
        return Tell.slugify(alias)

    @staticmethod
    def _validate_alias(alias, category_override=None):
        slug = Tell.clean_alias(alias)
        if Tell.is_slug_reserved(slug, category_override):
            raise InvalidAliasException(
                alias, f"{slug} is one of a handful of reserved strings for Tellus."
            )
        return slug

    def reassign_alias(self, alias):
        """
        This is intentionally not a setter, as assigning an alias is more complicated than other attributes,
        and should only ever be done by the Teller, either during creation or an update.
        """
        self._alias = self._validate_alias(alias)

    @property
    def alias(self) -> str:
        return self._alias

    def derived_aliases(self):
        return []

    def prioritized_sources(self, reverse_order=False):
        """
        :param: reversed: if True, will reverse sort the results in reverse order (since that is actually what
        coalesce needs).
        :return:  A list of prioritized sources for coalescing which right now in the order of TELLUS_CATEGORY_PRIORITY
        and then alphabetical.
        """
        # There is probably a cleverer way to do this, but this is what I got...
        sorted_sources = SortedSet(self.sources)
        prioritized = [
            category
            for category in TELLUS_CATEGORY_PRIORITY
            if category in sorted_sources
        ]
        prioritized += list(sorted_sources - TELLUS_CATEGORY_PRIORITY)
        if reverse_order:
            prioritized.reverse()
        return prioritized

    def _coalesce_property(self, tell_property, values_dict):
        property_sources = []
        for source_id, value in values_dict.items():
            self._update_property(tell_property, value, False)
            property_sources.append(source_id)

        if len(property_sources) > 0:
            self._property_sources[tell_property] = property_sources
        elif tell_property in self._property_sources:
            self._property_sources.pop(tell_property)

    def coalesce(self):
        """
        Tells are assembled from multiple different sources.  This pulls all the data from the different sources
        together, and appropriately assigns the main properties, according to a prioritization scheme.
        It also identifies conflicting information, for potential display in the UI.
        """
        for tell_property in Tell.UPDATEABLE_PROPERTIES:
            property_sources = []
            for source_id in self.prioritized_sources(True):
                source_value = self.get_datum(source_id, tell_property)
                if source_value is not None:
                    self._update_property(tell_property, source_value, False)
                    property_sources.append(source_id)
                    if tell_property == Tell.TAGS:
                        # Tags are weird - after one coalesce, they just become informational never coalesce again
                        self._update_data_from_source(
                            source_id, {Tell._SRC_TAGS: source_value}
                        )
                        self.remove_datum(source_id, Tell.TAGS)
                elif tell_property in self.get_data(source_id):
                    # Just to clean up and be safe...
                    self.get_data(source_id).pop(tell_property)

            if len(property_sources) > 0:
                property_sources.reverse()
                self._property_sources[tell_property] = property_sources
            elif tell_property in self._property_sources:
                self._property_sources.pop(tell_property)

    @property
    def property_sources(self):
        return self._property_sources

    def has_no_properties(self):
        """
        A convenience method, mostly for testing, to put this question where it should live.
        :returns: True if all of the non-alias properties for the tell are empty, False otherwise.
        """
        return (
            self._description is None and self.go_url is None and len(self._tags) == 0
        )

    @property
    def groups(self):
        return list(self._groups)

    def create_group(self):
        self.add_to_tell_group(self)

    def in_group(self, group_name):
        return group_name in self._groups

    def add_to_tell_group(self, grouping_tell):
        self.add_tag(grouping_tell.alias)
        self._groups.add(grouping_tell.alias)
        if not grouping_tell.in_group(grouping_tell.alias):
            # Grouping Tells should always be in their own group once created...
            grouping_tell.add_to_tell_group(grouping_tell)

    @property
    def description(self):
        return self._description

    @property
    def go_url(self):
        if self._go_url is None and self.in_category(TELLUS_LINK):
            return self.internal_url
        return self._go_url

    @property
    def internal_url(self):
        if self.in_category(TELLUS_LINK) or self.in_category(TELLUS_DNS):
            return f"http://{self._alias}.example.com" # TODO What should this be?
        return None

    @property
    def is_go(self):
        return self.in_category(TELLUS_GO)

    @property
    def tags(self):
        return list(self._tags)

    def add_tag(self, tag):
        self.add_tags([Tell.slugify(tag)])

    def add_tags(self, tags):
        self._tags.update(tags)

    def has_all_tags(self, tags, include_alias=True):
        if include_alias and self.alias in tags:
            return True

        # Not sure if this is efficient, but it sure is clean
        return SortedSet(tags) <= self._tags

    def has_tag(self, tag, include_alias=True):
        return self.has_all_tags([tag], include_alias)

    def remove_tag(self, tag):
        try:
            self._tags.remove(tag)
        except KeyError:
            return None
        return tag

    @staticmethod
    def ensure_category_prefix(category):
        if category.startswith(TELLUS_PREFIX):
            return category
        return TELLUS_PREFIX + category

    @staticmethod
    def valid_category(category):
        return category in TELLUS_CATEGORIES

    @property
    def categories(self):
        return list(self._categories)

    def add_category(self, category):
        if category not in TELLUS_CATEGORIES:
            raise Exception(
                f"Illegal attempt to add category '{category}' (to tell '{self._alias}').  "
                f"Valid categories are: {TELLUS_CATEGORIES}"
            )
        self._categories.add(category)

    def remove_category(self, category):
        if category not in self._categories:
            logging.error(
                "Attempted to remove '%s' from Category '%s', but it wasn't in that Category.",
                self._alias,
                category,
            )
        self._categories.remove(category)

    def in_all_categories(self, categories):
        # Not sure if this is efficient, but it sure is clean
        return SortedSet(categories) <= self._categories

    def in_any_categories(self, categories):
        # Not sure if this is efficient, but it sure is clean
        return len(SortedSet(categories).intersection(self._categories)) > 0

    def categories_equal(self, categories):
        # Not sure if this is efficient, but it sure is clean
        return SortedSet(categories) == self._categories

    def categories_are_subset_of(self, categories):
        """
        Return True if the only categories this Tell has are a subset of the passed categories.
        """
        return self._categories <= SortedSet(categories)

    def in_category(self, category):
        return self.in_all_categories([category])

    def make_user_modified(self):
        self.add_category(TELLUS_USER_MODIFIED)

    @property
    def read_only(self):
        return not self.in_any_categories(EDITABLE_CATEGORIES)

    @staticmethod
    def _is_property(property_name):
        return property_name in Tell.CORE_PROPERTIES

    def _update_property(self, property_name, value, replace_tags=False):
        """
        Update the specified Tell Property (will ignore alias, though)
        :param property_name: the name of the property to update
        :param value: the value to set it to
        :param replace_tags:
        :raises: InvalidTellUpdateException if the property name is not in Tell.CORE_PROPERTIES
        :return: True if successful, False if there was a name collision with the current property (for Coalescing)
        """
        if not Tell._is_property(property_name):
            raise InvalidTellUpdateException(
                f"'{property_name}' is not a valid Tell property for update_properties.  Can only "
                f"update the following properties using this method: {Tell.CORE_PROPERTIES}"
            )

        internal_name = f"_{property_name}"
        set_value = None if value == "" else value
        if property_name in (Tell.DESCRIPTION, Tell.GO_URL):
            current_value = getattr(self, internal_name)
            setattr(self, internal_name, set_value)
            if current_value is not None and current_value != set_value:
                return False

        if property_name == Tell.TAGS:
            self._update_tags(value, replace_tags)

        return True

    def _update_tags(self, tag_value, replace_tags):
        if isinstance(tag_value, str):
            tags = SortedSet(Tell.string_to_tags(tag_value))
        else:
            tags = SortedSet(tag_value)

        if tags.__contains__(""):
            tags.remove("")

        if replace_tags:
            self._tags = tags
        else:
            self.add_tags(tags)

    def _is_updateable_by_source(self, property_name, source):
        return (
            source == SRC_TELLUS_USER
            or property_name == Tell.TAGS
            or not self.in_any_categories([TELLUS_GO, TELLUS_USER_MODIFIED])
        )

    @property
    def sources(self):
        return list(self._data.keys())

    def get_data_dict(self):
        return dict(self._data)

    def get_data(self, source_id):
        """
        :param source_id: the key of the Tell data block to get
        :param default: the default value to return if no data exists - otherwise, will return None
        :return: the Tell data block if it exists, or None if it doesn't
        """
        data = self._data.get(source_id)
        if data is None:
            return None

        return dict(self._data.get(source_id, None))

    def get_datum(self, source_id, key, default=None):
        """
        :param source_id: the key of the Tell data block to get the datum from
        :param key: the datum from the data block to return
        :param default: the default value to return if no datum exists - otherwise will return None
        :return: the Datum from the data block, if it exists, or None if it doesn't
        """
        data = self.get_data(source_id)
        if data is None:
            return default

        return data.get(key, default)

    def clear_data(self, source_id):
        if source_id in self._data:
            return self._data.pop(source_id)
        return None

    def remove_datum(self, source_id, key):
        if source_id in self._data and key in self._data[source_id]:
            return self._data[source_id].pop(key)
        return None

    def update_datum_from_source(self, source_id, key, value, modified_by=None):
        self.update_data_from_source(source_id, {key: value}, modified_by)

    def update_data_from_source(
        self, source_id, data_dict, modified_by=None, replace_data=False
    ):
        self._update_data_from_source(source_id, data_dict, replace_data)
        if modified_by:
            self.modified(modified_by)
        else:
            self.modified(source_id)

        # todo: should either add category here, or not depending on how I handle categories...
        if source_id in TELLUS_CATEGORIES:
            self.add_category(source_id)

        self.coalesce()  # We always coalesce after an external data update, unless explicitly suppressed.

    def _update_data_from_source(self, source_id, data_dict, replace_data=False):
        if replace_data or source_id not in self._data:
            self._data[source_id] = copy.deepcopy(data_dict)
        else:
            self._data[source_id].update(data_dict)

    def update_from_dict_representation(
        self,
        values_dict,
        source_id,
        modified_by,
        replace_tags=False,
        replace_data=False,
    ):
        """
        Update the Tell from a "full" dictionary representation including the Alias (which is checked).
        Generally this should only be used from sources that are providing a full Tell
        (e.g., the UI, or a tellus.yaml file)

        :param values_dict: the set of values to populate in the Tell
        :param source_id: the Source ID of the data
        :param modified_by: who is this being modified by?
        :param replace_tags: Should new tags replace the old tags (vs added to the set)?
        :param replace_data: If true, will  replace this source's data (rather than update it).  Defaults to False.
        """
        alias = Tell._validate_alias(values_dict.get(Tell.ALIAS, None), source_id)
        if not alias or alias != self.alias:
            raise InvalidTellUpdateException(
                f"Attempt to update the values of Tell '{self.to_simple_json()}'\n"
                f"did not contain the correct 'alias' value: {values_dict}, "
                f"even after cleaning to '{alias}."
            )

        if replace_tags:
            # todo:  this is a hack until I can fix it so users only update user tags
            self._tags.clear()

        self.update_data_from_source(
            source_id, values_dict, modified_by=modified_by, replace_data=replace_data
        )

    def to_json_pickle(self):
        return jsonpickle.encode(self)

    @staticmethod
    def from_json_pickle(json_string):
        tell = jsonpickle.decode(json_string)

        # This is to ensure that if we add attributes, then save and reload, we still have
        # the correct empty attributes on the loaded Tell
        new_tell = Tell(tell.alias, Tell._CATEGORY_LOADING)
        for tell_property in tell.__dict__:
            new_tell.__dict__[tell_property] = tell.__dict__[tell_property]

        return new_tell

    def go_json(self):
        return json.dumps({self._alias: self._go_url})

    def update_tellus_info(self, source_id, value):
        if value is None:
            try:
                self._data[source_id].pop(Tell.TELLUS_INFO)
            except KeyError:
                # This just means that we're clearing out some info that had never been set.
                pass
        else:
            self.update_datum_from_source(source_id, Tell.TELLUS_INFO, value)

    def tellus_info(self):
        """
        Additional information from sources that is relevant to Tellus (probably for use in the UI).

        :return: a json-serializable map of simple info about the Tell that is relevant to Tellus
        """
        tellus_info = {}
        for source_id, source_data in self._data.items():
            if Tell.TELLUS_INFO in source_data:
                tellus_info[source_id] = source_data[Tell.TELLUS_INFO]
        return tellus_info

    def _properties_dict(self):
        """
        :return: a dict just containing the basic properties of the Tell - a minimalist view.
        """
        return {
            "alias": self._alias,
            "go_url": self.go_url,
            "description": self.description,
            "categories": self.categories,
            "tags": self.tags,
        }

    def minimal_tell_dict(self):
        return self.tell_dict(minimal=True)

    def tell_dict(self, additional_properties=None, *, minimal=False):
        dict_representation = self._properties_dict()
        tellus_info = self.tellus_info()
        if tellus_info:
            dict_representation[Tell.TELLUS_INFO] = tellus_info

        if not minimal:
            data_dict = self.get_data_dict()
            dict_representation.update(
                {
                    "groups": self.groups,
                    "data": data_dict,
                    "read-only": self.read_only,
                    "z-audit-info": self.audit_info.to_simple_data_dict(),
                }
            )

        if additional_properties:
            dict_representation.update(additional_properties)

        return dict_representation

    def to_simple_json(self, additional_properties=None, *, minimal=False):
        """
        :param additional_properties: Any additional properties to decorate the dict with (e.g., User Info).
        :param minimal: If True, will return just the basic properties of the Tell
        :return: the simple JSON for the Tell
        """
        json_dict = self.tell_dict(additional_properties, minimal=minimal)

        try:
            return json.dumps(json_dict)
        except TypeError as error:
            logging.error(
                "Error trying to create simple json for Tell:  %s",
                self.to_json_pickle(),
            )
            raise error


class TellWrapper:
    """
    A wrapper around a Tell to provide some other functionality
    """

    # tellus-task: decide if this is something to keep, and if so extract and make User, CoffeeBot, Source superclass
    def __init__(self, wrapped_tell, wrapper_name, source_id):
        if not self.is_wrappable(wrapped_tell):
            raise TellusException(
                f"Attempted to create a {wrapper_name} with an invalid Tell:  {wrapped_tell.to_simple_json()}"
            )

        self._tell: Tell = wrapped_tell
        self._source_id = source_id

    def __eq__(self, other):
        """By default, wrappers are equivalent if their internal Tell is equivalent."""
        if isinstance(other, TellWrapper):
            return self._tell == other._tell
        return False

    @staticmethod
    def is_wrappable(tell: Tell):
        return tell is not None

    @property
    def alias(self):
        return self._tell.alias

    @property
    def tell(self):
        return self._tell

    def datum(self, key):
        return self._tell.get_datum(self._source_id, key)

    def set_datum(self, key, value):
        self._tell.update_datum_from_source(self._source_id, key, value)
