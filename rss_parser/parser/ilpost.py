import sqlite3
from typing import Optional, Dict

from rfeed import Item, Guid
from feedparser.util import FeedParserDict
from dateutil import parser, tz
from bs4 import BeautifulSoup
from bs4.element import Tag

from rss_parser.cache import Cache
from rss_parser.logger import cache_log
from rss_parser.parser import Parser
from rss_parser.selenium import Browser
from rss_parser.utils import wait_for


class IlPostCache(Cache):
    @staticmethod
    def init() -> None:
        connection = sqlite3.connect(Cache.DB)
        cursor = connection.cursor()
        cursor.execute(
            """ SELECT count(name) FROM sqlite_master WHERE type='table' AND name='ilpost' """
        )
        if cursor.fetchone()[0] == 0:
            cache_log("ilpost: preparing cache...")
            cursor.execute(
                """CREATE TABLE ilpost
                           (id text primary key, title text, published timestamp, description text)"""
            )
            connection.commit()
        cache_log("ilpost: cache ready.")
        connection.close()

    @classmethod
    def save_to_cache(
        cls, url: str, title: str, published: str, description: str
    ) -> None:
        cls._save_to_cache("ilpost", (url, title, published, description))

    @classmethod
    def recover_from_cache(cls, id_: str) -> Optional[Dict[str, str]]:
        return cls._recover_from_cache(id_, "ilpost")

    @staticmethod
    def prune(max_entries: int = 100) -> None:
        """Keeps in cache only the most recent 60 entries."""
        connection = sqlite3.connect(Cache.DB)
        count = connection.execute("""SELECT count(id) FROM ilpost""").fetchone()[0]
        to_prune = count - max_entries
        if to_prune > 0:
            connection.execute(
                """
            DELETE FROM ilpost WHERE ilpost.id in
            (SELECT id FROM ilpost ORDER BY published ASC limit '%s')
            """
                % to_prune
            )
            connection.commit()
            cache_log(f"ilpost: pruned {to_prune} old entries.")

    @classmethod
    def drop(cls):
        cls._drop_table("ilpost")


class IlPostParser(Parser):

    name: str = "ilpost"
    url: str = "https://www.ilpost.it/feed/"
    default_limit: int = 10
    cache: Cache = IlPostCache

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

            tz_dict = {
                "EST": tz.gettz("America/New_York"),
                "EDT": tz.gettz("America/New_York"),
            }
            published = parser.parse(entry["published"], tzinfos=tz_dict)

            # Save the parsed data to the cache
            cls.cache.save_to_cache(link, title, published, description)
        else:
            published = parser.parse(item["published"])
            description = item["description"]

        return Item(
            title=title,
            link=link,
            description=description,
            guid=Guid(link),
            pubDate=published,
        )

    @classmethod
    def _get_article_node(cls, url: str, browser: Browser) -> Tag:
        browser.open(url)
        return wait_for(
            lambda: BeautifulSoup(browser.get_page_source(), "html.parser").find(
                "article"
            )
        )

    @classmethod
    def _create_description(cls, article: Tag) -> str:
        description = ""

        # Find out if a subtitle is present
        subtitle = article.find("div", class_="sottit")
        if subtitle:
            description += str(subtitle)

        # initial figure
        figure = article.find("div", class_="figure-container cf")
        if figure:
            first_img = figure.find("img")
            caption = figure.find("span", class_="caption")
            description += cls._new_image_with_caption(
                first_img.attrs["data-src"], caption.text
            )

        # article body
        body = article.find("div", id="singleBody")
        if not body:
            body = article.find("span", id="singleBody")

        if body:
            for children in body.children:
                # text paragraph
                if children.name == "p":
                    description += str(children)
                # simple image
                if children.name == "img":
                    description += cls._new_image_with_caption(
                        children.attrs["src"], ""
                    )
                # attachments
                if children.name == "div" and "attachment" in children.attrs.get(
                    "id", ""
                ):
                    # images
                    img = children.find("img")
                    if img:
                        description += cls._new_image_with_caption(
                            img.attrs["data-src"], children.text
                        )
                # blockquote
                if children.name == "blockquote":
                    description += str(children)
                # video player
                if children.name == "div" and "video-container" in children.attrs.get(
                    "class", []
                ):
                    description += str(children.find("noscript").contents[0])
                # live feed
                if (
                    children.name == "div"
                    and "live-center-embed" in children.attrs.get("class", [])
                ):
                    description += str(children)

        # DEBUG - APPEND THE WHOLE UNPROCESSED ARTICLE
        # description += f"<hr>{str(article)}"

        return description

    @staticmethod
    def _new_image_with_caption(url: str, caption: str) -> str:
        # fix all webp images
        url = url.replace("jpeg.webp", "jpeg").replace("jpg.webp", "jpg")
        return (
            f"<div style='margin:8pt'><img src='{url}' />"
            f"<div style='margin-top: 5pt'><small><i>{caption}</i></small></div></div>"
        )
