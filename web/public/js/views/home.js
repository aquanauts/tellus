import {tellusLinksComponent} from "./components.js";
import {activeDNSLinksList} from "./dns.js";
import {TOOLS, isLocalPersistence} from "./wiring.js";

export default function() {
    let view = template('homeView');
    let leftCol = view.find(".left-home-col");
    let centerCol = view.find(".center-home-col");
    let rightCol = view.find(".right-home-col");

    if (isLocalPersistence()) {
        let messageRow = view.find('.tellus-message');
        let danger = template('tellus-danger');
        danger.text("Welcome to Tellus.  WARNING: currently using local persistence - data will not persist across deployments.");
        messageRow.append(danger);
    }

    leftCol.append(tellusLinksComponent(TOOLS, "Tools", 'tools'));
    centerCol.append(tellusLinksComponent("go", "Go Links [+]", null,"Click here to create a Go link"));
    rightCol.append(activeDNSLinksList());

    return view;
}
