import {DATA_SOCIALIZER, R_USER, TELLUS_USER_INFO} from "./wiring.js";
import {linkifyEmail, tellusMCTDataRow, tellusMCTHeader} from "./components.js";
import {tellusTellView} from "./tell.js";

export default function () {
    let view = template('usersView');

    view.append(tellusUserListNew())

    return view;
}


export function tellusUserListNew(userFilter=null, userNameHeader=null) {
    let view = template('usersMultiColumnView');

    let jsonURL = R_USER + '/';
    $.getJSON(jsonURL, function (data) {
        let tableHeader = ["Name", "Email", "Phone", "Links"];
        view.append(tellusMCTHeader(tableHeader));

        let appendedRows = 0;
        TellusUser.constructAndCacheFromJSON(data);

        for (let alias in data) {
            let user = TellusUser.lookupUser(alias);
            if (userFilter == null || userFilter.include(user)) {
                view.append(tellusMCTDataRow([user.userLink, linkifyEmail(user.email), user.phone, ""]));
                appendedRows += 1;
            }
        }

        let header = view.find('.user-name-header');
        let headerText = (userNameHeader == null) ? header.text() : userNameHeader;
        header.text(headerText + ' (' + appendedRows + ')');
    });

    return view;
}

export function tellusUserList(userFilter=null, userNameHeader=null) {
    let view = template('user-list');

    let jsonURL = R_USER + '/';
    $.getJSON(jsonURL, function (data) {
        let appendedRows = 0;
        for (let alias in data) {
            TellusUser.constructAndCache(alias, JSON.parse(data[alias]));
        }

        for (let alias in data) {
            let user = TellusUser.lookupUser(alias);
            if (userFilter == null || userFilter.include(user)) {
                view.append(tellusUserRow(user, userFilter));
                appendedRows += 1;
            }
        }

        let header = view.find('.user-name-header');
        let headerText = (userNameHeader == null) ? header.text() : userNameHeader;
        header.text(headerText + ' (' + appendedRows + ')');
    });

    return view;
}

export function tellusUserRow(user, userFilter=null) {
    let view = template('user-list-user');

    view.find('.user-name').append(user.userLink);
    if (userFilter != null) {
        userFilter.appendAdditionalInformation(user, view.find('.user-additional-info'))
    }

    return view;
}

/**
 * Returns the URL of the User page itself for a given User Alias (as opposed to the GO URL, which will redirect).
 *
 * @param userAlias the User to link to.
 * @returns the User URL
 */
export function tellusUserURL(userAlias) {
    return '/#u.' + userAlias;
}

export function tellusUserPageLink(username, displayText=null) {
    let linkItem = template("tellus-user-page-link");
    linkItem.text(displayText ? displayText : username);
    linkItem.attr("href", tellusUserURL(username));

    return linkItem;
}

export function constructUser(username, data) {
    return new TellusUser(username, data);
}

/**
 * Return the User Link for the specified username.
 * If we have no active (cached) user with that username, just returns the text sent.
 */
export function activeUserLink(username) {
    let user = TellusUser.lookupUser(username);
    console.log(user)
    if (user) return user.userLink;
    return username;
}

/**
 * A wrapper around the user data coming back from Tellus, to abstract away the underlying data format.
 */
class TellusUser {
    static cachedUsers = {}

    constructor(alias, userData) {
        this.alias = alias;
        this.userTellData = userData;
    }

    /**
     * Construct a TellusUser and cache it locally for lookups.
     */
    static constructAndCache(alias, userData) {
        TellusUser.cachedUsers[alias] = new TellusUser(alias, userData);
        return TellusUser.cachedUsers[alias];
    }

    /**
     * Construct collection of TellusUsers from some JSON.
     */
    static constructAndCacheFromJSON(JSONData) {
        for (let alias in JSONData) {
            TellusUser.constructAndCache(alias, JSON.parse(JSONData[alias]));
        }
    }

    static lookupUser(alias) {
        return TellusUser.cachedUsers[alias];
    }

    /**
     * It is strongly encouraged to not use this directly outside of TellusUser but wrap in a getter like phone()
     */
    userInfo(key) {
        return this.userTellData.data[TELLUS_USER_INFO][key];
        // OMG Law of Demeter...at least it's localized...
    }

