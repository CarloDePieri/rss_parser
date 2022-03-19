from fastapi import BackgroundTasks, FastAPI, Response, HTTPException

from rss_parser.logger import cache_log, parser_log
from rss_parser.parser.nasa_iotd import NasaIOTDCache, NasaIOTDParser
from rss_parser.selenium import setup_selenium

app = FastAPI()

# Prepare selenium
setup_selenium()

# Register parsers
active_parsers = [NasaIOTDParser]
parser_log(f"activated: {', '.join(map(lambda x: x.name, active_parsers))}")

# Init the cache
cache_log("Init...")
for parser in active_parsers:
    parser.cache.init()
cache_log("Ready")


@app.get("/parse/{feed_id}.rss")
def parse(feed_id: str, background_tasks: BackgroundTasks) -> Response:
    """TODO"""

    for parser in active_parsers:
        if feed_id == parser.name:
            # background tasks will be executed after returning the response
            background_tasks.add_task(parser.prune_cache)
            # return the parsed feed
            return Response(content=parser.get_xml_feed(), media_type="application/xml")

    # If we got here we there were no match with the activated parsed
    raise HTTPException(status_code=404, detail="Feed not found")
