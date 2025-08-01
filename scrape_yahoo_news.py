import os
import time
import gspread
import chromedriver_autoinstaller
from bs4 import BeautifulSoup
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

print("📌 実行開始")

# ChromeDriver 自動インストール
chromedriver_autoinstaller.install()

# Google 認証
with open("tmp_creds.json", "w") as f:
    f.write(os.environ["GOOGLE_CREDENTIALS"])

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name("tmp_creds.json", scope)
client = gspread.authorize(creds)

# スプレッドシート ID
KEYWORDS_SHEET_ID = "1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc"
OUTPUT_SHEET_ID = "1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM"

# キーワード取得
keywords_ws = client.open_by_key(KEYWORDS_SHEET_ID).sheet1
keywords = keywords_ws.col_values(1)[1:]
print("✅ キーワード一覧:", keywords)

# 出力用ワークシート準備
today_str = datetime.now().strftime("%y%m%d")
output_book = client.open_by_key(OUTPUT_SHEET_ID)

try:
    output_ws = output_book.worksheet(today_str)
    print(f"📄 既存シート {today_str} を使用")
except:
    output_ws = output_book.add_worksheet(title=today_str, rows="1000", cols="20")
    print(f"🆕 シート {today_str} を新規作成")

output_ws.clear()
output_ws.append_row(["キーワード", "タイトル", "URL", "本文（冒頭100字）", "日付", "取得日時"])

# Selenium ブラウザ設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

# 各キーワードで検索・収集
for keyword in keywords:
    print(f"🔍 検索開始: {keyword}")
    search_url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"
    driver.get(search_url)
    time.sleep(3)  # JavaScriptレンダリング待ち

    soup = BeautifulSoup(driver.page_source, "html.parser")
    articles = soup.select("div.sc-1out364-0")
    print(f"　→ 記事数: {len(articles)}")

    for article in articles[:5]:
        try:
            a_tag = article.select_one("a")
            if not a_tag:
                continue

            title = a_tag.text.strip()
            link = a_tag["href"]
            date_tag = article.select_one("time")
            date = date_tag.text if date_tag else ""

            # 本文取得
            driver.get(link)
            time.sleep(2)
            detail_soup = BeautifulSoup(driver.page_source, "html.parser")
            tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body")
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
