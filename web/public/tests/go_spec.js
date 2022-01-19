import goView from '../js/views/go.js';
import {goFormComponent} from '../js/views/go.js';
import {tellusLinksComponent} from "../js/views/components.js";

describe('Go View', function () {
    it('Contains a Go Form and a Go View', function () {
        let view = goView();
        let goFormView = view.find('.goFormComponent');
        expect(goFormView.length).toEqual(1);
        let goLinkView = view.find('.tellusLinksComponent');
        expect(goLinkView.length).toEqual(1);
    });
});

describe('Go Link View', function () {
    let view;
    let mockRequest;

    let mockData = {
        "tellus": "/tellus",
        "apple": "http://apple.com",
    };

    beforeEach(function () {
        mockRequest = spyOn($, 'getJSON');
        view = tellusLinksComponent("go", "Go Links");
        mockRequest.calls.argsFor(0)[1](mockData);
    });


    it('Shows a title row', function () {
        expect(view.find('.list-group-item.active').length).toEqual(1);
        expect(view.find('.list-group-item.active').text()).toEqual("Go Links");
    });

    it('Contains a link to all of our mock data', function () {
        expect(view.find('.tellus-link-header').length).toEqual(1);
        expect(view.find('.tellus-link-item:first .tellus-link').text()).toEqual("tellus");
        let links = view.find('.tellus-link-item');
        let mockMap = new Map(Object.entries(mockData));
        expect(links.length).toEqual(mockMap.size);
        view.find('.tellus-link-item').each(function (index) {
            let link = $(this).find('.go-link');
            expect(link.attr("href")).toEqual(mockMap.get(link.text()));
        });
    });
});


describe('Go Form View', function () {
    let view;
    let mockRequest;

    let mockData = {
        "tellus": "/tellus"
    };

    beforeEach(function () {
        mockRequest = spyOn($, 'post');
        view = goFormComponent();
        // mockRequest.calls.argsFor(0)[1](mockData);
    });

    it('Has the expected form elements', function () {
        expect(view.find('.alias').length).toEqual(1);
        expect(view.find('.go_url').length).toEqual(1);
        expect(view.find('.go-submit').length).toEqual(1);
    });

    it('Allows us to submit a new URL', function () {
        view.find('#alias').val('vfh');
        view.find('#go_url').val('http://veryfinehat.com');
        view.find('#go-submit-btn').click();

        // figure out how to properly implement this test
        // expect(view.find('.go-response').text()).toEqual("Saved!");
    });
});
