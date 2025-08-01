import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print("📌 実行開始")

# Step 1: Google 認証（Secretsから読み込んだ JSON をファイルに保存）
with open("tmp_creds.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS"])

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('tmp_creds.json', scope)
client = gspread.authorize(creds)

# Step 2: スプレッドシートのID設定
KEYWORDS_SHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"
OUTPUT_SHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"

# Step 3: キーワード取得
keywords_ws = client.open_by_key(KEYWORDS_SHEET_ID).sheet1
keywords = keywords_ws.col_values(1)[1:]  # A2以降
print("✅ キーワード一覧:", keywords)

# Step 4: 出力シートの準備（日付別シートを新規 or 取得）
output_book = client.open_by_key(OUTPUT_SHEET_ID)
today_str = datetime.now().strftime("%y%m%d")

try:
    output_ws = output_book.worksheet(today_str)
    print(f"📄 既存シート {today_str} を使用")
except gspread.exceptions.WorksheetNotFound:
    output_ws = output_book.add_worksheet(title=today_str, rows="1000", cols="20")
    print(f"🆕 シート {today_str} を新規作成")

output_ws.clear()
output_ws.append_row(["キーワード", "タイトル", "URL", "本文（冒頭100字）", "日付", "取得日時"])

# Step 5: Yahooニュース取得処理
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

for keyword in keywords:
    print(f"🔍 検索開始: {keyword}")
    url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        articles = soup.select("li.newsFeed_item")
        print(f"　→ 見つかった記事数: {len(articles)}")

        for article in articles[:5]:  # 上位5件まで処理
            title_tag = article.select_one(".newsFeed_item_title")
            link_tag = article.select_one("a")
            if not title_tag or not link_tag:
                continue

            title = title_tag.text.strip()
            link = link_tag["href"]
            date = article.select_one("time").text if article.select_one("time") else ""

            # 本文取得（詳細ページへ）
            body = ""
            try:
                detail = requests.get(link, headers=headers, timeout=10)
                detail_soup = BeautifulSoup(detail.content, "html.parser")
                tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body")
                body = tag.text.strip() if tag else ""
            except Exception as e:
                print(f"　⚠️ 本文取得失敗: {e}")

            output_ws.append_row([
                keyword, title, link, body[:100], date,
                datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            ])

    except Exception as e:
        print(f"❌ エラー発生（{keyword}）: {e}")
