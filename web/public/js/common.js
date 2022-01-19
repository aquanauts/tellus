'use strict';

import {getVersion, R_USER, TELLUS_APP_USERNAME, TELLUS_USER} from "./views/wiring.js";
import * as Cookies from "../vendor/jscookie-2.2.1/js.cookie.js"; // ACTUALLY USED
import {infoMessage} from "./views/components.js";
import {constructUser, tellusUserPageLink, tellusUserURL} from "./views/users.js";
import {showCoffeeStatus} from "./views/socializer.js";

const LOCAL_USER = 'local_tellususer';  // js visible cookie for user

export function setupCommonUI() {
    $('.tellus-version').text("Tellus v" + getVersion());
}

function setCurrentUsername(username) {
    console.log("setCU");
    if (username != null && username !== TELLUS_APP_USERNAME) {
        window.Cookies.set(LOCAL_USER, username);
        console.log("setCU: " + username );
    } else {
        window.Cookies.remove(LOCAL_USER);
        console.log("setCU remove ");
    }
}

export function getCurrentUsername() {
    let currentUser = window.Cookies.get(LOCAL_USER);
    if (currentUser === TELLUS_APP_USERNAME) {
        return null;
    }

    return currentUser;
}

export async function displayCurrentUser() {
    let currentUser = getCurrentUsername();
    let serverUser = await $.get("/m/whoami");

    if (serverUser == null) {
        console.log("No user - should only be possible in a dev environment.");
    } else if (currentUser !== serverUser) {
        setCurrentUsername(serverUser);
        window.location.reload();
    }

    let login = template('tellus-current-user');
    if (currentUser != null) {
        login.append(tellusUserPageLink(currentUser))
    } else {
        console.log("No user - should only happen in a dev environment.");
        login.text("No User");
    }

    $('.navbar-username').append(login);
}

export function setupSocialElements() {
    showCoffeeStatus();
}
