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
INPUT_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'

DATE_STR = datetime.now().strftime('%y%m%d')
BASE_SHEET = 'Base'

# ヘッドレスブラウザ設定
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# WebDriver起動
browser = webdriver.Chrome(options=chrome_options)

# 入力スプレッドシートからURL取得
print("--- Getting URLs from spreadsheet ---")
sh_input = gc.open_by_key(INPUT_SPREADSHEET_ID)
input_ws = sh_input.worksheet("URLS")
urls = input_ws.col_values(3)[1:]  # C列（C2以降）
print(f"Found {len(urls)} URLs: {urls}")

# 出力スプレッドシートを設定
sh_output = gc.open_by_key(OUTPUT_SPREADSHEET_ID)

# 日付シートがなければ作成
print("--- Checking output sheet ---")
if DATE_STR not in [ws.title for ws in sh_output.worksheets()]:
    sh_output.duplicate_sheet(sh_output.worksheet(BASE_SHEET).id, new_sheet_name=DATE_STR)
    print(f"Created new sheet: {DATE_STR}")
date_ws = sh_output.worksheet(DATE_STR)
print(f"Using output sheet: {date_ws.title}")


# ニュース記事取得関数
def fetch_article_and_comments(url):
    print(f"  - Fetching page source for: {url}")
    browser.get(url)
    time.sleep(3)
    
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    
    # 本文取得
    article_div = soup.find('div', class_='article_body')
    paragraphs = article_div.find_all('p') if article_div else []
    body_lines = [p.get_text(strip=True) for p in paragraphs]
    print(f"  - Found {len(body_lines)} paragraphs for body.")

    # コメント全件取得
    comments = []
    print("  - Scraping comments...")
    try:
        while True:
            more_button = browser.find_element(By.CLASS_NAME, 'news-comment-loadmore-btn')
            if more_button.is_displayed():
                browser.execute_script("arguments[0].click();", more_button)
                time.sleep(1)
            else:
                break
    except Exception as e:
        # ボタンがない場合はループを抜ける
        print(f"  - No more comments button found. Eror: {e}")
        pass

    soup = BeautifulSoup(browser.page_source, 'html.parser')
    comment_divs = soup.find_all('div', class_='news-comment-body')
    comments = [div.get_text(strip=True) for div in comment_divs]
    print(f"  - Found {len(comments)} comments.")

    return body_lines, comments

# 各URL処理
print("--- Starting URL processing ---")
for idx, url in enumerate(urls):
    if not url:
        print(f"Skipping empty URL at index {idx+1}")
        continue
    try:
        print(f"Processing URL {idx+1}: {url}")
        body, comments = fetch_article_and_comments(url)

        # 個別シート作成
        sheet_title = str(idx + 1)
        print(f"  - Creating individual sheet: {sheet_title}")
        if sheet_title in [ws.title for ws in sh_output.worksheets()]:
            sh_output.del_worksheet(sh_output.worksheet(sheet_title))
            print(f"    - Deleted old sheet: {sheet_title}")
        new_ws = sh_output.add_worksheet(title=sheet_title, rows="100", cols="10")
        print(f"    - Created new sheet: {new_ws.title}")

        # 本文出力
        print(f"  - Writing {len(body)} body paragraphs to sheet...")
        for i, line in enumerate(body):
            new_ws.update_cell(i + 1, 1, line)

        # コメント出力
        print(f"  - Writing {len(comments)} comments to sheet...")
        for j, comment in enumerate(comments):
            new_ws.update_cell(j + 20, 1, comment)

        # コメント数記載
        print(f"  - Updating comment count in {date_ws.title} sheet...")
        date_ws.update_cell(idx + 2, 6, len(comments))  # F列

        print(f"Successfully processed URL {idx+1}")

    except Exception as e:
        print(f"Error processing URL {idx+1} ({url}): {e}")
        date_ws.update_cell(idx + 2, 6, 'ERROR')
        print(f"Updated status to 'ERROR' in {date_ws.title} sheet.")

browser.quit()
print("--- Scraping job finished ---")
