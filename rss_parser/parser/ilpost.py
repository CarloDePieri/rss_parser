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
            for child in body.children:
                # text paragraph
                if child.name == "p":
                    description += str(child)
                # simple image
                if child.name == "img":
                    description += cls._new_image_with_caption(child.attrs["src"])
                # attachments
                if child.name == "div" and "attachment" in child.attrs.get("id", ""):
                    # images
                    img = child.find("img")
                    if img:
                        description += cls._new_image_with_caption(
                            img.attrs["data-src"], child.text
                        )
                # blockquote
                if child.name == "blockquote":
                    description += str(child)
                # video player
                if child.name == "div" and "video-container" in child.attrs.get(
                    "class", []
                ):
                    yt = child.find("div", class_="rll-youtube-player")
                    if yt:
                        src = yt.attrs["data-src"]
                        description += cls._new_video_placeholder(src)
                # image gallery
                if child.name == "div" and "gallery" in child.attrs.get("class", []):
                    for inner_child in child.children:
                        url = inner_child.find("a").attrs["href"]
                        src = inner_child.find("img").attrs["data-src"]
                        description += cls._new_gallery_image(url, src)
                # live feed
                if child.name == "div" and "live-center-embed" in child.attrs.get(
                    "class", []
                ):
                    description += str(child)

        # DEBUG - APPEND THE WHOLE UNPROCESSED ARTICLE
        # description += f"<hr>{str(article)}"

        return description

    @staticmethod
    def _new_image_with_caption(url: str, caption: str = None) -> str:
        # fix all webp images
        url = url.replace("jpeg.webp", "jpeg").replace("jpg.webp", "jpg")
        caption_code = ""
        if caption:
            caption_code = f"<figcaption>{caption}</figcaption>"
        return f"<figure><picture><img src='{url}'/></picture>{caption_code}</figure>"

    @staticmethod
    def _new_video_placeholder(url: str) -> str:
        id_ = url.split("/")[-1]
        url = f"https://www.youtube.com/watch?v={id_}"
        return (
            f'<figure><picture><a href="{url}" target="_blank">'
            f'<img src="https://i.ytimg.com/vi/{id_}/hqdefault.jpg" alt="youtube"></a></picture>'
            f"<figcaption>(YouTube video - Click the placeholder to open it)</figcaption></figure>"
        )

    @staticmethod
    def _new_gallery_image(url: str, src: str) -> str:
        # fix all webp images
        url = url.replace("jpeg.webp", "jpeg").replace("jpg.webp", "jpg")
        return (
            f'<figure><picture><a href="{url}" target="_blank">'
            f'<img src="{src}" alt="youtube"></a></picture>'
            f"</figure>"
        )
