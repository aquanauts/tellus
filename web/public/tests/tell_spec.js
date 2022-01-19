import {tellusTellView} from '../js/views/tell.js';

describe('Tell View', function () {
    let view;
    let mockRequest;

    let mockData = {
        "alias": "tellus",
        "go_url": "/tellus",
        "tags": "go, tellus",
        "categories": "tellus-internal, tellus-go",
        "read-only": "true",
        "z-audit-info": "{\"created\": \"2020-03-09T18:25:58.666366+00:00\", \"created_by\": \"tell_spec\", \"last_modified\": \"2020-03-09T18:26:00.302119+00:00\", \"last_modified_by\": \"tell_spec\"}}"
    };

    beforeEach(function () {
        mockRequest = spyOn($, 'getJSON');
        view = tellusTellView("tellus");
        mockRequest.calls.argsFor(0)[1](mockData);
    });


    it('Has our expected table elements', function () {
        expect(view.find('.tell-alias').length).toEqual(1);
        expect(view.find('.tell-url').length).toEqual(1);
        expect(view.find('.tell-tags').length).toEqual(1);
        expect(view.find('.tell-categories').length).toEqual(1);
    });


    it('Contains our mock data', function () {
        expect(view.find('.tell-alias').text()).toEqual("tellus");
        expect(view.find('.tell-url').text()).toEqual("/tellus");
        expect(view.find('.tell-tags').text()).toEqual("go, tellus");
        // expect(view.find('.tell-categories').find('.tellus-category').length).toEqual(2);
    });
});

