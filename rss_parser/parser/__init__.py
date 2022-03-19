from abc import ABC, abstractmethod

from rss_parser.cache import Cache
from rss_parser.selenium import Browser


class Parser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def default_limit(self) -> int:
        pass

    @property
    @abstractmethod
    def cache(self) -> Cache:
        pass

    @classmethod
    @abstractmethod
    def get_xml_feed(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def parse_source(cls, url: str, browser: Browser) -> str:
        pass
