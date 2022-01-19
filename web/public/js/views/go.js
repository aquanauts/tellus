import {tellusLinksComponent, infoMessage} from "./components.js";

export default function (newTellAlias) {
    let view = template('goView');

    if (newTellAlias != null) {
        infoMessage("There is currently no Go Link for '" + newTellAlias + "'.  Please create one below, if you like.");
    }

    view.append(goFormComponent(newTellAlias));
    view.append(tellusLinksComponent("go", "Go Links"));

    return view;
}


export function goFormComponent(newTellAlias) {
    let view = template('goFormComponent');
    let response = view.find('.go-response');

    view.find('.alias').val(newTellAlias);

    function submitGoData(event) {
        let alias = view.find('.alias').val();
        let url = view.find('.go_url').val();
        let tags = view.find('.tags').val();

        let params = {
            'alias': alias,
            'go_url': url,
            'tags': tags,
        };

        $.post("/g", params, function (data) {
            showView(window.location.hash)
        });

        return false; // Don't reload the page!
    }

    view.find("#go-form").on('submit', submitGoData);

    return view;
}

window.addEventListener('load', function () {
    let forms = document.getElementsByClassName('needs-validation');
    let validation = Array.prototype.filter.call(forms, function (form) {
        form.addEventListener('submit', function (event) {
            if (form.checkValidity() === false) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}, false);

