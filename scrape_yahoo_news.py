import os
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# Google Sheets認証
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

# Google Sheets設定
SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
DATE_STR = datetime.now().strftime('%y%m%d')
BASE_SHEET = 'Base'

# ヘッドレスブラウザ設定
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# WebDriver起動
# main.ymlで手動インストールされたchromedriverを使用する
browser = webdriver.Chrome(options=chrome_options)

# Google SheetからURL取得
sh = gc.open_by_key(SPREADSHEET_ID)
input_ws = sh.worksheet("input")
urls = input_ws.col_values(3)[1:]  # C列（C2以降）

# 日付シートがなければ作成
if DATE_STR not in [ws.title for ws in sh.worksheets()]:
    sh.duplicate_sheet(sh.worksheet(BASE_SHEET).id, new_sheet_name=DATE_STR)

date_ws = sh.worksheet(DATE_STR)

# ニュース記事取得関数
def fetch_article_and_comments(url):
    browser.get(url)
    time.sleep(3)
    
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    
    # 本文取得
    article_div = soup.find('div', class_='article_body')
    paragraphs = article_div.find_all('p') if article_div else []
    body_lines = [p.get_text(strip=True) for p in paragraphs]

    # コメント全件取得
    comments = []
    try:
        while True:
            more_button = browser.find_element(By.CLASS_NAME, 'news-comment-loadmore-btn')
            if more_button.is_displayed():
                browser.execute_script("arguments[0].click();", more_button)
                time.sleep(1)
            else:
                break
    except:
        pass

    soup = BeautifulSoup(browser.page_source, 'html.parser')
    comment_divs = soup.find_all('div', class_='news-comment-body')
    comments = [div.get_text(strip=True) for div in comment_divs]

    return body_lines, comments

# 各URL処理
for idx, url in enumerate(urls):
    if not url:
        continue
    try:
        body, comments = fetch_article_and_comments(url)

        # 個別シート作成
        sheet_title = str(idx + 1)
        if sheet_title in [ws.title for ws in sh.worksheets()]:
            sh.del_worksheet(sh.worksheet(sheet_title))
        new_ws = sh.add_worksheet(title=sheet_title, rows="100", cols="10")

        # 本文出力（1〜）
        for i, line in enumerate(body):
            new_ws.update_cell(i + 1, 1, line)

        # コメント出力（20〜）
        for j, comment in enumerate(comments):
            new_ws.update_cell(j + 20, 1, comment)

        # コメント数記載
        date_ws.update_cell(idx + 2, 6, len(comments))  # F列

    except Exception as e:
        print(f"Error at {url}: {e}")
        date_ws.update_cell(idx + 2, 6, 'ERROR')

browser.quit()
