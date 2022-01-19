import json
import pathlib
import datetime as dt
from io import StringIO

import jsonpickle
import pytest

from tellus import __version__
from tellus.configuration import TELLUS_GO, TELLUS_INTERNAL
from tellus.persistence import (
    PickleFilePersistor,
    TELLUS_SAVE_DIR,
    PersistenceSetupException,
    PERSISTOR_HEADER_KEY,
    PERSISTOR_HEADER_VERSION,
    PERSISTOR_HEADER_SAVED,
    PERSISTOR_HEADER_SAVE_COUNTS,
)
from tellus.persistable import ZAuditInfo, Persistable

# pylint: disable=unused-argument
#   pylint gets cranky about the fake file system fixtures
from tellus.tell import Tell

TELLUS_PICKLE_SAVE_FILE_NO_HEADER = """{"_alias": "tellus", "_categories": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": ["tellus-go"]}, null]}]}, "_go_url": "/tellus", "_tags": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": []}, null]}]}, "py/object": "tellus.tells.Tell"}
{"_alias": "vfh", "_categories": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": ["tellus-go"]}, null]}]}, "_go_url": "http://veryfinehat.com", "_tags": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": []}, null]}]}, "py/object": "tellus.tells.Tell"}
{"_alias": "a", "_categories": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": ["tellus-go"]}, null]}]}, "_go_url": "BORKED", "_tags": {"py/reduce": [{"py/type": "sortedcontainers.sortedset.SortedSet"}, {"py/tuple": [{"py/set": []}, null]}]}, "py/object": "tellus.tells.Tell"}"""

TELLUS_PICKLE_SAVE_FILE_WITH_EARLIER_HEADER = f"""{{"persistor": "PickleFilePersistor","tellus-version": "{__version__}"}}
    {TELLUS_PICKLE_SAVE_FILE_NO_HEADER}
    """

PERSISTENCE_DATA = ""
PERSISTENCE_TEST_USER = "persistenceTest"


def create_current_save_file():
    """
    :return: a string that looks like a current, valid save file, whatever we are using
    """
    persistor = PickleFilePersistor(
        persist_root=None, save_file_name="current_pickle", testing=True,
    )
    buffer = StringIO()
    persistor.write_save_file(
        buffer,
        [
            Tell("tellus", go_url="/tellus", category=TELLUS_GO),
            Tell("vfh", go_url="http://veryfinehat.com", category=TELLUS_GO),
            Tell("quislet", category=TELLUS_INTERNAL),
        ],
    )

    return buffer.getvalue()


class MiniPersistable(Persistable):
    def __init__(self, values=None):
        super().__init__(PERSISTENCE_TEST_USER)
        self.values = values

    def to_json_pickle(self):
        return jsonpickle.encode(self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)


class MiniHolder(object):
    def __init__(self):
        self.persistables = []

    def load_me(self, load_string):
        self.persistables.append(jsonpickle.decode(load_string))


def test_persist_no_root(fs):
    persistor = PickleFilePersistor(persist_root=None, save_file_name="test")

    assert persistor.persistence_file() == pathlib.Path.cwd() / TELLUS_SAVE_DIR / "test"


def test_persistence_file_name(fs):
    try:
        PickleFilePersistor(persist_root=None, save_file_name=None)
        pytest.fail("Creating a Persistor with no file name should throw an exception.")
    except PersistenceSetupException as exception:
        print(exception)


def test_verify_save_file(fs):
    persistor = PickleFilePersistor(
        persist_root=None, save_file_name="current_pickle", testing=True,
    )
    buffer = StringIO()
    persistor.write_save_file(buffer, [MiniPersistable()])
    header = PickleFilePersistor.verify_save_file(StringIO(buffer.getvalue()))
    assert len(header) == 4
    assert header[PERSISTOR_HEADER_KEY] == "PickleFilePersistor"
    assert header[PERSISTOR_HEADER_VERSION] == f"{__version__}"
    assert header[PERSISTOR_HEADER_SAVED] is not None
    assert header[PERSISTOR_HEADER_SAVE_COUNTS] == 1
    assert buffer.tell() > 0

    fs.create_file(
        "earlier_pickle", contents=TELLUS_PICKLE_SAVE_FILE_WITH_EARLIER_HEADER
    )
    with open("earlier_pickle", "r") as save_file:
        header = PickleFilePersistor.verify_save_file(save_file)
        assert header == {
            "persistor": "PickleFilePersistor",
            "tellus-version": f"{__version__}",
        }
        assert save_file.tell() > 0

    fs.create_file("old_pickle", contents=TELLUS_PICKLE_SAVE_FILE_NO_HEADER)
    with open("old_pickle", "r") as save_file:
        header = PickleFilePersistor.verify_save_file(save_file)
        assert header is None
        assert save_file.tell() == 0, "This case should reset the file pointer."


def test_pickle_persistence(fs):
    persistor = PickleFilePersistor(
        persist_root="/test-location", save_file_name="test-file.txt"
    )
    persistable = MiniPersistable({"test-key": "test-value"})

    items_to_persist = [persistable]

    persistor.persist(items_to_persist)

    hodor = MiniHolder()  # too soon?
    persistor.load(hodor.load_me)
    loaded = hodor.persistables

    assert len(hodor.persistables) == 1, "Should have loaded our one test value"

    assert (
        persistable.to_json_pickle() == loaded[0].to_json_pickle()
    ), "Our loaded value should equal our existing persistable."


def test_pickle_persistence_cycle(fs):
    persistor = PickleFilePersistor(
        persist_root="/test-location", save_file_name="test-file.txt"
    )

    items_to_persist = [
        MiniPersistable({"test-key1": "test-value1"}),
        MiniPersistable({"test-key2": "test-value2"}),
        MiniPersistable({"test-key3": "test-value3"}),
    ]

    persistor.persist(items_to_persist)
    hodor = MiniHolder()
    persistor.load(hodor.load_me)
    loaded = hodor.persistables
    assert len(loaded) == len(items_to_persist)
    for persisted, loaded in zip(items_to_persist, loaded):
        assert (
            persisted == loaded
        ), f"{persisted.to_json_pickle()} should equal {loaded.to_json_pickle()}"


def test_audit_info():
    user = "rjbrande"
    now = dt.datetime.now(dt.timezone.utc)
    audit_info = ZAuditInfo("rjbrande")

    assert audit_info.created_by == user
    assert dt.datetime.fromisoformat(audit_info.created) == audit_info.created_datetime
    assert audit_info.last_modified_by == user
    assert (
        audit_info.last_modified == audit_info.created
    ), "Initially, last_modified should == created"

    assert (
        audit_info.created_datetime - now
    ).seconds < 1, "created_datetime should roughly be 'now'"


def test_audit_to_simple_dict_and_json():
    audit_info = ZAuditInfo("saturngirl")
    audit_info.modified("cosmicboy")
    test_dict = audit_info.to_simple_data_dict()

    assert test_dict["created_by"] == "saturngirl"
    assert test_dict["last_modified_by"] == "cosmicboy"
    assert test_dict["created"] == audit_info.created
    assert test_dict["last_modified"] == audit_info.last_modified

    assert json.dumps(test_dict) == audit_info.to_simple_json()
