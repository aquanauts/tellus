import tellsView from '../js/views/tells.js';

describe('Tells View', function () {
    let view;
    let mockRequest;

    let mockData = {
        "dray": "http://dray.github.com",
        "tellus": "/tellus",
        "vfh": "http://veryfinehat.com",
    };

    beforeEach(function () {
        mockRequest = spyOn($, 'getJSON');
        view = tellsView();
        mockRequest.calls.argsFor(0)[1](mockData);
    });

    it('Contains a single links component', function () {
        let view = tellsView();

        let tellsLinkView = view.find('.tellusLinksComponent');
        expect(tellsLinkView.length).toEqual(1);
    });

    it('Shows a title row', function () {
        expect(view.find('.list-group-item.active').length).toEqual(1);
        expect(view.find('.list-group-item.active').text()).toEqual("All Tells");
    });

    it('Contains a link to all of our mock data', function () {
        expect(view.find('.tellus-link-group').length).toEqual(1);
        expect(view.find('.tellus-link-item:first .tellus-link').text()).toEqual("dray");
        let links = view.find('.tellus-link-item');
        let mockMap = new Map(Object.entries(mockData));
        expect(links.length).toEqual(mockMap.size);
        view.find('.tellus-link-item').each(function (index) {
            let link = $(this).find('.go-link');
            expect(link.attr("href")).toEqual(mockMap.get(link.text()));
        });
    });
});
