from coreason_jules_automator.utils.logger import logger  # type: ignore


def test_logger() -> None:
    logger.info("Test log")
    assert True
