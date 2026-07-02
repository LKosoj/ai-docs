import logging


LOGGER_NAME = "ai_docs"


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[ai-docs] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    for handler in logger.handlers:
        handler.setLevel(level)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
