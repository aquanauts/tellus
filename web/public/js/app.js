import homeView from './views/home.js';
import goView from './views/go.js';
import tellsView from './views/tells.js';
import searchView from './views/search.js';
import {tellusTellView, tellusEditTellView} from './views/tell.js';
import sourcesView from './views/sources.js';
// import discussionsView from './views/discussions.js';
import usersView from "./views/users.js";
import socializerView from "./views/socializer.js";
import toolsView from './views/tools.js';
import debugView from './views/components.js';
import dnsView from './views/dns.js';
import {tellusUserView} from "./views/users.js";

/**
 * Defines the routes for the header to various views.
 * The one character entries map to the Command Routes in wiring.js
 */
export function routes() {
    return {
        '': homeView,
        '#': homeView,
        '#home': homeView,
        '#go': goView,
        '#g': goView,
        '#l': tellsView,
        '#tells': tellsView,
        '#tell': tellusTellView,
        '#t': tellusTellView,
        '#editTell': tellusEditTellView,
        '#e': searchView,
        '#search': searchView,
        '#u': tellusUserView,
        '#who': usersView,
        '#social': socializerView,
        '#sources': sourcesView,
        // '#discussions': discussionsView,  // tellus-task: this is deprecated, remove eventually
        '#debug': debugView,
        // These two may be deprecated...
        '#dns': dnsView,
        '#tools': toolsView,
    }
}
