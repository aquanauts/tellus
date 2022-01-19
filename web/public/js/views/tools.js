import {tellusLinksComponent} from "./components.js";
import {TOOLS} from "./wiring.js";

export default function() {
    let view = template('toolsView');

    view.append(tellusLinksComponent(TOOLS, "Tools"));

    return view;
}
