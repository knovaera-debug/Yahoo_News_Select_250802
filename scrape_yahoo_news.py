import os
import time
from datetime import datetime, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# === Google認証設定 ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = "service_account.json"
credentials = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
gc = gspread.authorize(credentials)

# === スプレッドシート設定 ===
KEYWORDS_SPREADSHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"  # キーワード用
OUTPUT_SPREADSHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"  # 出力先

INPUT_SHEET_NAME = "keywords"
JST = pytz.timezone('Asia/Tokyo')
today_jst = datetime.now(JST).strftime("%y%m%d")

print("📌 実行開始")

# === キーワード取得 ===
keyword_ws = gc.open_by_key(KEYWORDS_SPREADSHEET_ID).worksheet(INPUT_SHEET_NAME)
keywords = [row[0] for row in keyword_ws.get_all_values()[1:] if row]
print(f"✅ キーワード一覧: {keywords}")

# === 出力シート準備 ===
output_book = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
try:
    output_ws = output_book.worksheet(today_jst)
except gspread.exceptions.WorksheetNotFound:
    try:
        base_ws = output_book.worksheet("Base")
        output_ws = base_ws.duplicate(new_sheet_name=today_jst)
    except gspread.exceptions.WorksheetNotFound:
        output_ws = output_book.add_worksheet(title=today_jst, rows="100", cols="10")
        output_ws.update('A1:F1', [["No", "キーワード", "タイトル", "URL", "日付", "本文"]])

# === Chromeドライバー設定（ヘッドレス） ===
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)

row_idx = 2

# === 各キーワードで検索処理 ===
for kw in keywords:
    print(f"🔍 検索開始: {kw}")
    url = f"https://news.yahoo.co.jp/search?p={kw}"
    driver.get(url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    articles = soup.select('div.sc-7n8lh-2.fvHeUD > div > article > div > div > div > a')

    print(f"　→ 記事数: {len(articles)}")

    for i, a_tag in enumerate(articles):
        try:
            href = a_tag.get("href")
            title = a_tag.get_text(strip=True)
            driver.get(href)
            time.sleep(1.5)
            article_soup = BeautifulSoup(driver.page_source, "html.parser")

            # 日付取得
            date_tag = article_soup.select_one('time')
            date_text = date_tag.get_text(strip=True) if date_tag else ""

            # 本文取得
            body_tag = article_soup.select_one("article")
            if not body_tag:
                body_tag = article_soup.select_one("div[class*='article']")
            body = body_tag.get_text(separator="\n", strip=True) if body_tag else ""

            # スプレッドシートに出力
            output_ws.update(f"A{row_idx}:F{row_idx}", [[i + 1, kw, title, href, date_text, body]])
            row_idx += 1
        except Exception as e:
            print(f"⚠️ 取得失敗: {e}")
            continue

driver.quit()
print("✅ 完了")
