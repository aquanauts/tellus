import datetime as dt
import json
from abc import ABC

import jsonpickle

from tellus.tellus_utils import now, now_string

UNKNOWN_USER = "unknown"


class ZAuditInfo(object):
    """
    Standard audit information for persisted objects.  The naming is a bit of a hack to make it sort to the end
    of serialized data for readability.
    """

    def __init__(self, created_by):
        created_time = now_string()

        self._created_by = created_by
        self._created = created_time
        self._last_modified_by = created_by
        self._last_modified = self._created

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_json_pickle(self):
        return jsonpickle.encode(self)

    @property
    def created_by(self):
        return self._created_by

    @property
    def created(self):
        return self._created

    @property
    def created_datetime(self):
        return dt.datetime.fromisoformat(self._created)

    @property
    def last_modified_by(self):
        return self._last_modified_by

    @property
    def last_modified(self):
        return self._last_modified

    @property
    def last_modified_datetime(self):
        return dt.datetime.fromisoformat(self._last_modified)

    def seconds_since_last_modified(self, comparison_time=None):
        # largely to make certain testing easier
        if comparison_time is None:
            comparison_time = now()

        return (comparison_time - self.last_modified_datetime).seconds

    def modified(self, modified_by):
        self._last_modified_by = modified_by
        self._last_modified = now_string()

    def to_simple_data_dict(self):
        simple_dict = {
            "created": self.created,
            "created_by": self.created_by,
            "last_modified": self.last_modified,
            "last_modified_by": self.last_modified_by,
        }

        return simple_dict

    def to_simple_json(self):
        return json.dumps(self.to_simple_data_dict())


class Persistable(ABC):
    def __init__(self, created_by):
        if created_by is None:
            created_by = UNKNOWN_USER

        self._z_audit_info = ZAuditInfo(created_by)

    @property
    def audit_info(self) -> ZAuditInfo:
        return self._z_audit_info

    def modified(self, modified_by):
        self.audit_info.modified(modified_by)

    @property
    def last_modified(self):
        # We use this a lot for tests.
        return self._z_audit_info.last_modified
