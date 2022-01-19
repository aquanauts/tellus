import {constructUser, tellusUserList} from "./users.js";
import {getCurrentUsername} from "./../common.js";
import {R_USER} from "./wiring.js";

export default function () {
    let view = template('socialView');

    let coffeeBot = view.find('.tellus-coffee-bot');
    coffeeBot.show();
    coffeeBot.on('click', toggleCoffeeStatus);
    coffeeBotStatusForUser(getCurrentUsername(), coffeeBot, true);

    view.append(tellusUserList(new CoffeeFilter(), "Coffee Bot List"));

    return view;
}

class CoffeeFilter {  // Yes, it is named this way because it is funny
     include(user) {
        return user.isCoffeeBotOn || user.hasCoffeePair;
    }

    appendAdditionalInformation(user, element) {
         let pair = user.coffeePairUser;
         if (pair) {
             element.text("Coffee Pair: ");
             element.append(pair.userLink);
         } else {
             element.text("Will be scheduled in next coffee run!")
         }
    }
}

export function showCoffeeStatus() {
    coffeeBotStatusForUser(getCurrentUsername(), $('.social-link'))
}

export function coffeeBotStatusForUser(username, element, requiresLogIn=false) {
    if (username) {
        let jsonURL = R_USER + '/' + username;
        $.getJSON(jsonURL, function (data) {
            let current_user = constructUser(username, data);
            showCoffeeBotStatus(current_user.isCoffeeBotOn, element);
        });
    } else if (requiresLogIn) {
        console.log("No logged in user.  Hiding coffee bot.");
        element.text('Please log in to enable Coffee Bot.');
    }
}


export function showCoffeeBotStatus(isCoffeeBotOn, element) {
    if (isCoffeeBotOn) {
        element.find('.tellus-coffee-bot-off').hide();
        element.find('.tellus-coffee-bot-on').show();
    } else {
        element.find('.tellus-coffee-bot-off').show();
        element.find('.tellus-coffee-bot-on').hide();
    }
}

export function toggleCoffeeStatus() {
    $.post("/t/toggle-tag", {'alias': getCurrentUsername(), 'toggle-tag': 'coffee-bot'}, function (data) {
        window.location.reload()
    });
}