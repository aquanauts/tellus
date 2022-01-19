import pytest
from asynctest import mock


def make_mock_response(text, status=200):
    mock_response = mock.Mock()
    mock_response.text = mock.CoroutineMock(return_value=text)
    mock_response.status = status
    return mock_response


@pytest.fixture
def mock_session(mocker):
    session = mock.Mock()
    mocker.patch("aiohttp.ClientSession", return_value=session)
    session.get = mock.CoroutineMock()
    session.close = mock.CoroutineMock()
    return session


@pytest.fixture
def this_test_name(request):
    """
    Entirely a convenience method for clarity.  Just gets the name of the current test and returns it.
    You must add it to the parameters of the test, as with 'request' above, to make it work.
    """
    return request.node.name


def assert_modified_since(
    auditable, comparison_datetime, should_have_been_modified=True
):
    """
    A weird little convenience method for testing - a convenient way to repeatedly check if an Auditable
    (e.g., a Tell) has been modified over a series of events, or not.

    :param auditable:  The Auditable to check
    :param comparison_datetime:  The prior last modified datetime to compare against.  If None, this should always pass.
    :param should_have_been_modified:  Should the Auditable have been modified?
    :return: the current last_modified time, for use in the next assertion
    """
    if comparison_datetime is not None:
        if should_have_been_modified:
            assert comparison_datetime < auditable.audit_info.last_modified_datetime
        else:
            assert comparison_datetime == auditable.audit_info.last_modified_datetime
            # Yes, this should fail if the comparison datetime is after "last modified"

    return auditable.audit_info.last_modified_datetime


def assert_not_modified_since(auditable, comparison_datetime):
    """
    Convenience wrapper of assert_modified_since for better readability.
    """
    return assert_modified_since(auditable, comparison_datetime, False)
