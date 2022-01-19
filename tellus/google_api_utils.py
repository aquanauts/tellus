import gspread
from googleapiclient.discovery import build
from gspread.utils import extract_id_from_url
from oauth2client.service_account import ServiceAccountCredentials

from tellus.configuration import VAULT_PATH, ADMIN_ACCOUNT_DELEGATE

RETRIES = 3

SCOPES_SHEETS = [
    "https://www.googleapis.com/auth/drive",
    "https://spreadsheets.google.com/feeds",
]
DEFAULT_DIRECTORY_FIELDS = ["name", "primaryEmail", "phones"]

def _service_account_credentials(scopes, delegated_account=None):
    client_config = get_credentials_from_vault(path=VAULT_PATH)

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        client_config, scopes=scopes
    )
    if delegated_account:
        return credentials.create_delegated(delegated_account)

    return credentials


def _authorized_gspread():
    return gspread.authorize(_service_account_credentials(SCOPES_SHEETS))


def _authorized_service(credentials, api, version="v3"):
    """
    Gets us an authorized Google API service. Defaults to v3:  https://developers.google.com/drive/api/v3/reference
    """
    service = build(api, version, credentials=credentials, cache_discovery=False)

    return service


def _authorized_drive():
    return _authorized_service(_service_account_credentials(SCOPES_SHEETS), "drive")


def get_spreadsheet_by_key(sheet_key):
    return _authorized_gspread().open_by_key(sheet_key)


def get_spreadsheet_by_url(sheet_url):
    return _authorized_gspread().open_by_url(sheet_url)


def extract_key(document_url):
    return extract_id_from_url(document_url)


def key_from_url(document_url):
    return extract_id_from_url(document_url)


def file_last_updated(document_key):
    drive = _authorized_drive()
    # pylint: disable=no-member
    metadata = (
        drive.revisions()
        .get(fileId=document_key, revisionId="head", fields="modifiedTime")
        .execute()
    )
    return metadata.get("modifiedTime")


def retrieve_gsuite_user_directory():
    """
    :return: our company directory as a dict, keyed by primary email.
    """
    credentials = _service_account_credentials(
        ["https://www.googleapis.com/auth/admin.directory.user.readonly"],
        delegated_account=ADMIN_ACCOUNT_DELEGATE,  # For now...
    )

    service = build(
        "admin", "directory_v1", credentials=credentials, cache_discovery=False,
    )

    parameters = {
        "domain": "",
        "maxResults": 250,
        "projection": "basic",
        "viewType": "domain_public",
    }
    # pylint: disable=no-member
    result = service.users().list(**parameters).execute()["users"]
    user_map = {}
    for user in result:
        user_map[user["primaryEmail"]] = user

    return user_map


def paste_csv(contents, sheet, cell):
    wks = None
    if "!" in cell:
        (tabName, cell) = cell.split("!")
        wks = sheet.worksheet(tabName)
    else:
        wks = sheet.sheet1
    wks.clear()
    (firstRow, firstColumn) = gspread.utils.a1_to_rowcol(cell)

    body = {
        "requests": [
            {
                "pasteData": {
                    "coordinate": {
                        "sheetId": wks.id,
                        "rowIndex": firstRow - 1,
                        "columnIndex": firstColumn - 1,
                    },
                    "data": contents,
                    "type": "PASTE_NORMAL",
                    "delimiter": ",",
                }
            }
        ]
    }
    for _ in range(RETRIES):
        try:
            res = sheet.batch_update(body)
            return res
        except gspread.exceptions.APIError:
            pass

    raise Exception(f"Failed {RETRIES} attempts to update gsheet")
