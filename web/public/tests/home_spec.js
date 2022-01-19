import homeView from '../js/views/home.js';

describe('Home View', function () {
    it('Contains the expected number of lists', function () {
        let view = homeView();
        let linkComponents = view.find('.tellusLinksComponent');
        expect(linkComponents.length).toEqual(3);
    });
});
