from fastapi import FastAPI, Response, HTTPException

from rss_parser.logger import cache_log
from rss_parser.parser.nasa_iotd import nasa_iotd_get_feed, NasaIOTDCache
from rss_parser.selenium import setup_selenium

app = FastAPI()

# Prepare selenium
setup_selenium()

# Init the cache
cache_log("Init...")
NasaIOTDCache.init()
cache_log("Ready")


@app.get("/parse/{feed_id}.rss")
def parse(feed_id: str) -> Response:
    if feed_id == "nasa_iotd":
        return Response(content=nasa_iotd_get_feed(), media_type="application/xml")
    else:
        raise HTTPException(status_code=404, detail="Feed not found")
