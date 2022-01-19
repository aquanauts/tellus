# A temporary home for configuration till I figure out how to do configuration better in Python-land
import os

from dotenv import load_dotenv
from sortedcontainers import SortedSet

load_dotenv()


# Confluence
CONFLUENCE_URL = ""
CONFLUENCE_API_USERNAME = ""
CONFLUENCE_API_PASSWORD = ""

# Github
GITHUB_URL = ""
GITHUB_ACCESS_TOKEN = ""
GITHUB_API_URL = f"{GITHUB_URL}/api/v3"
DNS_FILE_URL = f""

# Google APIs
# The following is obviously not good, but is required for now to access the admin directory
# tellus-task: this should be either replaced with a more general delegate, or a different authentication method
# Vault
VAULT_PATH = "tellus"

####
# Tellus configuration
####
TELLUS_SAVE_FILE_NAME = "tellus_tells_save.txt"

# A set of non-user users that tend to show up in our source of valid users
NEVER_VALID_USERNAMES = [
    "tellus",
    "service",
]

TELLUS_APP_USERNAME = "tellus"  # used when something is created/modified by Tellus
TELLUS_PREFIX = "tellus-"

# Categories - these specify specific behavior for Tellus in many cases
TELLUS_INTERNAL = TELLUS_PREFIX + "internal"
TELLUS_GO = TELLUS_PREFIX + "go"
TELLUS_SOURCED = TELLUS_PREFIX + "sourced"
TELLUS_TOOL = TELLUS_PREFIX + "aq-tool"
TELLUS_TOOL_RELATED = TELLUS_PREFIX + "aq-tool-related"
TELLUS_LINK = TELLUS_PREFIX + "link"
TELLUS_DNS = TELLUS_PREFIX + "dns"
TELLUS_DNS_OTHER = TELLUS_PREFIX + "dns-other"
TELLUS_USER_MODIFIED = TELLUS_PREFIX + "user"
TELLUS_USER = TELLUS_PREFIX + "aquanaut"
TELLUS_INACTIVE_USER = TELLUS_PREFIX + "inactive-user"
TELLUS_SHEET_SPEC = TELLUS_PREFIX + "sheet-spec"
TELLUS_TESTING = TELLUS_PREFIX + "unit-testing-only"
TELLUS_CATEGORIES = SortedSet(
    [
        TELLUS_GO,  # Go Links; Tellus' core type of Tell - User Modifiable
        TELLUS_LINK,  # links, which are (or have been) actually active
        TELLUS_DNS,  # DNS entries which might be links
        TELLUS_DNS_OTHER,  # Other DNS entries (likely not links)
        TELLUS_INTERNAL,  # Tellus' internal category - these often have special, individualized behavior
        TELLUS_TOOL,  # Primary Tools entries, from tellus.yml files
        TELLUS_TOOL_RELATED,  # Related Tools entries, from tellus.yml files
        TELLUS_USER_MODIFIED,  # created/modified by a human - Tellus will be careful about automated updates
        TELLUS_USER,  # a tell representing an actual user
        TELLUS_INACTIVE_USER,  # a tell representing an deactivated user
        TELLUS_SHEET_SPEC,  # a tell representing the specification for a Google Sheet to load
        TELLUS_SOURCED,  # This Tell came from a source, but has no other special behavior.
        TELLUS_TESTING,  # Only for use in unit tests - see below
    ]
)
# TELLUS_TESTING this exists because other categories can have special behaviors
# This should *never* have any special behavior associated with it, so is safe as a
# generic category for testing purposes

# This sets the default priority order for coalescing data - anything not in here will be arbitrary
# (probably alphabetical).
TELLUS_CATEGORY_PRIORITY = (TELLUS_USER_MODIFIED, TELLUS_GO)

# Which categories are currently allowed to be edited by the UI?
# This guarantees that Tells only in other categories can be managed by Tellus safely...
EDITABLE_CATEGORIES = SortedSet([TELLUS_GO, TELLUS_USER_MODIFIED,])

# Special Tells
TELLUS_ABOUT_TELL = (
    f"{TELLUS_PREFIX}about"  # The tell that is the "About" link for Tellus.
)
