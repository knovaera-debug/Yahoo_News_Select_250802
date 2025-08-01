import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# 📌 Google Sheets 設定
KEYWORDS_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
INPUT_SHEET_NAME = 'keywords'
BASE_SHEET_NAME = 'Base'

# 📌 認証
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
credentials = Credentials.from_service_account_info(eval(GOOGLE_CREDENTIALS), scopes=[
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
])
gc = gspread.authorize(credentials)

# 📌 キーワード取得
keyword_ws = gc.open_by_key(KEYWORDS_SPREADSHEET_ID).worksheet(INPUT_SHEET_NAME)
keywords = keyword_ws.col_values(1)[1:]
print("📌 実行開始")
print(f"✅ キーワード一覧: {keywords}")

# 📌 日付設定
now = datetime.now()
target_date = now.strftime('%y%m%d')
print(f"📄 既存シート {target_date} を使用")

# 📌 出力先準備
sh = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
try:
    ws = sh.worksheet(target_date)
except gspread.exceptions.WorksheetNotFound:
    base = sh.worksheet(BASE_SHEET_NAME)
    ws = sh.duplicate_sheet(base.id, new_sheet_name=target_date)

# 📌 Chrome セットアップ（ヘッドレス）
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

# 📌 検索処理
row = 2
for kw in keywords:
    print(f"🔍 検索開始: {kw}")
    url = f"https://news.yahoo.co.jp/search?p={kw}&ei=utf-8"
    driver.get(url)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    print(f"🌐 ページソース冒頭（1000文字）:\n{soup.prettify()[:1000]}")

    articles = soup.select("a[href^='https://news.yahoo.co.jp/articles/']")
    seen_urls = set()
    count = 0

    for article in articles:
        link = article.get("href")
        if link in seen_urls:
            continue
        seen_urls.add(link)
        title = article.get_text().strip()

        ws.update_cell(row, 1, row - 1)             # No.
        ws.update_cell(row, 2, title)               # タイトル
        ws.update_cell(row, 3, link)                # URL
        ws.update_cell(row, 4, kw)                  # キーワード
        ws.update_cell(row, 5, datetime.now().strftime('%Y/%m/%d %H:%M:%S'))  # 取得日時

        row += 1
        count += 1

    print(f"　→ 記事数: {count}")

driver.quit()
