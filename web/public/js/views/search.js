import {addCategoryBadges, tellusLinksComponent} from "./components.js";
import {ALL_TELLS, displayCategories} from "./wiring.js";
import {queryStringDescription} from "./tells.js";

export default function(queryString=ALL_TELLS) {
    let view = template('tellsView');

    let header = queryString === ALL_TELLS ? "All Tells" : `Search Results for ${queryString}`;

    view.append(tellusLinksComponent(queryString, header));

    return view;
}
