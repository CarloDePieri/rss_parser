from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Response, HTTPException
from fastapi.responses import HTMLResponse

from rss_parser.logger import cache_log, parser_log
from rss_parser.parser.ilpost import IlPostParser
from rss_parser.parser.nasa_iotd import NasaIOTDParser
from rss_parser.selenium import setup_selenium, Browser

app = FastAPI()

# Prepare selenium
setup_selenium()

# Register parsers
active_parsers = [NasaIOTDParser, IlPostParser]
parser_log(f"activated: {', '.join(map(lambda x: x.name, active_parsers))}")

# Init the cache
cache_log("Init...")
for parser in active_parsers:
    parser.cache.init()
cache_log("Ready")


@app.get("/parse/{feed_id}.rss")
def parse(
    feed_id: str, background_tasks: BackgroundTasks, limit: Optional[int] = None
) -> Response:
    """TODO"""

    for active_parser in active_parsers:
        if feed_id == active_parser.name:
            # background tasks will be executed after returning the response
            background_tasks.add_task(active_parser.cache.prune)
            # use the default limit if it was not specified or if it was invalid
            if not limit or limit > active_parser.default_limit or limit < 1:
                limit = active_parser.default_limit
            # return the parsed feed
            return Response(
                content=active_parser.get_xml_feed(limit), media_type="application/xml"
            )

    # If we got here we there were no match with the activated parsed
    raise HTTPException(status_code=404, detail="Feed not found")


@app.get("/cached/{feed_id}/", response_class=HTMLResponse)
def cached(feed_id: str, id_: str):
    """Used to quickly preview an already cached item."""
    for active_parser in active_parsers:
        if feed_id == active_parser.name:
            cached_item = active_parser.cache.recover_from_cache(id_=id_)
            if cached_item:
                return f"""
                <html><head></head><body>{ cached_item["description"] }</body></html>
                """
            # If we got here the requested id was not cached
            raise HTTPException(
                status_code=404, detail=f"Element not found in table {feed_id}"
            )

    # If we got here we there were no match with the activated parsed
    raise HTTPException(status_code=404, detail="Feed not found")


@app.get("/preview/{feed_id}/", response_class=HTMLResponse)
def preview(feed_id: str, id_: str):
    """Used to quickly preview an item, it will not hit nor update the cache. Useful when debugging a parser."""
    for active_parser in active_parsers:
        if feed_id == active_parser.name:
            browser = Browser()
            try:
                parsed_source = active_parser.parse_source(url=id_, browser=browser)
                return f"""
                <html><head></head><body>{ parsed_source }</body></html>
                """
            finally:
                browser.quit()

    # If we got here we there were no match with the activated parsed
    raise HTTPException(status_code=404, detail="Feed not found")


@app.get("/flush/{feed_id}/")
def flush_cache(feed_id: str):
    for active_parser in active_parsers:
        if feed_id == active_parser.name:
            active_parser.cache.flush_cache()
            return {f"{feed_id}": "cache flushed"}
    raise HTTPException(status_code=404, detail="Feed not found")
