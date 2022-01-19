// Common components used throughout the Tellus UI

import {
    displayDescription,
    displayName,
    queryRoute,
    R_TELLS,
    relativeTimeAgo,
    TELLUS_INFO
} from "./wiring.js";

const EXTENDED_TELL_LIST = false;

export default function() {
    let view = template('debugView');

    view.append(tellusLinksComponent('FAKE', 'TEST HEADER NO LINK'));
    view.append(tellusLinksComponent('FAKE', 'TEST HEADER LINK', 'http://github.com/aquanauts/tellus'));

    return view;
}


export function tellusDataBlock(headerKey, data_json) {
    let view = template('tellusDataBlock');

    let header = view.find('.tellus-data-header')
    header.text(displayName(headerKey, true));
    header.attr("title", displayDescription(headerKey, true))

    $.each(data_json, function ( key, value ) {
        let listItem = template('tellus-data-item');
        listItem.find('.tellus-data-key').text(key);
        listItem.find('.tellus-data-value').append(linkify(value));

        view.find('.tellus-data-table').append(listItem);
    });

    return view;
}

export function tellusLinksComponent(queryString, headerText, headerLink=null, tooltip=null, extended = EXTENDED_TELL_LIST) {
    let view = template('tellusLinksComponent');

    view.addClass(' links-' + queryString);
    let header = view.find('.tellus-link-header');
    header.attr("href", "#" + (headerLink == null ? queryString : headerLink))
    if (tooltip != null) {
        header.attr("title", tooltip)
    }
    header.find('.tellus-link-header-text').text(headerText);

    return tellusLinkItems(queryString, header, view, extended ? tellusExtendedLinkItem : tellusLinkItem);
}

function tellusLinkItems(queryString, header, view, linkFunction) {
    let jsonURL = queryRoute(R_TELLS, queryString);
    $.getJSON(jsonURL, function (data) {
        header.find('.tell-count').text(Object.keys(data).length);

        for (let alias in data) {
            let tell = new Tell(alias, data[alias])
            view.append(linkFunction(tell));
        }
    });

    return view;
}

function tellusExtendedLinkItem(tell) {
    let linkItem = template('tellus-link-item-extended');
    tellusLinkItem(tell, linkItem);

    linkItem.find('.tlie-description').text(tell.description)

    let tags = linkItem.find('.tlie-tags')
    addTagBadges(tags, tell.tags)

    return linkItem;
}

function tellusLinkItem(tell, linkItem=null) {
    if (linkItem == null) {
        linkItem = template('tellus-link-item');
    }

    let linkTextItem = linkItem.find('.tellus-link')

    linkTextItem.text(tell.alias);

    if (tell.goURL) {
        linkItem.find('.tellus-link').attr("href", tellusGoURL(tell.alias));
    } else {
        linkItem.find('.tellus-link').attr("href", tellusTellURL(tell.alias));
    }
    linkItem.find('.tellus-edit').attr("href", "#t" + PARAM_SEPARATOR + tell.alias);

    let description =  tell.always_description

    // Highlight the Tell if it has errors (e.g., a link is not active)
    let tellErrors = tell.tellErrors
    if (tellErrors != null) {
        linkTextItem.addClass('tellus-link-error');
        description = description + '\n\nTellus Says:\n' + tellErrors;
    }

    linkItem.attr("title", description);

    return linkItem;
}

function prettify(value) {
    // todo: make this try to format dates more nicely as well as URLs
}


/**
 * Create a link to place in another element, if it looks like a URL.
 *
 * @param url the URL to turn into a link
 * @param linkText the text to use for the URL - defaults to the URL if unspecified
 * @param assumeIsLink treat what is passed for URL as a URL no matter what it looks like.
 * @param assumeIsEmail treat what is passed for as an email no matter what it looks like (if it is not a URL).
 *
 * @returns if the URL is a URL, a tellus-generic-url <a> element populated with the URL; or if the email is an email,
 *       makes it a 'mailto'.  Otherwise just returns the unmodified linkText.
 */
