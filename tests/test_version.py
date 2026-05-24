from importlib.metadata import version

import cept


def test_runtime_version_matches_package_metadata() -> None:
    assert cept.__version__ == version("cept")
