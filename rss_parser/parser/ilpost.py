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
from rss_parser.helpers import parse_telegram_iframe
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
    def flush_cache(cls):
        cls._truncate_table("ilpost")


class IlPostParser(Parser):

    name: str = "ilpost"
    url: str = "https://www.ilpost.it/feed/"
    default_limit: int = 10
    cache: Cache = IlPostCache

    @classmethod
    def parse_source(cls, url: str, browser: Browser) -> str:
        article = cls._get_article_node(url, browser)
        return cls._create_description(article, browser)

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

            description = cls._create_description(article, browser)

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
    def _create_description(cls, article: Tag, browser: Browser) -> str:
        description = ""

        # Find out if a subtitle is present
        subtitle = article.find("div", class_="sottit")
        if subtitle:
            description += str(subtitle)

        # initial figure
        header = article.find("div", class_="entry-container")
        if header:
            for child in header.children:
                if (
                    child.name == "div"
                    and "figure-container" in child.attrs["class"]
                    and "cf" in child.attrs["class"]
                ):
                    first_img = child.find("img")
                    if first_img:
                        caption = child.find("span", class_="caption")
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
                    # look for a telegram iframe
                    iframe = child.find("iframe")
                    if iframe:
                        if "telegram-post" in iframe.attrs.get("id", ""):
                            description += parse_telegram_iframe(iframe, browser)
                        else:
                            description += cls._new_generic_iframe(iframe)
                    else:
                        # normale text paragraph
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
                        description += f"<figure><figcaption><a href='{url}' target='_blank'>[GALLERY]</a></figcaption></figure>"
                # live feed
                if child.name == "div" and "live-center-embed" in child.attrs.get(
                    "class", []
                ):
                    description += f"<p><a href='{child.attrs['data-src']}'>[[ LIVE BLOG - Click to open a tidy version ]]</a></p>"
                # data (maps)
                if child.name == "div" and "ilpost_datawrapper" in child.attrs.get(
                    "class", []
                ):
                    description += cls._new_data_wrapper(child)
                # data (graphs)
                if child.name == "div" and "flourish-embed" in child.attrs.get(
                    "class", []
                ):
                    description += "<p><figure><figcaption>[[ DATA GRAPH - Open the webpage to see it ]]</figcaption></figure></p>"

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
            f'<img src="https://i.ytimg.com/vi/{id_}/hqdefault.jpg"></a></picture>'
            f"<figcaption>(YouTube video - Click the placeholder to open it)</figcaption></figure>"
        )

    @staticmethod
    def _new_gallery_image(url: str, src: str) -> str:
        # fix all webp images
        url = url.replace("jpeg.webp", "jpeg").replace("jpg.webp", "jpg")
        return (
            f'<figure><picture><a href="{url}" target="_blank">'
            f'<img src="{src}"></a></picture>'
            f"</figure>"
        )

    @staticmethod
    def _new_generic_iframe(wrapper: Tag) -> str:
        try:
            url = wrapper.attrs.get("src")
            if not url or url[0:4] != "http":
                url = wrapper.attrs.get("data-url")
            if not url or url[0:4] != "http":
                url = wrapper.attrs.get("data-lazy-src")
            start_link = ""
            end_link = ""
            if url and url[0:4] == "http":
                start_link = f"<a href='{url}'>"
                end_link = "</a>"
            return (
                f"<figure><picture><iframe src='{url}'></iframe></picture>"
                f"<figcaption>{start_link}[[ IFRAME - Click here to see it ]]{end_link}</figcaption></figure>"
            )
        except Exception as e:
            return "<p><figure><figcaption>[[ BROKEN IFRAME - Open the webpage to see it ]]</figcaption></figure>"

    @staticmethod
    def _new_data_wrapper(wrapper: Tag) -> str:
        try:
            url = wrapper.attrs["data-url"]
            return (
                f"<figure><picture><iframe src='{url}'></iframe></picture>"
                f"<figcaption><a href='{url}'>[[ DATA VISUALIZATION - Open the full page if you can't see it ]]</a></figcaption></figure>"
            )
        except Exception as e:
            return "<p><figure><figcaption>[[ BROKEN DATA VISUALIZATION - Open the full page to see it ]]</figcaption></figure>"
