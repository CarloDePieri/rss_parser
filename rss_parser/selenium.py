import os
import re
import requests
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

    if os.geteuid() == 0:
        msg = f"FATAL ERROR: CHROME CAN'T BE LAUNCHED SAFELY BY ROOT. LAUNCH THE PROGRAM AS A NORMAL USER!"
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
        if _get_latest_chromedriver_version(chrome_version) != chromedriver_version:
            selenium_log(f"Wrong Chromedriver version.")
            _download_chromedriver(chrome_version)
    else:
        selenium_log(f"Chromedriver not found.")
        _download_chromedriver(chrome_version)

    selenium_log("Chromedriver is up-to-date.")


def _download_chromedriver(version: str) -> None:
    chromedriver_dir = Path(CHROMEDRIVER_PATH).parent.absolute()
    chromedriver_archive = f"{CHROMEDRIVER_PATH}_linux64.zip"
    latest_chromedriver_version = _get_latest_chromedriver_version(version)

    selenium_log(f"Chrome version: {version}")
    selenium_log(f"Latest Chromedriver version: {latest_chromedriver_version}")
    selenium_log(f"Downloading...")

    # Delete old chromedriver
    if os.path.exists(CHROMEDRIVER_PATH):
        os.remove(CHROMEDRIVER_PATH)

    # Delete old chromedriver archive
    if os.path.exists(chromedriver_archive):
        os.remove(chromedriver_archive)

    # Download a new chromedriver archive
    chromedriver_url = f"https://chromedriver.storage.googleapis.com/{latest_chromedriver_version}/chromedriver_linux64.zip"
    subprocess.run(
        ["wget", chromedriver_url, "--directory-prefix", chromedriver_dir],
        capture_output=True,
    )
    # unzip it
    subprocess.run(["unzip", chromedriver_archive], capture_output=True)


def _get_latest_chromedriver_version(version: str) -> str:
    version_family = ".".join(version.split(".")[:-1])
    latest_release_url = (
        f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{version_family}"
    )
    response = requests.get(latest_release_url)
    return response.text