    /**
     * Return the Full Name for the specified alias.  If we have no cached user with that alias, just returns it.
     */
    static fullName(alias) {
        let user = TellusUser.lookupUser(alias);
        if (user) return user.fullName;
        return alias;
    }

    get username() {
        return this.alias;
    }

    get email() {
        return this.userTellData.email;
    }

    AVATAR_URL = "Avatar URL"
    CONFLUENCE = "Confluence"
    EMAIL      = "Email"
    FULL_NAME  = "Full Name"
    GITHUB     = "Github"
    PHONE      = "Phone"

    get phone() {return this.userInfo(this.PHONE);}
    get confluence() {return this.userInfo(this.CONFLUENCE);}
    get github() {return this.userInfo(this.GITHUB);}
    get avatarURL() {return this.userInfo(this.AVATAR_URL);}

    get fullName() {
        let name = this.userTellData.fullName;
        if (name) return name;
        return this.username;
    }

    /**
     * Return the User object for my Coffee Pair's user name, or null if it is not cached.
     */
    get coffeePairUser() {
        return TellusUser.lookupUser(this.coffeePair);
    }

    get coffeePair() {
        try {
            let socializerData = this.userTellData.data[DATA_SOCIALIZER]
            if (socializerData != null) {
                return socializerData['coffee-pair'];
            }
            return null;
        } catch (error) {
            console.log('Error in coffeePair:  ' + this.userTellData);
            throw error;
        }
    }

    coffeeHistory(pairsBack = 5) {
        try {
            let socializerData = this.userTellData.data[DATA_SOCIALIZER]
            if (socializerData != null) {
                let coffeeHistory = socializerData['coffee-history'];
                if (coffeeHistory != null) {
                    let coffeeHistoryList = Object.keys(coffeeHistory);
                    return coffeeHistoryList.slice(Math.max(coffeeHistoryList.length - pairsBack, 0));
                }
            }
            return ["No coffee history."];
        } catch (error) {
            console.log('Error in coffeeHistory:  ' + this.userTellData);
            throw error;
        }
    }

    get hasCoffeePair() {
        return this.coffeePair != null;
    }

    get isCoffeeBotOn() {
        return this.userTellData.tags.includes("coffee-bot");
    }

    get userLink() {
        return tellusUserPageLink(this.username, this.fullName)
    }
}


//////// Single User View

export function tellusUserView(userAlias) {
    // For now, just me trying out the new interface
    // if (userAlias !== 'dgroothuis') return tellusTellView(userAlias);

    let view = template('tellusUserPageView');
    let leftCol = view.find('.tellusUserLeftColumn');
    let midCol = view.find('.tellusUserMiddleColumn');
    let rightCol = view.find('.tellusUserRightColumn');

    let jsonURL = R_USER + '/' + userAlias;
    $.getJSON(jsonURL, function (data) {
        let user = TellusUser.constructAndCache(userAlias, data);

        leftCol.append(tellusUserLinks(user))
        leftCol.append(coffeeBotCard(user));

        midCol.append(tellusUserCard(user));
        // midCol.text("Middle Column TODO")

        // rightCol.text("Right Column TODO")
    });

    // view.append(tellusTellView(userAlias));  // Remove this once this is all working
    return view;
}

export function tellusUserCard(user) {
    let userCard = template('tellusUserCard');

    userCard.find('.userCardFullName').text(user.fullName);
    userCard.find('.userCardPhone').text(user.phone);

    userCard.find('.userCardEmail').text(user.email);
    userCard.find('.userCardEmail').attr("href", "mailto:" +user.email);
    // userCard.find('.userCardAvatar').attr("src", user.avatarURL)  TODO: uncomment when figure out Confluence access

    return userCard;
}

export function tellusUserLinks(user) {
    let userCard = template('tellusUserLinks');
    userCard.find('.userCardHomepage').attr("href", user.confluence);

    let github = user.github;
    if (github == null) {
        userCard.remove('.userCardGithubLI')
    } else {
        userCard.find('.userCardGithub').attr("href", user.github);
    }

    return userCard;
}

export function coffeeBotCard(user) {
    let userCard = template('coffeeBotCard');

    userCard.find('.coffeePair').append(tellusUserPageLink(user.coffeePair));
    let coffeeHistory = template('tellus-tiny-note');
    coffeeHistory.text("Last 5: " + user.coffeeHistory().join(', '));
    userCard.find('.coffeeHistory').append(coffeeHistory)

    return userCard;
}