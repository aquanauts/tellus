import {tellusLinksComponent} from "./components.js";
import {DNS_ALL, DNS_ACTIVE} from "./wiring.js";


export function activeDNSLinksList() {
    return tellusLinksComponent(DNS_ACTIVE, "Active DNS Links", 'dns')
}

export default function() {
    let view = template('dnsView');
    let leftCol = view.find(".left-dns-col")
    let rightCol = view.find(".right-dns-col")

    leftCol.append(activeDNSLinksList());
    rightCol.append(tellusLinksComponent(DNS_ALL, "All DNS Entries", 'dns'));

    return view;
}

