import sqlite3
import datetime
from typing import Optional, Dict

from rfeed import Item, Feed, Guid
import feedparser
from feedparser.util import FeedParserDict
from dateutil import parser, tz
from bs4 import BeautifulSoup
from bs4.element import Tag

from rss_parser.cache import Cache
from rss_parser.logger import cache_log, log
from rss_parser.parser import Parser
from rss_parser.selenium import Browser
from rss_parser.utils import wait_for


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

    @staticmethod
    def prune(max_entries: int = 60) -> None:
        """Keeps in cache only the most recent 60 entries."""
        connection = sqlite3.connect(Cache.DB)
        count = connection.execute("""SELECT count(id) FROM nasa_iotd""").fetchone()[0]
        to_prune = count - max_entries
        if to_prune > 0:
            connection.execute(
                """
            DELETE FROM nasa_iotd WHERE nasa_iotd.id in
            (SELECT id FROM nasa_iotd ORDER BY published ASC limit '%s')
            """
                % to_prune
            )
            connection.commit()
            cache_log(f"nasa_iotd: pruned {to_prune} old entries.")

    @classmethod
    def flush_cache(cls):
        cls._truncate_table("nasa_iotd")


class NasaIOTDParser(Parser):

    name: str = "nasa_iotd"
    url: str = "https://www.nasa.gov/rss/dyn/lg_image_of_the_day.rss"
    default_limit: int = 60
    cache: Cache = NasaIOTDCache

    @classmethod
    def parse_source(cls, url: str, browser: Browser) -> str:
        article = cls._get_article_node(url, browser)
        return cls._create_description(article)

    @classmethod
    def parse_entry(cls, entry: FeedParserDict, browser: Browser) -> Item:
        link = entry["link"]
        title = entry["title"]

        item = cls.cache.recover_from_cache(link)

        if not item:
            #
            # No cached entry, we need to parse it
            #
            article = cls._get_article_node(link, browser)

            description = cls._create_description(article)
            author_node = article.find("div", class_="editor")
            author = str(author_node.text).replace("Editor: ", "")

            tz_dict = {
                "EST": tz.gettz("America/New_York"),
                "EDT": tz.gettz("America/New_York"),
            }
            published = parser.parse(entry["published"], tzinfos=tz_dict)

            # Save the parsed data to the cache
            cls.cache.save_to_cache(link, title, published, author, description)
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

    @classmethod
    def _get_article_node(cls, url: str, browser: Browser) -> Tag:
        browser.open(url)
        return wait_for(
            lambda: BeautifulSoup(browser.get_page_source(), "html.parser").find(
                "div", class_="article-body"
            )
        )

    @staticmethod
    def _create_description(article: Tag) -> str:
        image_node = article.find("div", class_="feature-image-container")
        text_node = article.find("div", class_="text")
        image = (
            str(image_node)
            .replace('href="/sites', 'href="https://www.nasa.gov/sites')
            .replace('src="/sites', 'src="https://www.nasa.gov/sites')
        )
        text = str(text_node)
        return image + "<br>" + text
