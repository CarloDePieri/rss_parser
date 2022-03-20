import re

from rss_parser.selenium import Browser
from rss_parser.utils import wait_for

from bs4 import BeautifulSoup
from bs4.element import Tag


def parse_telegram_iframe(iframe: Tag, browser: Browser) -> str:
    """Return a tidy view of a telegram iframe."""

    url = iframe.attrs["src"]

    # DEBUG
    # url = "https://t.me/V_Zelenskiy_official/890?embed=1&tme_mode=1"  # video
    # url = "https://t.me/V_Zelenskiy_official/891?embed=1&tme_mode=1"  # gallery
    # url = "https://t.me/bestwallpapes/594?embed=1&tme_mode=1"  # image

    try:
        browser.open(url)
        page_src = wait_for(
            lambda: BeautifulSoup(browser.get_page_source(), "html.parser").find(
                "div", class_="tgme_widget_message"
            )
        )
        text = page_src.find("div", class_="tgme_widget_message_text")
        link = page_src.find("div", class_="tgme_widget_message_link")
        link_url = link.find("a").attrs["href"]
        author = page_src.find("a", class_="tgme_widget_message_owner_name").text
        video = page_src.find("a", class_="tgme_widget_message_video_player")

        media_warning = ""
        video_str = ""
        if video:
            video_thumb_url = (
                page_src.find("i", class_="tgme_widget_message_video_thumb")
                .attrs["style"]
                .split("'")[1]
            )
            video_str = f"<p><a href='{link_url}' target='_blank'><img src='{video_thumb_url}'/></a>"
            media_warning = f"<a href='{link_url}' target='_blank'>[VIDEO]</a> "

        # images
        image = page_src.find("a", class_="tgme_widget_message_photo_wrap")
        image_str = ""
        if image:
            # check if it's a gallery
            group = page_src.find("div", class_="tgme_widget_message_grouped")
            if group:
                # media gallery
                photo = group.find("a", class_="tgme_widget_message_photo_wrap")
                image_str = f"<p><a href='{link_url}' target='_blank'>{_image_from_style_background_url(photo.attrs['style'])}</a></p>"
                media_warning = f"<a href='{link_url}' target='_blank'>[GALLERY]</a> "
            else:
                image_str += _image_from_style_background_url(image.attrs["style"])

        return f"<blockquote>{image_str}{video_str}<p>{media_warning}{str(text)}</p><p>{author} - {link.find('a')}</p></blockquote>"

    except Exception as e:
        # Fallback
        return f"<blockquote><p>FAILED PARSING TELEGRAM MESSAGE</p><p>{url}</p></blockquote>"


def _image_from_style_background_url(style: str) -> str:
    regex = r"background-image:.*url\(('|\")(.*)('|\")\)"
    url = re.findall(regex, style)[0][1]
    return f"<img src='{url}'/><br>"
