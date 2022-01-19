import {
    addCategoryBadges,
    addTagBadges,
    tellusDataBlock,
    tellusGoLink,
    tellusLinksComponent
} from "./components.js";
import {displayDataBlocks} from "./wiring.js";
import {activeUserLink} from "./users.js";

export function tellusTellView(queryString) {
    let view = template('tellusTellPageView');

    populateTellView(view, queryString, true);

    return view;
}

export function tellusEditTellView(queryString) {
    let view = template('tellusTellPageView');

    populateTellView(view, queryString, false);

    return view;
}

function appendDataBlocks(data, element) {
    // Hacky way of checking if there is a map with stuff in it...
    if (data.data && Object.keys(data.data).length > 0) {
        displayDataBlocks().forEach( function(dataBlockKey) {
          if (dataBlockKey in data.data) {
              element.append(tellusDataBlock(dataBlockKey, data.data[dataBlockKey]));
          }
        });
    }
}

function fillCommonViewData(subView, data) {
    subView.find('.tell-alias').text(data['alias']);
    subView.find('.tell-data').text(data['data']);

    addCategoryBadges(subView.find('.tell-categories'), data['categories']);
}

function populateReadOnlyView(data) {
    let subView = template('tellusTellReadOnlyView');
    fillCommonViewData(subView, data);

    subView.find('.tell-url').text(data['go_url']);
    subView.find('.tell-url').attr("href", data['go_url']);
    subView.find('.tell-description').text(data['description']);
    addTagBadges(subView.find('.tell-tags'), data['tags']);

    return subView;
}

function populateEditableView(data) {
    let subView = template('tellusTellEditableView');
    fillCommonViewData(subView, data);

    subView.find('.new_alias').val(data['alias']);  // Note this is special...
    subView.find('.go_url').val(data['go_url']);
    subView.find('.description').val(data['description']);

    let tags = subView.find('.tags');
    tags.val(data['tags'].join(', '));
    tags.selectize({
        delimiter: ',',
        persist: false,
        create: function(input) {
            return {
                value: input,
                text: input
            }
        }
    });
    return subView;
}

function populateRelatedTells(view, data) {
    let relatedTable = view.find('.tellusRelatedTells');

    let groups = data['groups'];
    let queryString = groups != null ? groups.join('.') : '';
    if (queryString !== '') {
        relatedTable.append(tellusLinksComponent(queryString, "Related Tells"));
    }
}

function showTellView(editable = false, queryString) {
    if (editable) {
        window.location = "#editTell" + PARAM_SEPARATOR + queryString;
    } else {
        window.location = "#t" + PARAM_SEPARATOR + queryString;
    }
}

function appendAuditBlock(auditData, element) {
    let auditString = "Tell created ";

    // Note - this will (I believe) convert to the local time zone, but
    // be wary if we ever care about this information in-browser beyond as info
    auditString += moment(auditData['created']).format("MM-DD-YYYY hh:mm");
    auditString += " by '";
    auditString += auditData['created_by'];
    auditString += "' | last modified ";
    auditString += moment(auditData['last_modified']).format("MM-DD-YYYY hh:mm");
    auditString += " by '";
    auditString += auditData['last_modified_by'];
    auditString += "'";

    let block = template('tellus-audit-info');
    block.text(auditString);

    element.append(block);
}

function populateTellView(view, queryString, readView = false) {
    let tellTable = view.find('.tellusTellView');

    // This thing is a beast, mostly because I think it all needs to live inside this JSON call?
    // Would welcome someone with better js-fu telling me how to clean it up...
    $.getJSON('t' + PARAM_SEPARATOR + queryString, function (data) {
        let readOnly = !!data['read-only'];
        let alias = data['alias'];
        let goURL = data['go_url']

        let subView = (readView || readOnly) ? populateReadOnlyView(data) :  populateEditableView(data);
        if (goURL) {
            tellTable.append(tellusGoLink(alias));
        }
        tellTable.append(subView);

        if (readOnly) {
            subView.find('.tell-editable').remove();
        } else if (readView) {
            $("#tell-edit").click(function (event) {
                event.preventDefault();

                if ($(this).attr("value") === "tell-edit") {
                    showTellView(true, queryString)
                } else {
                    // Shouldn't be possible now...
                    console.log("UNKNOWN BUTTON/ACTION: " + $(this));
                }
            });
        } else {
            // The Tell is editable, and we are in edit mode
            // Handle buttons...seem to have to do this here, and not in a separate function
            // ...possibly because I don't know what I'm doing
            function updateTell(event) {
                let params = {
                    'alias': alias,
                    'new_alias': subView.find('.new_alias').val(),
                    'description': subView.find('.description').val(),
                    'tags': subView.find('.tags').val(),
                    'go_url': subView.find('.go_url').val(),
                };

                $.post("/t/update-tell", params, function (data) {
                    showTellView(false, data['alias']);
                });

                return false;  // Don't reload the page!
            }

            function deleteTell(event) {
                $.get("/t/" + alias + "/delete-tell", function (data) {
                    showView("#home");
                });

                return false;  // Don't reload the page!
            }

            $("#tell-update-form button").click(function (event) {
                event.preventDefault();

                if ($(this).attr("value") === "tell-update-submit") {
                    updateTell(event);
                } else if ($(this).attr("value") === "tell-update-cancel") {
                    showTellView(false, queryString);
                } else if ($(this).attr("value") === "tell-delete") {
                    deleteTell(event);
                } else {
                    // Shouldn't be possible now...
                    console.log("UNKNOWN BUTTON/ACTION: " + $(this));
                }
            });
        }

        populateRelatedTells(view, data);

        appendDataBlocks(data, tellTable);
        appendAuditBlock(data['z-audit-info'], tellTable);
    });

    return tellTable;
}