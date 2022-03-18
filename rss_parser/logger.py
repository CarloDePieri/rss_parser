import logging

log = logging.getLogger("uvicorn.error")


def cache_log(msg: str) -> None:
    log.info(f"[CACHE] {msg}")


def selenium_error(msg: str) -> None:
    log.error(f"[SELENIUM] {msg}")


def selenium_log(msg: str) -> None:
    log.info(f"[SELENIUM] {msg}")
