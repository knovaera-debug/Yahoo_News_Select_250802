import os
import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 設定 ---
KEYWORDS_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
INPUT_SHEET_NAME = 'keywords'
HEADLESS = True

# --- Google認証 ---
google_creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
gc = gspread.authorize(credentials)

# --- キーワード読み込み ---
keyword_ws = gc.open_by_key(KEYWORDS_SPREADSHEET_ID).worksheet(INPUT_SHEET_NAME)
keywords = keyword_ws.col_values(1)[1:]  # A2以降

# --- 日付と出力シート名 ---
now = datetime.now()
JST = timedelta(hours=9)
today_jst = (now + JST).strftime("%y%m%d")
print("📌 実行開始")
print("✅ キーワード一覧:", keywords)

# --- 出力用シート準備 ---
output_book = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
try:
    output_ws = output_book.worksheet(today_jst)
except gspread.exceptions.WorksheetNotFound:
    base_ws = output_book.worksheet("Base")
    output_ws = base_ws.duplicate(new_sheet_name=today_jst)
print(f"📄 既存シート {today_jst} を使用")

# --- Chromeドライバ設定（GitHub Actions対応） ---
options = Options()
if HEADLESS:
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)

# --- 検索処理 ---
all_data = []
row_num = 2
for kw in keywords:
    print(f"🔍 検索開始: {kw}")
    url = f"https://news.yahoo.co.jp/search?p={kw}&ei=utf-8"
    driver.get(url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    articles = soup.select("li.sc-8tlg6o-0")  # Yahoo!記事ブロックセレクタ
    print(f"　→ 記事数: {len(articles)}")

    for article in articles:
        try:
            title = article.select_one('a').text.strip()
            link = article.select_one('a')['href']
            date_elem = article.select_one("time")
            date_text = date_elem.text.strip() if date_elem else "不明"
            all_data.append([row_num - 1, kw, title, link, date_text])
            row_num += 1
        except Exception as e:
            print(f"⚠️ パースエラー: {e}")
            continue

# --- データ書き込み（バルク）---
if all_data:
    print(f"📝 出力行数: {len(all_data)}")
    output_ws.update(f"A2:E{len(all_data)+1}", all_data)
else:
    print("📭 書き込むデータがありません。")

driver.quit()
print("✅ 処理完了")
