import {infoMessage} from "./components.js";
import {displayTimestamp, R_SOURCES} from "./wiring.js";

export default function () {
    let view = template('sourcesView');
    let list = view.find('.sourcesList');
    let queryString = "/" + R_SOURCES;

    $.getJSON(queryString, function (data) {
        for (let source_id in data) {
            let displayName = data[source_id].display_name;
            let description = data[source_id].description;
            let sourceItem = template('source-item')
            // sourceItem.find('.source-id').text(source);
            sourceItem.find('.source-display-name').text(displayName);
            sourceItem.find('.source-description').text(description);
            sourceItem.find('.tellus-source-info').text(
                data[source_id].status + ', '
                + displayTimestamp(data[source_id].last_run)
                + '  ["' + data[source_id].last_run_message + '"]'
            );

            sourceItem.find('.load-source').click(function (event) {
                event.preventDefault();

                $.getJSON(`/${R_SOURCES}/${source_id}/load`, function(message){});
                infoMessage("Loading '" + source_id + "'...");
            });

            list.append(sourceItem);
        }
    });

    view.find(".load-all-sources").click(function (event) {
        event.preventDefault();

        $.getJSON(`/${R_SOURCES}/load-all`, function (message) {});
        infoMessage("Loading all sources...");
    });


    return view;
}