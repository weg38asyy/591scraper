import re
import os
import time
import shutil
import random
import logging
from datetime import date
from typing import Optional

import typer
import joblib
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    before_sleep_log,
    RetryError,
    retry_if_exception_type,
)

from utils.post_processing import adjust_price_, auto_marking_, parse_price

LOGGER = logging.getLogger(__name__)


class NotExistException(Exception):
    pass


def get_attributes(soup):
    result = {}
    try:
        result["養寵物"] = (
            "No" if "不可養寵物" in soup.select_one(
                "div.service-rule").text else "Yes"
        )
    except AttributeError:
        result["養寵物"] = None
    contents = soup.select_one("div.main-info-left div.content").children
    for item in contents:
        try:
            name = item.select_one("div div.name").text
            if name in ("租金含", "車位費", "管理費"):
                result[name] = name = item.select_one(
                    "div div.text").text.strip()
        except AttributeError as e:
            print(e)
            continue
    service_list = soup.select_one("div.service-list-box").select(
        "div.service-list-item"
    )
    services = []
    for item in service_list:
        if "del" in item["class"]:
            continue
        services.append(item.text.strip())
    result["提供設備"] = ", ".join(services)
    attributes = soup.select_one("div.house-pattern").find_all("span")
    for i, key in enumerate(("格局", "坪數", "樓層", "型態")):
        result[key] = attributes[i * 2].text.strip()
    return result


@retry(
    reraise=False,
    retry=retry_if_exception_type(TimeoutException),
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    before_sleep=before_sleep_log(LOGGER, logging.INFO),
)
def get_page(browser: webdriver.Chrome, listing_id):
    browser.get(f"https://rent.591.com.tw/home/{listing_id}".strip())
    wait = WebDriverWait(browser, 5)
    try:
        wait.until(
            ec.visibility_of_element_located(
                (By.CSS_SELECTOR, "div.main-info-left"))
        )
    except TimeoutException as e:
        soup = BeautifulSoup(browser.page_source, "lxml")
        tmp = soup.select_one("div.title")
        # print(tmp)
        if tmp and "不存在" in tmp.text:
            raise NotExistException()
        else:
            raise e
    return True


def get_listing_info(browser: webdriver.Chrome, listing_id):
    try:
        get_page(browser, listing_id)
    except RetryError:
        pass
    soup = BeautifulSoup(browser.page_source, "lxml")
    result = {"id": listing_id}
    if soup.select_one(".house-title h1") is None:
        return
    print('123')
    result["title"] = soup.select_one(".house-title h1").text
    result["addr"] = soup.select_one("span.load-map").text.strip()
    complex = soup.select_one("div.address span").text.strip()
    if complex != result["addr"]:
        result["社區"] = complex
    result["price"] = parse_price(soup.select_one("span.price").text)
    result["desc"] = soup.select_one("div.article").text.strip()
    dayBeforeText = soup.select_one("div.release-time").text.strip()
    startIndex = dayBeforeText.find('在') + 1
    endIndex = dayBeforeText.find('前') + 1
    startIndex2 = dayBeforeText.find('(') + 1
    endIndex2 = dayBeforeText.find('內') + 1
    publish = dayBeforeText[startIndex:endIndex]
    result['publish_count'] = 9999
    if publish.find('天') != -1:
        result['publish_count'] = int(re.findall(
            r'-?\d+\.?\d*', publish)[0]) * 24 * 60
    elif publish.find('時') != -1:
        result['publish_count'] = int(
            re.findall(r'-?\d+\.?\d*', publish)[0]) * 60
    elif publish.find('分') != -1:
        result['publish_count'] = int(re.findall(r'-?\d+\.?\d*', publish)[0])

    # print(result['publish_days'])
    # print(result['publish_hours'])

    # print(result['publish_mins'])
    result['publish'] = dayBeforeText
    # result["updated"] = dayBeforeText[startIndex2:endIndex2]
    result["poster"] = re.sub(
        r"\s+", " ", soup.select_one("p.name").text.strip())
    result.update(get_attributes(soup))
    return result

# 尋找關鍵字檔案


def findfile(keyword, root):
    # keyword為關鍵字，root為資料夾路徑
    filelist = []  # 存放每個檔案
    rfilelist = []  # 存放匹配檔案
    for root, dirs, files in os.walk(root):
        for name in files:
            filelist.append(os.path.join(root, name))
       # 遍歷路徑檔案下的所有資料夾，將所有檔案放入filelist
    for i in filelist:
        if os.path.isfile(i):
            if keyword in os.path.basename(os.path.splitext(i)[0]):
                rfilelist.append(i)
            else:
                pass
        else:
            pass
    return rfilelist


def main(
    source_path: str = "cache/",
    data_path: Optional[str] = None,
    output_path: Optional[str] = None,
    limit: int = -1,
    headless: bool = False,
):
    # Get jbl file lists
    listing_paths = findfile('listings', source_path)
    id = 0

    for source_path in listing_paths:
        id += 1
        listing_ids = joblib.load(source_path)
        df_original: Optional[pd.DataFrame] = None

        if data_path:
            if data_path.endswith(".pd"):
                df_original = pd.read_pickle(data_path)
            else:
                df_original = pd.read_csv(data_path)
            listing_ids = list(set(listing_ids) -
                               set(df_original.id.values.astype("str")))
            print(len(listing_ids))

        if limit > 0:
            listing_ids = listing_ids[:limit]

        print(listing_ids)
        print(f"Collecting {len(listing_ids)} entries...")

        chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        # ChromeDriver的路徑，預設在當前目錄（預設MAC OS執行檔，若為Win執行檔有.exe）
        chromeDriver = './chromedriver'

        options = webdriver.ChromeOptions()
        options.binary_location = chromePath
        if headless:
            options.add_argument("headless")
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        browser = webdriver.Chrome(
            service=Service(chromeDriver), options=options)

        data = []
        for id_ in tqdm(listing_ids, ncols=100):
            try:
                data.append(get_listing_info(browser, id_))
            except NotExistException:
                LOGGER.warning(f"Does not exist: {id_}")
                pass
            time.sleep(random.random() * 5)

        df_new = pd.DataFrame(data)
        optional_fields = ("租金含", "車位費", "管理費")
        for field in optional_fields:
            if field not in df_new:
                df_new[field] = None
        df_new = auto_marking_(df_new)
        df_new = adjust_price_(df_new)
        df_new["fetched"] = date.today().isoformat()
        if df_original is not None:
            df_new = pd.concat([df_new, df_original],
                               axis=0).reset_index(drop=True)

        output_path = "cache/df"+str(id)+".csv"

        df_new["link"] = (
            "https://rent.591.com.tw/rent-detail-" +
            df_new["id"].astype("str") + ".html"
        )
        column_ordering = [
            "mark",
            "title",
            "price",
            "price_adjusted",
            "link",
            "addr",
            "publish",
            "publish_count",
            "desc",
            "社區",
            "車位費",
            "管理費",
            "poster",
            "養寵物",
            "提供設備",
            "格局",
            "坪數",
            "樓層",
            "型態",
            "id",
            "fetched",
        ]
        print(df_new.drop("desc", axis=1).sample(min(df_new.shape[0], 10)))
        df_new[column_ordering].to_csv(output_path, index=False)
        print("Finished!")


if __name__ == "__main__":
    typer.run(main)
