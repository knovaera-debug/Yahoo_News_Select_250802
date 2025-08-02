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
    print(f"🔍 検索開始: {keyword}")
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
        try:
            article_data = f'=HYPERLINK("{link}", "{title}")'
            output_ws.update(f'B{i+1}', article_data)
            output_ws.update(f'C{i+1}', time_str)
            output_ws.update(f'D{i+1}', keyword)
        except Exception as e:
            print(f"⚠️ 書き込み失敗: {e}")

        # コメント数取得（必要に応じて）
        try:
            if link.startswith('https://news.yahoo.co.jp/articles/'):
                driver.get(link)
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                comment_count_elem = soup.select_one('span[class*="commentCount"]')
                comment_count = comment_count_elem.text.strip() if comment_count_elem else "0"
                output_ws.update(f'F{i+1}', comment_count)
        except Exception as e:
            print(f"⚠️ コメント数取得失敗: {e}")


print("✅ 完了")
driver.quit()
