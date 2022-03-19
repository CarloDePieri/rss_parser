import sqlite3
import datetime
from typing import Optional, Dict

from rfeed import Item, Feed, Guid
import feedparser
from feedparser.util import FeedParserDict
from dateutil import parser, tz
from bs4 import BeautifulSoup

from rss_parser.cache import Cache
from rss_parser.logger import cache_log, log
from rss_parser.parser import Parser
from rss_parser.selenium import Browser
from rss_parser.utils import wait_for


def parse_entry(entry: FeedParserDict, browser: Browser) -> Item:
    link = entry["link"]
    title = entry["title"]

    item = NasaIOTDCache.recover_from_cache(link)

    if not item:
        #
        # No cached entry, we need to parse it
        #
        browser.open(link)

        article = wait_for(
            lambda: BeautifulSoup(browser.get_page_source(), "html.parser").find(
                "div", class_="article-body"
            )
        )

        image_node = article.find("div", class_="feature-image-container")
        text_node = article.find("div", class_="text")
        author_node = text_node.find("div", class_="editor")

        image = str(image_node).replace(
            'href="/sites', 'href="https://www.nasa.gov/sites'
        )
        text = str(text_node)
        description = image + "<br>" + text
        author = str(author_node.text).replace("Editor: ", "")

        tz_dict = {
            "EST": tz.gettz("America/New_York"),
            "EDT": tz.gettz("America/New_York"),
        }
        published = parser.parse(entry["published"], tzinfos=tz_dict)

        # Save the parsed data to the cache
        NasaIOTDCache.save_to_cache(link, title, published, author, description)
    else:
        published = parser.parse(item["published"])
        author = item["author"]
        description = item["description"]

    return Item(
        title=title,
        link=link,
        description=description,
        author=author,
        guid=Guid(link),
        pubDate=published,
    )


class NasaIOTDCache(Cache):
    @staticmethod
    def init() -> None:
        connection = sqlite3.connect(Cache.DB)
        cursor = connection.cursor()
        cursor.execute(
            """ SELECT count(name) FROM sqlite_master WHERE type='table' AND name='nasa_iotd' """
        )
        if cursor.fetchone()[0] == 0:
            cache_log("nasa_iotd: preparing cache...")
            cursor.execute(
                """CREATE TABLE nasa_iotd
                           (id text primary key, title text, published timestamp, author text, description text)"""
            )
            connection.commit()
        cache_log("nasa_iotd: cache ready.")
        connection.close()

    @classmethod
    def save_to_cache(
        cls, url: str, title: str, published: str, author: str, description: str
    ) -> None:
        cls._save_to_cache("nasa_iotd", (url, title, published, author, description))

    @classmethod
    def recover_from_cache(cls, id_: str) -> Optional[Dict[str, str]]:
        return cls._recover_from_cache(id_, "nasa_iotd")


class NasaIOTDParser(Parser):

    name: str = "nasa_iotd"
    cache: Cache = NasaIOTDCache

    @staticmethod
    def get_xml_feed() -> str:
        nasa_feed = feedparser.parse(
            "https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss"
        )

        entries = []

        browser = Browser()

        for entry in nasa_feed["entries"]:
            try:
                entries.append(parse_entry(entry, browser))
            except TimeoutError:
                log.error(f"SKIPPED: {entry['link']} - Timed out when parsing")
            except Exception:
                log.error(f"SKIPPED: {entry['link']} - Unknown error")

        browser.quit()

        feed = Feed(
            title=nasa_feed["feed"]["title"],
            link=nasa_feed["feed"]["link"],
            description=nasa_feed["feed"]["subtitle"],
            language=nasa_feed["feed"]["language"],
            lastBuildDate=datetime.datetime.now(),
            items=entries,
        )

        return feed.rss()

    @staticmethod
    def prune_cache():
        """Keeps in cache only the most recent 70 entries."""
        cache_log("nasa_iotd: pruning...")
        cache_log("nasa_iotd: pruned.")
