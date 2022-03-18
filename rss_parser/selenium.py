import os
import re
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver

from rss_parser.logger import selenium_log, selenium_error

CHROMEDRIVER_PATH = os.getcwd() + "/chromedriver"
CHROME_BIN_PATH = "/usr/bin/google-chrome-stable"


class Browser:

    driver: WebDriver

    def __init__(self, headless: bool = True):
        opts = Options()
        if headless:
            opts.add_argument("--headless")
        opts.binary_location = CHROME_BIN_PATH
        chrome_driver = CHROMEDRIVER_PATH
        self.driver = webdriver.Chrome(options=opts, executable_path=chrome_driver)

    def open(self, url: str) -> None:
        self.driver.get(url)

    def get_page_source(self) -> str:
        return self.driver.page_source

    def quit(self) -> None:
        self.driver.quit()


def setup_selenium():
    if not os.path.isfile(CHROME_BIN_PATH):
        msg = f"FATAL ERROR: CHROME WAS NOT FOUND AT {CHROME_BIN_PATH}"
        selenium_error(msg)
        raise Exception(msg)

    chrome_version = (
        subprocess.run([CHROME_BIN_PATH, "--version"], capture_output=True)
        .stdout.decode("utf-8")
        .replace("Google Chrome ", "")
        .replace(" \n", "")
    )

    if os.path.isfile(CHROMEDRIVER_PATH):
        chromedriver_version = (
            subprocess.run([CHROMEDRIVER_PATH, "--version"], capture_output=True)
            .stdout.decode("utf-8")
            .replace("ChromeDriver ", "")
            .replace("\n", "")
        )
        chromedriver_version = re.sub(r" \((.*)\)", "", chromedriver_version)
        if chrome_version != chromedriver_version:
            selenium_log(f"Wrong Chromedriver version.")
            _download_chromedriver(chrome_version)
    else:
        selenium_log(f"Chromedriver not found.")
        _download_chromedriver(chrome_version)

    selenium_log("Chromedriver is up-to-date.")


def _download_chromedriver(version: str) -> None:
    selenium_log(f"Downloading Chromedriver version {version}...")

    chromedriver_dir = Path(CHROMEDRIVER_PATH).parent.absolute()
    chromedriver_archive = f"{CHROMEDRIVER_PATH}_linux64.zip"

    # Delete old chromedriver
    if os.path.exists(CHROMEDRIVER_PATH):
        os.remove(CHROMEDRIVER_PATH)

    # Delete old chromedriver archive
    if os.path.exists(chromedriver_archive):
        os.remove(chromedriver_archive)

    # Download a new chromedriver archive
    chromedriver_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_linux64.zip"
    subprocess.run(
        ["wget", chromedriver_url, "--directory-prefix", chromedriver_dir],
        capture_output=True,
    )
    # unzip it
    subprocess.run(["unzip", chromedriver_archive], capture_output=True)