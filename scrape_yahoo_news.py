import chromedriver_autoinstaller
chromedriver_autoinstaller.install()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from datetime import datetime
from openpyxl import Workbook
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import time

# ✅ タイムゾーンと日付取得
jst = pytz.timezone('Asia/Tokyo')
now = datetime.now(jst)
today_str = now.strftime('%y%m%d')

# ✅ Google認証・スプレッドシート読み込み
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# ✅ 入力スプレッドシート（キーワード）
KEYWORDS_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
INPUT_SHEET_NAME = 'keywords'
keyword_ws = gc.open_by_key(KEYWORDS_SPREADSHEET_ID).worksheet(INPUT_SHEET_NAME)
keywords = keyword_ws.col_values(1)[1:]  # 1列目の2行目以降

# ✅ 出力スプレッドシート
OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
output_book = gc.open_by_key(OUTPUT_SPREADSHEET_ID)

try:
    output_ws = output_book.worksheet(today_str)
except gspread.exceptions.WorksheetNotFound:
    base_ws = output_book.worksheet("Base")
    output_ws = output_book.duplicate_sheet(source_sheet_id=base_ws.id, new_sheet_name=today_str)

# ✅ Chrome設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

# ✅ 処理本体
for keyword in keywords:
    print(f"\U0001F50D 検索開始: {keyword}")
    url = f"https://news.yahoo.co.jp/search?p={keyword}&ei=utf-8"
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    articles = soup.select('article')
    print(f"　→ 記事数: {len(articles)}")

    for i, article in enumerate(articles[:10], start=1):
        title = article.h3.text.strip() if article.h3 else ""
        link = article.a['href'] if article.a else ""
        time_tag = article.time
        time_str = time_tag['datetime'] if time_tag and 'datetime' in time_tag.attrs else ''

        # ✅ コメント数取得処理
        comment_count = ""
        try:
            if 'news.yahoo.co.jp/articles/' in link:
                driver.get(link)
                time.sleep(1.5)
                soup_detail = BeautifulSoup(driver.page_source, 'html.parser')
                comment_tag = soup_detail.select_one("a[class*='comment']")
                if comment_tag and comment_tag.text:
                    comment_count = ''.join(filter(str.isdigit, comment_tag.text))
        except Exception as e:
            print(f"⚠️ コメント取得失敗: {e}")

        try:
            article_data = f'=HYPERLINK("{link}", "{title}")'
            output_ws.update(f'B{i+1}', article_data)
            output_ws.update(f'C{i+1}', time_str)
            output_ws.update(f'D{i+1}', keyword)
            output_ws.update(f'F{i+1}', comment_count)
        except Exception as e:
            print(f"⚠️ 書き込み失敗: {e}")

print("✅ 完了")
driver.quit()