export function linkify(url, linkText=url, assumeIsLink=false, assumeIsEmail = false) {
    let displayURL = url;
    try {
        if (displayURL.startsWith('tellus:')) {
            // Special case where Tellus is returning an internal URL
            displayURL = displayURL.replace('tellus:', window.origin);
        }

        if (assumeIsLink || displayURL.startsWith('http')) {
            return buildHREF(linkText, displayURL)
        } else if (assumeIsEmail || displayURL.endsWith('@example.com')) {
            return buildHREF(linkText, displayURL, true)
        }
    } catch(error) {
        console.log("Error in linkify(): " + error);
    }

    return linkText;
}

/**
 * Convenience function to always treat a link as an email.
 */
export function linkifyEmail(url, linkText=url) {
    return linkify(url, linkText, false, true);
}

function buildHREF(linkText, urlOrEmail, isEmail=false) {
    let a = template(isEmail ? 'tellus-generic-email' : 'tellus-generic-url');

    a.text(linkText);
    if (isEmail) {
        a.attr("href", "mailto:" + urlOrEmail);
    } else {
        a.attr("href", urlOrEmail);
    }

    return a;
}

/**
 * Create a standard Go URL link for a Tell, using the current instance.
 *
 * @param alias the Tellus alias to link to.
 * @returns the GO URL
 */
export function tellusGoURL(alias) {
    return window.origin + '/' + alias;
}

/**
 * Returns the URL of the Tell page itself for a given Alias (as opposed to the GO URL, which will redirect).
 *
 * @param alias the Tell to link to.
 * @returns the Tell URL
 */
export function tellusTellURL(alias) {
    return '/#t.' + alias;
}

export function tellusGoLink(alias) {
    let linkItem = template('tellus-go-link');
    let url =  tellusGoURL(alias);

    linkItem.find('.tellus-go-href').text(url);
    linkItem.find('.tellus-go-href').attr("href", url);

    return linkItem;
}

export function infoMessage(messageText, error=false, clearPriors=true) {
    let messageRow = $('.tellus-message');
    if (clearPriors) {
        messageRow.text("");
    }
    let message = error ? template('tellus-danger') : template('tellus-info');
    message.text(messageText);
    messageRow.append(message);
}

export function addTagBadges(component, tagList) {
    for (let tag of tagList) {
        let tagItem = template('tellus-tag');
        tagItem.text(tag);
        tagItem.attr("href", linkQuery(tag));
        component.append(tagItem);
    }
}

export function addCategoryBadges(component, categoryList) {
    for (let category of categoryList) {
        let categoryItem = template('tellus-category');
        categoryItem.text(displayName(category));
        categoryItem.attr("href", linkQuery(category));
        categoryItem.attr("title", displayDescription(category));
        component.append(categoryItem);
    }
}

export function linkQuery(queryString) {
    return "#l." + queryString;
}

/////////////
// Multi-column Tables
/////////////
export function tellusMCTHeader(headerColumnNames) {
    return tellusMCTRow(headerColumnNames, 'multi-column-table-primary-col-header', 'multi-column-table-other-col-header')
}

export function tellusMCTDataRow(columnData) {
    return tellusMCTRow(columnData, 'multi-column-table-primary-col-row', 'multi-column-table-other-col-row')
}

function tellusMCTRow(columnData, primaryColumnTemplate, otherColumnTemplate) {
    let view = template('multi-column-table-row');
    let primaryColumn = template(primaryColumnTemplate);
    view.append(primaryColumn.append(columnData[0]));

    for (let i = 1; i < columnData.length; i++) {
        let column = template(otherColumnTemplate);
        view.append(column.append(columnData[i]))
    }

    return view;
}

/**
 * A wrapper around some Tell data coming back from Tellus to abstract away the underlying data format.
 * Here rather than tell.js for import sensibility.
 */
class Tell {
    constructor(alias, tellData) {
        this.alias = alias;
        this.tellData = tellData;
    }

    get goURL() {
        return this.tellData.go_url;
    }

    get description() {
        return this.tellData.description;
    }


    get always_description() {
        if (this.description != null) {
            return this.description;
        }
        return this.alias;
    }

    get tags() {
        return this.tellData.tags;
    }

    get tellErrors() {
        let errors = this.tellData[TELLUS_INFO]
        if (errors == null) {
            return null;
        }
        return JSON.stringify(errors);
    }
}
