import {addCategoryBadges, tellusLinksComponent} from "./components.js";
import {ALL_TELLS, displayCategories, displayDescription} from "./wiring.js";

export default function(queryString=ALL_TELLS) {
    let view = template('tellsView');

    let header = queryString === ALL_TELLS ? "All Tells" : queryStringDescription(queryString);

    addCategoryBadges(view.find('.tellus-categories'), displayCategories());
    view.append(tellusLinksComponent(queryString, header));

    return view;
}

export function queryStringDescription(category) {
    return displayDescription(category, false, "Tells with tags/categories: " + category)
}

