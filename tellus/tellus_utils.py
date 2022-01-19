import datetime as dt
import logging

import aiohttp
from dateutil.parser import parse, ParserError
from tellus.creds import get_credentials_from_vault

DATETIME_DEFAULT_FORMAT = "%Y-%m-%d %H:%M %Z"


async def is_url_available(url, timeout_seconds=1):
    """
    Ping a URL and see if it is active.  (Primarily for improved ease of mocking.  You may mock me.)
    :param url: the URL to check
    :param timeout_seconds: has a default, but can be overridden
    :return: true if the URL is "available" (i.e., returns some value)
    """
    # Super basic check for now - if it's a-up (and has some content), it's a-go!
    available = False
    logging.debug("Checking if address '%s' is available.", url)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    session = aiohttp.ClientSession(
        timeout=timeout, connector=aiohttp.TCPConnector(verify_ssl=False)
    )

    # pylint: disable=broad-except
    try:
        response = await session.get(url)
        status = response.status
        text = await response.text()
        available = status == 200 and len(text) > 0

        if not available:
            logging.debug("'%s' is not available - status was %s", url, status)
    except Exception as exception:
        # Intentionally ignoring exceptions here...
        logging.debug("'%s' is not available: %s", url, repr(exception))

    await session.close()

    return available


def get_tellus_credentials():
    print(get_credentials_from_vault("tellus"))


# Date / Time Utilities to centralize these in one place for possible replacement later
# Tellus basically assumes any dates/times handed around are ALWAYS UTC,
# and only converted if they are being displayed
def now():
    """
    :return: a UTC datetime for the current time.  Placed here to centralize our timestamps.
    """
    return dt.datetime.now(dt.timezone.utc)


def now_string():
    """
    :return: a UTC datetime for the current time, in standard ISO string format.
    """
    return datetime_string(now())


def datetime_string(datetime):
    return datetime.isoformat()


def datetime_from_string(string):
    return parse(string)


def prettify_string(string, format_string=DATETIME_DEFAULT_FORMAT):
    """
    Take a iso datetime string and make it prettier.
    :return: the formatted date string OR the string that was passed in if there is a parsing error.
    """
    try:
        return prettify_datetime(datetime_from_string(string), format_string)
    except (ParserError, TypeError):
        return string


def prettify_datetime(datetime, format_string=DATETIME_DEFAULT_FORMAT):
    """
    The same as prettify_string but for a datetime
    """
    return datetime.strftime(format_string)


class TellusException(RuntimeError):
    # Superclass for Tellus Exceptions to be able to catch them as a group.
    def __init__(self, message):
        RuntimeError.__init__(self, message)
