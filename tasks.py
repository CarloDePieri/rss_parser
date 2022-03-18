from invoke import task


@task
def run(c):
    c.run("poetry run uvicorn rss_parser.api:app")
