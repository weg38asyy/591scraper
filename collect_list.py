import os
import time
import random
from typing import List
from urllib.parse import urlparse, parse_qs

import typer
import joblib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup

# 方案一
URLS = ['https://rent.591.com.tw/?showMore=1&option=broadband,cold,washer&multiNotice=boy,all_sex,not_cover&region=3&order=posttime&orderType=desc&other=near_subway&section=34,27&searchtype=1&rentprice=6000,10000',
        'https://rent.591.com.tw/?showMore=1&multiNotice=not_cover,boy,all_sex&option=cold,broadband&other=newPost&region=1&section=4,12&searchtype=1&rentprice=6000,12000',
        'https://rent.591.com.tw/?showMore=1&multiNotice=not_cover,boy,all_sex&option=cold,broadband&region=1&section=11,10,7&searchtype=1&other=near_subway,newPost&rentprice=6000,10000']
# 方案二
URLS2 = ['https://rent.591.com.tw/?showMore=1&option=broadband,cold,washer&multiNotice=boy,all_sex,not_cover&region=3&order=posttime&orderType=desc&rentprice=6000,10000&multiFloor=6_12,2_6&other=near_subway,newPost&kind=2',
         'https://rent.591.com.tw/?showMore=1&option=broadband,cold,washer&multiNotice=boy,all_sex,not_cover&region=3&order=posttime&orderType=desc&rentprice=6000,10000&multiFloor=6_12,2_6&other=near_subway,newPost&kind=3',
         'https://rent.591.com.tw/?showMore=1&multiNotice=not_cover,boy,all_sex&option=cold,broadband,washer&region=1&section=11,4,12,10,7&searchtype=1&rentprice=6000,12000&kind=2&other=near_subway,newPost',
         'https://rent.591.com.tw/?showMore=1&multiNotice=not_cover,boy,all_sex&option=cold,broadband,washer&region=1&section=11,4,12,10,7&searchtype=1&rentprice=6000,12000&kind=3&other=near_subway,newPost']

chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
# ChromeDriver的路徑，預設在當前目錄（預設MAC OS執行檔，若為Win執行檔有.exe）
chromeDriver = './chromedriver'


def urlIterator(URLS: list, output_path: str, max_pages: int, quiet: bool):
    listings: List[str] = []
    for URL in URLS:
        try:
            region = parse_qs(urlparse(URL).query)["region"][0]
        except AttributeError as e:
            print("The URL must hav..e a 'region' query argument!")
            raise e
        except:
            region = None
        options = webdriver.ChromeOptions()
        options.binary_location = chromePath
        if quiet:
            options.add_argument("headless")
        browser = webdriver.Chrome(
            service=Service(chromeDriver), options=options)
        browser.get(URL)
        try:
            browser.find_element(By.CSS_SELECTOR,
                                 f'dd[data-id="{region}"]').click()
        except NoSuchElementException:
            pass
        time.sleep(2)
        for i in range(max_pages):
            print(f"Page {i+1}")
            soup = BeautifulSoup(browser.page_source, "lxml")
            for item in soup.find_all("section", attrs={"class": "vue-list-rent-item"}):
                link = item.find("a")
                listings.append(link.attrs["href"].split(
                    "-")[-1].split(".")[0])
            browser.find_element(By.CLASS_NAME, "pageNext").click()
            time.sleep(random.random() * 5)
            try:
                browser.find_element(By.CSS_SELECTOR, "a.last")
                break
            except NoSuchElementException:
                pass

    print(len(set(listings)))
    joblib.dump(listings, output_path)
    print(f"Done! Collected {len(listings)} entries.")


def main(max_pages: int = 2, quiet: bool = False):
    urlIterator(URLS, "cache/listings1.jbl", max_pages, quiet)
    urlIterator(URLS2, "cache/listings2.jbl", max_pages, quiet)


if __name__ == "__main__":
    typer.run(main)
