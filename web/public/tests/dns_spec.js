import dnsView from '../js/views/dns.js';
import {linkClass, DNS_ACTIVE, DNS_ALL} from "../js/views/wiring.js";

describe('DNS View', function () {
    let view;
    let mockRequest;

    let mockData = {
        "dray": "http://dray.github.com",
        "tellus": "http://tellus.github.com",
    };

    beforeEach(function () {
        mockRequest = spyOn($, 'getJSON');
        view = dnsView();
        mockRequest.calls.argsFor(0)[1](mockData);
    });

    it('Contains a single links component', function () {
        let view = dnsView();

        let dnsLinkView = view.find('.tellusLinksComponent');
        expect(dnsLinkView.length).toEqual(2);
    });

    it('Has two link groups', function () {
        expect(view.find('.tellus-link-group').length).toEqual(2);
        expect(view.find('.list-group-item.active').length).toEqual(2);
    });

    it('Contains our mock DNS Link data', function () {
        expect(view.find(linkClass(DNS_ACTIVE)).length).toEqual(1);
        let dnsView = view.find(linkClass(DNS_ACTIVE));

        expect(dnsView.find('.list-group-item.active').length).toEqual(1);
        expect(dnsView.find('.list-group-item.active').text()).toEqual("Active DNS Links");
        // Note: this indicates we expect these to be sorted server side...
        expect(view.find('.tellus-link-item:first .tellus-link').text()).toEqual("dray");
        let links = view.find('.tellus-link-item');
        let mockMap = new Map(Object.entries(mockData));
        expect(links.length).toEqual(mockMap.size);
        view.find('.tellus-link-item').each(function (index) {
            let link = $(this).find('.go-link');
            expect(link.attr("href")).toEqual(mockMap.get(link.text()));
        });
    });

    it('Contains our mock Other DNS table', function () {
        expect(view.find(linkClass(DNS_ALL)).length).toEqual(1);
        let dnsView = view.find(linkClass(DNS_ALL));

        expect(dnsView.find('.list-group-item.active').length).toEqual(1);
        expect(dnsView.find('.list-group-item.active').text()).toEqual("All DNS Entries");
        // right now, the js functionality is otherwise identical to the DNS link test...
    });
});
