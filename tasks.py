from invoke import task
from xvfbwrapper import Xvfb


@task
def run_dev(c):
    c.run("poetry run uvicorn --reload rss_parser.api:app")


@task
def run_dev_xvfb(c):
    display = Xvfb()
    display.start()
    try:
        c.run("poetry run uvicorn --reload rss_parser.api:app")
    finally:
        display.stop()


@task
def run_xvfb(c):
    """Launch this if no real X display is available. Needs xvfb installed."""
    display = Xvfb()
    display.start()
    try:
        c.run("poetry run uvicorn --host 0.0.0.0 rss_parser.api:app")
    finally:
        display.stop()
