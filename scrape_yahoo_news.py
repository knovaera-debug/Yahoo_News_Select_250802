import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# GOOGLE_CREDENTIALS を一時ファイルとして保存
with open("tmp_creds.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS"])

# Google Sheets 認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('tmp_creds.json', scope)
client = gspread.authorize(creds)

# スプレッドシートのID
KEYWORDS_SHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"
OUTPUT_SHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"

# キーワード取得
keywords_ws = client.open_by_key(KEYWORDS_SHEET_ID).sheet1
keywords = keywords_ws.col_values(1)[1:]  # A列2行目以降

# 出力用シート（今日の日付で新シート作成）
output_book = client.open_by_key(OUTPUT_SHEET_ID)
today_str = datetime.now().strftime("%y%m%d")

try:
    output_ws = output_book.worksheet(today_str)
except gspread.exceptions.WorksheetNotFound:
    output_ws = output_book.add_worksheet(title=today_str, rows="1000", cols="20")

output_ws.clear()
output_ws.append_row(["キーワード", "タイトル", "URL", "本文（冒頭100字）", "日付", "取得日時"])

# ニュース取得処理
headers = {"User-Agent": "Mozilla/5.0"}
for keyword in keywords:
    url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.content, "html.parser")
    articles = soup.select("li.newsFeed_item")[:5]

    for article in articles:
        try:
            title = article.select_one(".newsFeed_item_title").text.strip()
            link = article.select_one("a")["href"]
            date = article.select_one("time").text if article.select_one("time") else ""

            body = ""
            try:
                detail = requests.get(link, headers=headers)
                detail_soup = BeautifulSoup(detail.content, "html.parser")
                tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body")
                body = tag.text.strip() if tag else ""
            except:
                pass

            output_ws.append_row([
                keyword, title, link, body[:100], date,
                datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            ])
        except Exception as e:
            print(f"❌ Error on keyword '{keyword}': {e}")
