"""
This is a central file for common names and constants across Tellus, as a central, universally-importable
module for everything to prevent circular imports.

It should map to elements in wiring.js as needed.

Ideally, anything that is shared across the UI and the Server (e.g., strings used for commands, etc.) should be in here.
"""

from tellus.configuration import TELLUS_DNS_OTHER

# Command Routes - single characters reserved for some action or internal use
R_GO = "g"  # redirects to a GO URL
R_TELL = "t"  # json for a individual Tells
R_LINKS = "l"  # json list of go links, based on a query string
R_TELLS = "q"  # basic json for a queried group of Tells, based on a query string
R_SEARCH = "e"  # basic json of a group of Tells, based on a search string
# R_TELLS_VERBOSE = "v"  # full json for a queried group of Tells, based on a query string
R_SOURCES = "o"  # routes for controlling sources
R_USER = "u"  # routes for information pertaining to a specific tellus user
R_MGMT = "m"  # routes for management functions and controls for Tellus
R_TESTING = "x"  # routes for testing and monitoring endpoints (e.g., Tellus status)
R_UNSECURE = "y"  # routes for testing and monitoring endpoints that are expected to bypass the proxy

# R_STATIC_FILES = "h"  # the route to our static files
# NOTE: the above, while preferable, does not work to to an insidious bug deep in the way aiohttp handles add_static
# for now, the workaround is to have a long, ugly route to static files like...
STATIC_FILES = "tellusstaticfiles"  # the route to our static files

TELLUS_PROTOCOL = (
    "tellus:"  # Allows the UI to know this is an internal Tellus URL for link creation
)

FAIL = f"{R_TESTING}/fail"

# Parameters
SESSION_TELLUS_USER = "tellususer"
TELLUS_COOKIE_NAME = "TELLUS"

# UI information
UI_ROUTE_GO = "/#go"
UI_ROUTE_TELL = "/#t."
PARAM_SEPARATOR = "."

# Command Words - special words reserved for Tellus to communicate to/from the UI
ALL_TELLS = "all-tells"
ALL = "all"
TELL_DELETE = "delete-tell"
TELL_UPDATE = "update-tell"
TELL_TOGGLE_TAG = "toggle-tag"

RESERVED_UI_WORDS = [
    ALL,
    ALL_TELLS,
    TELL_DELETE,
    TELL_UPDATE,
    TELL_TOGGLE_TAG,
    STATIC_FILES,
]  # These words should be reserved by Tellus - attempting to create Tells with these names is disallowed

UI_SUPPRESSED_CATEGORIES = [
    TELLUS_DNS_OTHER
]  # These categories are generally suppressed in the Tellus UI, unless explicitly requested.

TELLUS_UI_INFO = "tellus-info"


def ui_route_to_tell(alias):
    return f"{UI_ROUTE_TELL}{alias}"


def ui_route_go(alias):
    return f"{UI_ROUTE_GO}{PARAM_SEPARATOR}{alias}"
