import os
import json
import time
import gspread
import pytz
import chromedriver_autoinstaller
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets認証
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gc = gspread.authorize(credentials)

# シート設定
SPREADSHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"
INPUT_SHEET = "input"

# JST設定
JST = pytz.timezone("Asia/Tokyo")
now = datetime.now(JST)
now_str = now.strftime("%y%m%d")

# Chrome headless設定
chromedriver_autoinstaller.install()
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

def fetch_article_and_comments(url):
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 本文
    article = soup.find("article")
    content_lines = []
    if article:
        for p in article.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                content_lines.append(text)

    # コメント数取得
    comment_count = 0
    try:
        comment_span = soup.find("span", class_="news-comment-count")
        if comment_span:
            comment_count = int(comment_span.text.strip().replace("件", ""))
    except:
        pass

    # コメント本体
    comments = []
    comment_blocks = soup.select(".news-comment-body")
    for block in comment_blocks:
        text = block.get_text(strip=True)
        if text:
            comments.append(text)

    return content_lines, comments, comment_count

def main():
    sh = gc.open_by_key(SPREADSHEET_ID)
    input_ws = sh.worksheet(INPUT_SHEET)
    urls = input_ws.col_values(3)[1:]  # C列（C2〜）

    # 出力シートがなければ作成
    try:
        output_ws = sh.worksheet(now_str)
    except:
        base = sh.worksheet("Base")
        output_ws = sh.duplicate_sheet(source_sheet_id=base.id, new_sheet_name=now_str)
        output_ws = sh.worksheet(now_str)

    for i, url in enumerate(urls):
        if not url.strip():
            continue

        print(f"[{i+1}] {url}")
        content, comments, count = fetch_article_and_comments(url)

        # 本文
        for j, line in enumerate(content):
            output_ws.update_cell(1 + j + 1, 1, line)

        # コメント
        for k, comment in enumerate(comments):
            output_ws.update_cell(20 + k + 1, 1, comment)

        # コメント件数をinputシートF列に
        input_ws.update_cell(i + 2, 6, count)

    driver.quit()

if __name__ == "__main__":
    main()
