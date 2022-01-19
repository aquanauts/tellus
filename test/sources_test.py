import logging

import pytest

from tellus.sources import (
    Sourcer,
    Source,
    DuplicateSourceException,
    STATUS_COMPLETED,
    STATUS_NOT_RUN,
    STATUS_FAILED,
)
from tellus.tell import InvalidAliasException
from tellus.tellus_utils import now_string
from test.tells_test import create_test_teller

SRC_TEST = "testing-source"


class FakeSource(Source):
    def __init__(
        self,
        source_id=SRC_TEST,
        description="A no-op source just used for testing purposes.",
        boom=False,
        run_restriction=None,
        teller=None,
    ):
        super().__init__(
            teller,
            source_id=source_id,
            description=description,
            run_restriction=run_restriction,
        )
        self._run_result = None
        self._boom = boom

    async def load_source(self):
        if self._boom:
            raise Exception("Boom.")

        self._run_result = f"Source {self.source_id} ran at {now_string()}"
        logging.info(self._run_result)
        return "Fake Source Completed"

    @property
    def run_result(self):
        return self._run_result


async def test_source_basics():
    teller = create_test_teller()
    try:
        FakeSource("Testing Source", "an invalid source name")
        pytest.fail("Having an invalid Source name should raise an exception.")
    except InvalidAliasException:
        pass

    source = FakeSource("test-source-info", "test source", teller=teller)

    assert source.source_id == "test-source-info"

    assert not teller.has_tell(
        source.source_tell_alias
    ), "The source tell is presently lazily constructed."
    source_tell = source.source_tell
    assert source_tell is not None
    assert source_tell.alias == "tellus-source-test-source-info"

    assert source.description == "test source"
    assert (
        source.last_run is None
    ), "Before the source is run, there will be no last run"
    assert (
        source.display_name == source.source_id
    ), "If no Display name is specified, Display Name == Source ID"

    info = source.source_info()
    assert info["source_id"] == "test-source-info"
    assert info["description"] == "test source"
    assert info["last_run"] is None
    assert info["last_run_message"] == STATUS_NOT_RUN
    assert info["status"] == STATUS_NOT_RUN

    await Sourcer.run_load_source(source)
    assert source.last_run is not None, "After a load, should have a last run time"

    info = source.source_info()
    assert info["source_id"] == "test-source-info"
    assert info["description"] == "test source"
    assert info["last_run"] == source.last_run
    assert info["last_run_message"] == "Fake Source Completed"
    assert info["status"] == STATUS_COMPLETED

    boomer = FakeSource("boom-source", "OK, boomer", True)
    await Sourcer.run_load_source(boomer)
    info = boomer.source_info()
    assert (
        info["status"] == STATUS_FAILED
    ), "Tellus should continue after a Source exception, but should show that the Source Failed"
    assert (
        info["last_run_message"]
        == "'boom-source' source failed to load, with exception: Exception('Boom.')"
    ), "Tellus should get a message back on why it failed."
    assert boomer.last_run is not None


def test_enabled_sources():
    teller = create_test_teller()
    sourcer = Sourcer(teller, [FakeSource(), FakeSource("also-wik", "Another source")])
    assert sourcer.active_source_ids() == [SRC_TEST, "also-wik"]

    try:
        Sourcer(
            teller,
            [
                FakeSource(),
                FakeSource("also-wik", "Another source"),
                FakeSource("also-wik", "Another another source"),
            ],
        )
        pytest.fail(
            "Should have thrown an exception when trying to add two sources with the same source id."
        )
    except DuplicateSourceException:
        pass


async def test_load_source():
    teller = create_test_teller()
    source = FakeSource("test-load-source", "Test loading an individual source.")
    sourcer = Sourcer(teller, [source])

    assert source.run_result is None
    await sourcer.load_source_for_id("test-load-source")
    assert source.run_result is not None


async def test_source_should_run():
    always_source = FakeSource("always-run", "Test run timing/scheduling")
    once_source = FakeSource(
        "run-once", "Test run timing/scheduling", run_restriction=Source.RUN_ON_STARTUP
    )

    teller = create_test_teller()
    sourcer = Sourcer(teller, [always_source, once_source])

    assert always_source.should_run
    assert once_source.should_run

    await sourcer.load_sources()
    assert always_source.should_run
    assert (
        not once_source.should_run
    ), "Once a RUN_ON_STARTUP source has been run, it shouldn't run again until Tellus restarts"

    always_last = always_source.last_run
    once_last = once_source.last_run
    await sourcer.load_sources()
    assert always_source.last_run != always_last
    assert once_source.last_run == once_last

    # Just explicitly testing this path as well
    once_again = FakeSource(
        "run-once", "Test run timing/scheduling", run_restriction=Source.RUN_ON_STARTUP
    )
    await Sourcer.run_load_source(once_again)
    again_last = once_again.last_run
    assert not once_again.should_run
    await Sourcer.run_load_source(once_again)
    assert once_again.last_run == again_last


def test_source_tell():
    pass
