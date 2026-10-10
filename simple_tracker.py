"""Search Amazon and write a JSON price report. No browser is started on import."""

import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from amazon_config import (
    BASE_URL,
    CURRENCY,
    DIRECTORY,
    FILTERS,
    NAME,
    get_chrome_web_driver,
    get_web_driver_options,
    set_browser_as_incognito,
)


def parse_price(text, currency="€"):
    """Parse comma/dot decimal separators and grouped European/English prices."""
    value = text.replace(currency, "").replace("\xa0", "").strip()
    value = re.sub(r"(\d)\s*\n\s*(\d{2})$", r"\1.\2", value)
    value = re.sub(r"\s+", "", value)
    if not re.fullmatch(r"\d[\d.,]*", value):
        raise ValueError("Unrecognized price format")
    if "," in value and "." in value:
        decimal = "," if value.rfind(",") > value.rfind(".") else "."
        value = value.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    elif "," in value or "." in value:
        separator = "," if "," in value else "."
        parts = value.split(separator)
        if len(parts) == 2 and len(parts[-1]) in (1, 2):
            value = ".".join(parts)
        elif all(len(part) == 3 for part in parts[1:]):
            value = "".join(parts)
        else:
            raise ValueError("Ambiguous price format")
    try:
        return float(Decimal(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid price") from exc


class GenerateReport:
    def __init__(self, file_name, filters, base_link, currency, data, directory=DIRECTORY):
        self.data = data or []
        self.file_name = file_name
        report = {
            "title": file_name,
            "date": self.get_now(),
            "best_item": self.get_best_item(),
            "currency": currency,
            "filters": filters,
            "base_link": base_link,
            "products": self.data,
        }
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_name).strip("._") or "report"
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{safe_name}.json"
        self.path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def get_now():
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def get_best_item(self):
        return min(self.data, key=lambda item: item["price"], default=None)


class AmazonAPI:
    def __init__(self, search_term, filters, base_url, currency, driver=None):
        url = urlsplit(base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("The base URL must be HTTPS without embedded credentials")
        low, high = Decimal(str(filters["min"])), Decimal(str(filters["max"]))
        if not low.is_finite() or not high.is_finite() or not 0 <= low <= high:
            raise ValueError("Expected 0 <= minimum price <= maximum price")
        self.base_url = base_url.rstrip("/") + "/"
        self.search_term = search_term
        self.currency = currency
        self.price_filter = f"p_36:{int(low * 100)}-{int(high * 100)}"
        if driver is None:
            options = get_web_driver_options()
            set_browser_as_incognito(options)
            driver = get_chrome_web_driver(options)
        self.driver = driver
        self.driver.set_page_load_timeout(30)

    def run(self):
        try:
            return self.get_products_info(self.get_products_links())
        finally:
            self.driver.quit()

    def get_products_links(self):
        query = urlencode({"k": self.search_term, "rh": self.price_filter})
        self.driver.get(f"{self.base_url}s?{query}")
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot"))
            )
        except TimeoutException:
            return []
        links = self.driver.find_elements(By.CSS_SELECTOR, 'div.s-main-slot a[href*="/dp/"]')
        return list(
            dict.fromkeys(
                link.get_attribute("href") for link in links if link.get_attribute("href")
            )
        )

    @staticmethod
    def get_asin(product_link):
        match = re.search(
            r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)",
            urlsplit(product_link).path + "/",
        )
        return match.group(1) if match else None

    def get_asins(self, links):
        return list(dict.fromkeys(asin for link in links if (asin := self.get_asin(link))))

    def shorten_url(self, asin):
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            raise ValueError("Invalid ASIN")
        return f"{self.base_url}dp/{asin}"

    def get_products_info(self, links):
        return [
            product
            for asin in self.get_asins(links)
            if (product := self.get_single_product_info(asin))
        ]

    def _text(self, selector):
        try:
            return (
                self.driver.find_element(By.CSS_SELECTOR, selector)
                .get_attribute("textContent")
                .strip()
            )
        except NoSuchElementException:
            return None

    def get_title(self):
        return self._text("#productTitle")

    def get_seller(self):
        return self._text("#bylineInfo")

    def convert_price(self, price):
        return parse_price(price, self.currency)

    def get_price(self):
        for selector in (
            "#corePrice_feature_div .a-offscreen",
            "#priceblock_ourprice",
            ".a-price .a-offscreen",
        ):
            value = self._text(selector)
            if value:
                try:
                    return self.convert_price(value)
                except ValueError:
                    continue
        return None

    def get_single_product_info(self, asin):
        url = self.shorten_url(asin)
        self.driver.get(f"{url}?language=en_GB")
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            )
        except TimeoutException:
            return None
        title, seller, price = self.get_title(), self.get_seller(), self.get_price()
        if title and seller and price is not None:
            return {
                "asin": asin,
                "url": url,
                "title": title,
                "seller": seller,
                "price": price,
            }
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", default=NAME)
    parser.add_argument("--output-dir", type=Path, default=Path(DIRECTORY))
    args = parser.parse_args()
    products = AmazonAPI(args.search, FILTERS, BASE_URL, CURRENCY).run()
    report = GenerateReport(args.search, FILTERS, BASE_URL, CURRENCY, products, args.output_dir)
    print(f"Wrote {len(products)} products to {report.path}")


if __name__ == "__main__":
    main()
