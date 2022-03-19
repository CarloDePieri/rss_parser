from abc import ABC, abstractmethod

from rss_parser.cache import Cache


class Parser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def cache(self) -> Cache:
        pass

    @staticmethod
    @abstractmethod
    def get_xml_feed() -> str:
        pass
