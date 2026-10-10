"""Default tracker settings and Selenium driver construction."""

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

DIRECTORY = "reports"
NAME = "PS4"
CURRENCY = "€"
MIN_PRICE = "200"
MAX_PRICE = "700"
FILTERS = {"min": MIN_PRICE, "max": MAX_PRICE}
BASE_URL = "https://www.amazon.de/"


def get_chrome_web_driver(options):
    driver_path = os.environ.get("CHROMEDRIVER")
    service = Service(executable_path=driver_path) if driver_path else Service()
    return webdriver.Chrome(service=service, options=options)


def get_web_driver_options():
    return webdriver.ChromeOptions()


def set_browser_as_incognito(options):
    options.add_argument("--incognito")


def set_automation_as_head_less(options):
    options.add_argument("--headless=new")
