from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
from datetime import datetime
import gspread
import json
import os

# Google Sheets 認証
credentials = json.loads(os.environ["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(credentials)

# スプレッドシート設定
KEYWORDS_SPREADSHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"
OUTPUT_SPREADSHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"
INPUT_SHEET_NAME = "keywords"
TODAY_SHEET_NAME = datetime.now().strftime("%y%m%d")

# キーワード取得
keyword_ws = gc.open_by_key(KEYWORDS_SPREADSHEET_ID).worksheet(INPUT_SHEET_NAME)
keywords = keyword_ws.col_values(1)[1:]  # A2以降
print(f"📌 実行開始")
print(f"✅ キーワード一覧: {keywords}")

# 出力先シート
sh = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
try:
    output_ws = sh.worksheet(TODAY_SHEET_NAME)
    print(f"📄 既存シート {TODAY_SHEET_NAME} を使用")
except:
    output_ws = sh.add_worksheet(title=TODAY_SHEET_NAME, rows="1000", cols="10")
    output_ws.append_row(["キーワード", "記事タイトル", "記事URL", "本文冒頭", "記事日付", "取得日時"])
    print(f"🆕 新規シート {TODAY_SHEET_NAME} を作成")

# Chromeドライバ設定
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--window-size=1280x800')
driver = webdriver.Chrome(options=options)

for keyword in keywords:
    print(f"🔍 検索開始: {keyword}")
    query_url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"
    driver.get(query_url)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    print("🌐 ページソース冒頭（1000文字）:")
    print(driver.page_source[:1000])

    articles = soup.select("a[href^='https://news.yahoo.co.jp/articles/']")
    print(f"　→ 記事数: {len(articles)}")

    for article in articles[:5]:
        try:
            title = article.text.strip()
            link = article["href"]
            date = ""  # 詳細ページから取得しない限り空

            # 本文取得
            driver.get(link)
            time.sleep(2)
            detail_soup = BeautifulSoup(driver.page_source, "html.parser")
            tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body") or detail_soup.select_one("div.article_body")
            body = tag.text.strip() if tag else ""

            output_ws.append_row([
                keyword,
                title,
                link,
                body[:100],
                date,
                datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            ])
        except Exception as e:
            print(f"⚠️ 記事処理エラー: {e}")

driver.quit()
print("✅ 完了")
