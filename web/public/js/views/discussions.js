import {request} from "https://cdn.skypack.dev/@octokit/request";
import {relativeTimeAgo} from "./wiring.js";
import {tellusUserPageLink} from "./users.js";
import {linkify, tellusMCTDataRow, tellusMCTHeader} from "./components.js";

export default function () {
    let view = template('discussionsView');
    // Discussions Read Only Token
    let token = '';

    view.append(githubDiscussionTable(3, "Tellus", token));
    view.append(githubDiscussionTable(7, "Team", token));
    return view;
}

export function githubDiscussion(team, token) {
    return request(`GET /teams/${team}/discussions`, {
        baseUrl: "https://github.com/api/v3",
        headers: {
            Authorization: `token ${token}`,
        },
    });
};

export function githubDiscussionComments(team, token, discussionNumber) {
    return request(`GET /teams/${team}/discussions/${discussionNumber}/comments`, {
        baseUrl: "https://github.com/api/v3",
        headers: {
            Authorization: `token ${token}`,
        },
    });
};

export function githubDiscussionTable(team_id, team_name, token) {
    let view = template('discussionsView');

    let teamSection = template('multi-column-table-section');

    view.append(teamSection.append(team_name));
    let header =["Title", "Author", "Last Reply...", "...By", "Replies"];
    view.append(tellusMCTHeader(header));

    let discussions = githubDiscussion(team_id, token);
    let comments = []

    discussions.then(discussionResults => {
        comments = []
        discussionResults.data.forEach(discussion => {
            // console.log(`Processing: ${discussion.title}`)
            discussion.lastCommentAt = discussion.updated_at;
            discussion.lastCommentBy = discussion.author.login;
            comments.push(
                githubDiscussionComments(team_id, token, discussion.number).then(comments => {
                    if (comments.data.length > 0) {
                        let lastComment = comments.data[0];
                        discussion.lastCommentAt = lastComment.updated_at;
                        discussion.lastCommentBy = lastComment.author.login;
                        // console.log(`Commentating: ${discussion.title}: ${discussion.number}`)
                    }
                }))
        })
        return [comments, discussionResults.data];
    }).then(results => {
        Promise.all(results[0]).then(commentResults => {
            let discussionResults = results[1];
            // console.log(`Sorting and writing.`)
            discussionResults.sort((a, b) => Date.parse(b.lastCommentAt) - Date.parse(a.lastCommentAt));
            discussionResults.forEach(discussion => {
                view.append(tellusDiscussionTableRow(discussion));
            });
        })
    })

    return view;
}

export function tellusDiscussionTableRow(discussion) {
    return tellusMCTDataRow(
        [
            linkify(`${discussion.html_url}`, `${discussion.title}`),
            tellusUserPageLink(`${discussion.author.login}`),
            relativeTimeAgo(discussion.lastCommentAt),
            tellusUserPageLink(discussion.lastCommentBy),
            `${discussion.comments_count}`
        ]
    );
}


