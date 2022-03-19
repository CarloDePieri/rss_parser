import datetime

import feedparser

from abc import ABC, abstractmethod
from rfeed import Feed, Item, Guid

from rss_parser.cache import Cache
from rss_parser.logger import log
from rss_parser.selenium import Browser


class Parser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def url(self) -> str:
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
    def parse_source(cls, url: str, browser: Browser) -> str:
        pass

    @classmethod
    def get_xml_feed(cls, limit: int = -1) -> str:
        feed = feedparser.parse(cls.url)

        entries = []

        browser = Browser()

        if limit == -1:
            # Use the default_limit
            limit = cls.default_limit

        for entry in feed["entries"][:limit]:
            try:
                entries.append(cls.parse_entry(entry, browser))
            except TimeoutError:
                entries.append(cls._get_broken_item(entry["link"]))
                log.error(f"SKIPPED: {entry['link']} - Timed out when parsing")
            except Exception as e:
                entries.append(cls._get_broken_item(entry["link"]))
                log.error(f"SKIPPED: {entry['link']} - Unknown error")

        browser.quit()

        feed = Feed(
            title=feed["feed"]["title"],
            link=feed["feed"]["link"],
            description=feed["feed"]["subtitle"],
            language=feed["feed"]["language"],
            lastBuildDate=datetime.datetime.now(),
            items=entries,
        )

        return feed.rss()

    @staticmethod
    def _get_broken_item(url: str) -> Item:
        return Item(
            title="BROKEN",
            link=url,
            description=f"Something went wrong when parsing <a href='{url}'>{url}</a>",
            guid=Guid(url),
        )
