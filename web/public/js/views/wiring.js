// Probably fancier ways to do this, but I am slowly moving any tokens that are cross-client/server into this
// file for centralization. Most constants and items in here will have a counterpart in the python files
// SEE: wiring.py

export const DNS_ACTIVE = 'link';
export const DNS_ALL = 'dns';
export const DNS_OTHER = 'dns-other';
export const TOOLS = 'aq-tool';
export const USERS = 'aquanaut';
export const ALL_TELLS = 'all-tells';
export const ALL = 'all';

export const TELLUS_USER = 'tellususer';
export const TELLUS_APP_USERNAME = 'tellus';

// Command Routes - single characters reserved for some action or internal use
// These should directly map to their counterparts in wiring.py
export const R_GO = 'g';  // redirects to a GO URL
export const R_TELL = 't';  // returns json for a single Tell
export const R_LINKS = 'l';   // returns a json list of go links
export const R_TELLS = 'q';   // returns minimal json for a queried group of tells
export const R_SOURCES = 'o';   // routes for controlling sources (TBD)
export const R_USER = 'u';   // routes for information pertaining to a specific tellus user (TBD)
export const R_MGMT = 'm';   // routes for management functions and controls for Tellus
export const R_TESTING = 'x';   // routes for testing endpoints

// Special Data Block Keys (usually Source IDs)
export const DATA_SOCIALIZER = 'socializer';
export const DATA_USER_INFO = 'user-info';
export const TELLUS_INFO = "tellus-info"

// Tellus Categories that should be displayed, in order
const DISPLAY_TELLUS_CATEGORIES = {
    '': ['ALL', 'All Tells'],  // Yes, this is cheaty.  But...kind of nice?
    'tellus-go': ['go', 'Go Links'],
    'tellus-user': ['user modified', 'Human-modified (tellus will limit systematic updates)'],
    'tellus-link': ['dns', 'Active DNS Entries'],
    'tellus-aq-tool': ['tools', 'Tools (tellus.yml primary entries)'],
    'tellus-aq-tool-related': ['tools*', 'Tool-related (tellus.yml related entries)'],
    'tellus-dns': ['dns', 'All DNS entries'],
    'tellus-dns-other': ['dns other', "Non-link DNS Entries (hidden in 'All Tells' list by default)"],
    'tellus-aquanaut': ['user', "Aquanauts"],
    'tellus-internal': ['tellus', 'Has a special Tellus function (please be careful if editing).'],
};

// Other Tellus Categories that are not for common display
const OTHER_TELLUS_CATEGORIES = {
    'tellus-domain': ['domain', 'Domains'],
};

// Data block IDs that should be displayed, in display order
// Note that any data blocks not in this list will not be displayed on the Tell page.
export const TELLUS_USER_INFO = 'user-info';
const DISPLAY_TELLUS_DATA_BLOCKS = {
    'user-info': ['User Info', 'User Info'],  // For reasons I do not understand, the constant above doesn't work here
    'tellus-aq-tool': ['tellus.yml info', 'Data from tellus.yml'],
    'tellus-dns': ['DNS Info', 'DNS Info'],
    'tellus-debug-info': ['Debugging', 'Debugging'],
};

const DISPLAY_NAME = 0
const DISPLAY_DESCRIPTION = 1

const ALL_TELLUS_CATEGORIES = Object.assign({}, DISPLAY_TELLUS_CATEGORIES, OTHER_TELLUS_CATEGORIES);

export function displayCategories() {
    return Object.keys(DISPLAY_TELLUS_CATEGORIES);
}

export function displayDataBlocks() {
    return Object.keys(DISPLAY_TELLUS_DATA_BLOCKS);
}

/**
 * @param lookupKey
 * @param dataBlock is this looking up a data block?
 * @param displayItem either DISPLAY_NAME or DISPLAY_DESCRIPTION
 * @param defaultValue
 * @returns {*}
 */
function lookupDisplayInfo(lookupKey, dataBlock, displayItem, defaultValue) {
    if (dataBlock && lookupKey in DISPLAY_TELLUS_DATA_BLOCKS) {
        return DISPLAY_TELLUS_DATA_BLOCKS[lookupKey][displayItem];
    }
    if (lookupKey in DISPLAY_TELLUS_CATEGORIES) {
        return DISPLAY_TELLUS_CATEGORIES[lookupKey][displayItem];
    }

    return defaultValue;
}

/**
 * @param lookupKey the key of the category or data block
 * @param dataBlock is this looking up a data block?
 * @returns the display name associated with the lookupKey
 */
export function displayName(lookupKey, dataBlock=false) {
    return lookupDisplayInfo(lookupKey, dataBlock, DISPLAY_NAME, "???")
}

/**
 * @param lookupKey the key of the category or data block
 * @param dataBlock is this looking up a data block?
 * @param defaultDescription
 * @returns the display description associated with the lookupKey
 */
export function displayDescription(lookupKey, dataBlock=false, defaultDescription="No description available.") {
    return lookupDisplayInfo(lookupKey, dataBlock, DISPLAY_DESCRIPTION, defaultDescription)
}


export function linkClass(linkIdentifier) {
    return '.links-' + linkIdentifier;
}

export function isLocalPersistence() {
    let returnValue = true;
    $.ajax({
        url: '/x/tellus-status',
        async: false,
        dataType: "json",
        success: function (data) {
            returnValue = data['localPersistence'];
        }
    });
    return returnValue;
}

export function getVersion() {
    let returnValue = true;
    $.ajax({
        url: '/x/tellus-status',
        async: false,
        dataType: "json",
        success: function (data) {
            returnValue = data['tellusVersion'];
        }
    });
    return returnValue;
}

export function displayTimestamp(isoDateString) {
    if (isoDateString === 'None' || isoDateString == null) {
        return 'No Timestamp';
    }
    return moment(isoDateString).format("MM-DD-YYYY hh:mm");
}

export function displayDate(isoDateString) {
    if (isoDateString === 'None' || isoDateString == null) {
        return 'No Timestamp';
    }
    return moment(isoDateString).format("MM-DD-YYYY");
}


export function relativeTimeAgo(isoDateString) {
    return moment(isoDateString).fromNow();
}

/**
 * Return the URL to query the server for a chunk of tell data.  Defaults to returning Tell Links.
 * @param queryString the "Query String" for Tellus
 * @param dataRoute the route for the Data to query.
 * @returns {string}  A relative path URL to the relevant data, for a json query.
 */
export function queryRoute(dataRoute, queryString) {
    return dataRoute + '/' + queryString
}
