from time import sleep
from typing import TypeVar, Callable

T = TypeVar("T")


def wait_for(fun: Callable[[], T], ticks: int = 10) -> T:
    """Keeps calling fun until it returns something different from None, then return it.

    Keeps going waiting exponentially more time until it returns or times out with a TimeoutError."""
    counter = 1
    while True:
        node = fun()
        if node:
            return node
        sleep(0.1 * counter)
        counter += 1
        if counter > ticks:
            raise TimeoutError
