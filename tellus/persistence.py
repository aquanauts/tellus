import logging
import pathlib

import json

from tellus.tellus_utils import TellusException, now_string
from tellus import __version__

TELLUS_SAVE_DIR = "tellus-persistence"

_FAKE_ROOT = "%BAD_FILE_NAME%"

PERSISTOR_HEADER_KEY = "persistor"
PERSISTOR_HEADER_VERSION = "tellus-version"
PERSISTOR_HEADER_SAVED = "file-saved"
PERSISTOR_HEADER_SAVE_COUNTS = "current-run-file-saves"


class PersistenceSetupException(TellusException):
    def __init__(self, message):
        TellusException.__init__(self, f"Persistor set up incorrectly :  '{message}'.")


class PickleFilePersistor:
    def __init__(self, *, persist_root, save_file_name, testing=False):
        self._testing = testing
        if persist_root is None:
            self._persist_root = _FAKE_ROOT
            logging.error(
                "NO PERSISTENT ROOT SPECIFIED - this should generally only be true for testing (which is %s).  "
                "Will be saving to: %s",
                self._testing,
                self._persistence_root,
            )
        else:
            self._persist_root = pathlib.Path(persist_root)
            logging.info("Setting persistent root to: %s", self._persistence_root)

        PickleFilePersistor._validate_persistence_file(save_file_name)

        self._save_dir = TELLUS_SAVE_DIR
        self._save_file = save_file_name
        self._save_counts = 0

    @staticmethod
    def _validate_persistence_file(save_file_name):
        if save_file_name is None:
            raise PersistenceSetupException("Save file must be specified.")

    @staticmethod
    def _default_save_dir():
        return pathlib.Path.cwd()

    def is_local_persistence(self):
        return self._persist_root == _FAKE_ROOT

    @property
    def _persistence_root(self):
        if self._persist_root == _FAKE_ROOT:
            if not self._testing:
                logging.error(
                    "WRITING TO CURRENT DIRECTORY - This means no persistence root was specified. "
                    "This should only happen when running tests, which we do not think we are doing."
                )
            return self._default_save_dir()
        return self._persist_root

    def persistence_dir(self):
        return self._persistence_root / self._save_dir

    def persistence_file(self):
        return self.persistence_dir() / self._save_file

    def _initialize_persistence_directory(self):
        if self.persistence_dir().exists():
            logging.error(
                "Persistence directory '%s' already exists.", self.persistence_dir()
            )
            return

        self.persistence_dir().mkdir(parents=True)
        logging.info(
            "Successfully created persistence directory '%s'.", self.persistence_dir()
        )

    def _construct_file_header(self):
        """
        Write the file persistor header to the specified file, and return
        :param save_file: a file to persist to
        :return: the header dict that was written out.
        """
        self._save_counts += 1
        header = {
            PERSISTOR_HEADER_KEY: self.__class__.__name__,
            PERSISTOR_HEADER_VERSION: __version__,
            PERSISTOR_HEADER_SAVED: now_string(),
            PERSISTOR_HEADER_SAVE_COUNTS: self._save_counts,
        }
        return header

    @staticmethod
    def verify_save_file(loadfile):
        header_line = loadfile.readline()
        if header_line:
            header_dict = json.loads(header_line)
            if PERSISTOR_HEADER_KEY in header_dict:
                logging.info("Successfully verified loadfile Header:  %s", header_dict)
                return header_dict

        logging.warning(
            "The first line of the save file was not a header.  "
            "This should be true only if converting from an older save file.  "
            "Tellus is assuming this is actually a Tell and resetting the file to the beginning. "
            "Line:  %s",
            header_line,
        )
        loadfile.seek(0)
        return None

    def persist(self, jsonpickleable_items):
        logging.info("Saving to [{%s}].", self.persistence_file())
        if not self.persistence_dir().exists():
            logging.info(
                "No Persistence Directory.  Creating it at: %s", self.persistence_dir()
            )
            self._initialize_persistence_directory()

        with open(self.persistence_file(), "w") as save_file:
            self.write_save_file(save_file, jsonpickleable_items)

    def write_save_file(self, io_buffer, jsonpickleable_items):
        """
        :param io_buffer: the file or string buffer to write to
        :param jsonpickleable_items: the items to write out
        :return:
        """
        header = self._construct_file_header()

        #  This is like this because of weird issue where the header wouldn't get written out:
        logging.debug("Writing Header file")
        io_buffer.write(json.dumps(header))
        for item in jsonpickleable_items:
            io_buffer.write("\n" + item.to_json_pickle())

    def load(self, load_callback):
        logging.info("Loading save file '%s'.", self.persistence_file())
        if self.persistence_file().exists():
            with open(self.persistence_file(), "r") as loadfile:
                self.verify_save_file(loadfile)
                for line in loadfile:
                    load_callback(line)
        else:
            logging.info(
                "Persistence file '%s' doesn't exist yet.  Making sure directory exists...",
                self.persistence_file(),
            )
            self._initialize_persistence_directory()

    def read_file(self):
        """
        Just hands back the contents of the save file, for debugging.
        :return: the contents of the save file
        """
        if not self.persistence_file().exists():
            return f"No save file currently exists at: {self.persistence_file()}"

        with open(self.persistence_file(), "r") as savefile:
            return savefile.read()
