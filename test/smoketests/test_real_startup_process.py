import sys

from tellus.main import main


def test_main(fs):
    """
    This is a smoke test that runs the true Tellus startup, and allows assertion of things that should
    be true at the end.  This is a smoke test because it will act against the real data sources,
    and thus should be used carefully.
    """
    main([])
