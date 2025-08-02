import os
import json
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===========================
# Google Sheets 認証
# ===========================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
with open("credentials.json", "r", encoding="utf-8") as f:
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.load(f), scope)
gc = gspread.authorize(credentials)

# ===========================
# Google Sheets 取得
# ===========================
SPREADSHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"
sheet = gc.open_by_key(SPREADSHEET_ID)
input_ws = sheet.worksheet("input")
urls = input_ws.col_values(3)[1:]  # C2以降

# ===========================
# 出力ファイル設定
# ===========================
today_str = datetime.now().strftime("%y%m%d")
try:
    base_ws = sheet.worksheet("Base")
    sheet.duplicate_sheet(base_ws.id, insert_sheet_index=0, new_sheet_name=today_str)
except:
    pass

daily_ws = sheet.worksheet(today_str)

# ===========================
# Selenium設定（ヘッドレス）
# ===========================
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

# ===========================
# 相対時間 -> 絶対時間
# ===========================
def parse_relative_time(text):
    now = datetime.now()
    if "分前" in text:
        return now - timedelta(minutes=int(text.replace("分前", "").strip()))
    elif "時間前" in text:
        return now - timedelta(hours=int(text.replace("時間前", "").strip()))
    elif "日前" in text:
        return now - timedelta(days=int(text.replace("日前", "").strip()))
    return now

# ===========================
# メイン処理
# ===========================
def scrape_article(url):
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 本文
    article_elem = soup.select_one("article")
    paragraphs = [p.get_text(strip=True) for p in article_elem.select("p") if p.get_text(strip=True)] if article_elem else []

    # コメント数
    comment_count = 0
    count_elem = soup.select_one(".news-comment-plural__count")
    if count_elem:
        try:
            comment_count = int(count_elem.get_text().replace(",", ""))
        except:
            pass

    # コメント一覧取得
    comments = []
    comment_blocks = soup.select(".news-comment-list__item")
    for block in comment_blocks:
        text = block.select_one(".news-comment-body")
        user = block.select_one(".news-comment-user__name")
        time_tag = block.select_one(".news-comment-time")
        if text:
            comments.append([user.text.strip() if user else "",
                             parse_relative_time(time_tag.text.strip()).strftime("%Y/%m/%d %H:%M") if time_tag else "",
                             text.text.strip()])

    return paragraphs, comment_count, comments

# ===========================
# 実行ループ
# ===========================
for idx, url in enumerate(urls):
    if not url.strip():
        continue
    print(f"▶ {idx+1}: {url}")
    try:
        paragraphs, comment_count, comments = scrape_article(url)

        # output: 本文 & コメント一覧
        page_ws = sheet.duplicate_sheet(base_ws.id, new_sheet_name=str(idx + 1))
        target_ws = sheet.worksheet(str(idx + 1))
        for i, line in enumerate(paragraphs[:15]):
            target_ws.update_cell(i + 1, 1, line)

        for i, comment in enumerate(comments[:100]):
            target_ws.update(f"A{20 + i}:C{20 + i}", [comment])

        # inputシートF列にコメント数を記録
        input_ws.update_cell(idx + 2, 6, comment_count)

    except Exception as e:
        print(f"❌ Error at {url}: {e}")

# 終了処理
driver.quit()
print("✅ 全処理完了")
