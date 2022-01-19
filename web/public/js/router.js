"use strict";
let routes = {};

const PARAM_SEPARATOR = '.';

function activateNavbar(hash) {
    $('.navbar .nav-link').removeClass('active');
    if (hash) {
        $(`.navbar .nav-link[href='${hash}']`).addClass('active');
    } else {
        $(`.navbar .nav-link[href='#home']`).addClass('active');
    }
}

/**
 * Clear the Tellus Messages.
 * This should probably move somewhere else?
 */
function clearMessages() {
    $('.tellus-message').empty();
}

function showView(hash) {
    clearMessages();
    var hashParts = hash.split(PARAM_SEPARATOR);  // NOTE - changed from standard '-' Tellus aliases allow dashes
    let viewName = hashParts[0];
    var viewFn = window.routes[viewName];
    if (viewFn) {
        triggerEvent('router.addView', viewName);
        $('.view-container').empty().append(viewFn(hashParts[1]));
        activateNavbar(hash);
    }
}

function routerOnReady(customRoutes) {
    window.routes = customRoutes;
    window.onhashchange = function() {
        showView(window.location.hash);
    };
    showView(window.location.hash);
}
