import os
import requests
import gspread
from datetime import datetime
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials

print("📌 実行開始")

# --- 認証：GitHub Secrets の GOOGLE_CREDENTIALS を一時ファイルに保存 ---
with open("tmp_creds.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS"])

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('tmp_creds.json', scope)
client = gspread.authorize(creds)

# --- スプレッドシートID定義 ---
KEYWORDS_SHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"
OUTPUT_SHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"

# --- キーワード取得 ---
keywords_ws = client.open_by_key(KEYWORDS_SHEET_ID).sheet1
keywords = keywords_ws.col_values(1)[1:]  # A列2行目以降
print("✅ キーワード一覧:", keywords)

# --- 出力シートの準備 ---
today_str = datetime.now().strftime("%y%m%d")
output_book = client.open_by_key(OUTPUT_SHEET_ID)

try:
    output_ws = output_book.worksheet(today_str)
    print(f"📄 既存シート {today_str} を使用")
except gspread.exceptions.WorksheetNotFound:
    output_ws = output_book.add_worksheet(title=today_str, rows="1000", cols="20")
    print(f"🆕 シート {today_str} を新規作成")

output_ws.clear()
output_ws.append_row(["キーワード", "タイトル", "URL", "本文（冒頭100字）", "日付", "取得日時"])

# --- User-Agent強化（Bot回避）---
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

# --- 各キーワードに対して Yahooニュース検索実行 ---
for keyword in keywords:
    print(f"🔍 検索開始: {keyword}")
    search_url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"

    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        # 最新のYahoo構造に対応したセレクタ
        articles = soup.select("div.sc-1out364-0")  # 記事全体ブロック
        print(f"　→ 見つかった記事数: {len(articles)}")

        for article in articles[:5]:  # 上位5件まで処理
            try:
                title_tag = article.select_one("a")
                if not title_tag:
                    continue

                title = title_tag.text.strip()
                link = title_tag["href"]
                date_tag = article.select_one("time")
                date = date_tag.text.strip() if date_tag else ""

                # --- 記事本文の取得 ---
                body = ""
                try:
                    detail = requests.get(link, headers=headers, timeout=10)
                    detail_soup = BeautifulSoup(detail.content, "html.parser")
                    tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body")
                    body = tag.text.strip() if tag else ""
                except Exception as e:
                    print(f"　⚠️ 本文取得失敗: {e}")

                output_ws.append_row([
                    keyword,
                    title,
                    link,
                    body[:100],
                    date,
                    datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                ])
            except Exception as e:
                print(f"　⚠️ 記事処理エラー: {e}")
    except Exception as e:
        print(f"❌ エラー（{keyword}）: {e}")
