import datetime
from time import sleep

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
    @abstractmethod
    def parse_entry(
        cls, entry: feedparser.util.FeedParserDict, browser: Browser
    ) -> str:
        pass

    @classmethod
    def get_xml_feed(cls, limit: int = -1) -> str:
        feed = feedparser.parse(cls.url)

        entries = []

        browser = Browser()

        if limit == -1:
            # Use the default_limit
            limit = cls.default_limit

        # Iterate over feed["entries"], allowing skipping entries
        read_entries = 0
        while len(entries) < limit and read_entries < len(feed["entries"]):
            entry = feed["entries"][read_entries]
            read_entries += 1
            tries = 0
            while tries < 3:
                try:
                    log.debug(f"PARSING: {entry['link']} - {entry['title']}")
                    entries.append(cls.parse_entry(entry, browser))
                    break
                except SkipEntryException:
                    break
                except TimeoutError as e:
                    entries.append(
                        cls._get_broken_item(entry["link"], entry["title"], str(e))
                    )
                    log.error(f"SKIPPED: {entry['link']} - Timed out when parsing")
                except Exception as e:
                    entries.append(
                        cls._get_broken_item(entry["link"], entry["title"], str(e))
                    )
                    log.error(f"SKIPPED: {entry['link']} - Unknown error")
                tries += 1
                # wait a second, try to eliminate source availability errors
                sleep(1)

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
    def _get_broken_item(url: str, title: str, error: str) -> Item:
        return Item(
            title="BROKEN",
            link=url,
            description=f"<h2>[BROKEN]{title}</h2><p>Something went wrong when parsing <a href='{url}'>{url}</a></p><p>{error}</p>",
            guid=Guid(url),
        )


class SkipEntryException(Exception):
    """Signal that this entry should be skipped."""
