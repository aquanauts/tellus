from tellus.tellus_sources.github_helper import gethub, retrieve_valid_github_usernames
from tellus.tellus_sources.tellus_yaml_source import TellusYMLSource


def test_get_tellus_yml_files():
    found_files = TellusYMLSource.query_for_files(gethub())
    all_files = []
    tellus_files = []
    for github_file in found_files:
        all_files.append(f"{github_file.repository.name}: {github_file.name}")
        if TellusYMLSource.is_tellus_file(github_file):
            tellus_files.append(f"{github_file.repository.name}: {github_file.name}")

    print(all_files)

    assert (
        "tellus: tellus.yml" in tellus_files
    ), "Should retrieve a tellus.yml from Tellus' repo"
    assert (
        "tellus: .tellus.yml" in tellus_files
    ), "Should retrieve a .tellus.yml from Tellus' repo"
    assert (
        "tellus: .tellus.yaml" in tellus_files
    ), "Should retrieve a .tellus.yaml from Tellus' repo"
    assert (
        "tellus: tellus_yaml_source.py" in all_files
    ), "Should retrieve tellus_yaml_source.py from Tellus' repo..."
    assert (
        "tellus: tellus_yaml_source.py" not in tellus_files
    ), "...but tellus_yaml_source.py should not be considered a Tellus file."
    assert (
        "tellus: destroy-all-tellus.yml" in all_files
    ), "Should retrieve a destroy-all-tellus.yaml from Tellus' repo..."
    assert (
        "tellus: destroy-all-tellus.yml" not in tellus_files
    ), "Should destroy-all-tellus.yaml should not be considered a Tellus file."


def test_github_users():
    users = retrieve_valid_github_usernames()
    assert (
        "tellus" in users
    ), "We should always get the tellus user, even if we can't connect..."
