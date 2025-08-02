import os
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import requests
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

# Selenium設定
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
browser = webdriver.Chrome(options=chrome_options)

# 入力スプレッドシートからURLを取得
print("--- Getting URLs from spreadsheet ---")
sh_input = gc.open_by_key(INPUT_SPREADSHEET_ID)
input_ws = sh_input.worksheet("URLS")
urls = input_ws.col_values(3)[1:] # C列（C2以降）からURLを取得
print(f"Found {len(urls)} URLs: {urls}")

# 出力スプレッドシートを設定
sh_output = gc.open_by_key(OUTPUT_SPREADSHEET_ID)
print("--- Checking output sheet ---")
if DATE_STR not in [ws.title for ws in sh_output.worksheets()]:
    sh_output.duplicate_sheet(sh_output.worksheet(BASE_SHEET).id, new_sheet_name=DATE_STR)
    print(f"Created new sheet: {DATE_STR}")
date_ws = sh_output.worksheet(DATE_STR)
print(f"Using output sheet: {date_ws.title}")

# ニュース記事の処理
print("--- Starting URL processing ---")
output_column = 2 # B列から開始
for idx, base_url in enumerate(urls, start=1):
    if not base_url or not base_url.startswith(('http://', 'https://')):
        print(f'Skipping invalid or empty URL at index {idx}: {base_url}')
        continue

    headers = {'User-Agent': 'Mozilla/5.0'}

    # 記事本文の取得
    article_bodies = []
    page = 1
    print(f"  - Processing article body for URL {idx}: {base_url}")
    while True:
        url = base_url if page == 1 else f"{base_url}?page={page}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')

        if '指定されたURLは存在しませんでした' in res.text:
            break

        body_tag = soup.find('article')
        body_text = body_tag.get_text(separator='\n').strip() if body_tag else ''

        if not body_text or body_text in article_bodies:
            break

        article_bodies.append(body_text)
        page += 1
    print(f"  - Found {len(article_bodies)} body pages.")
    
    # 記事タイトルと投稿日取得
    res_main = requests.get(base_url, headers=headers)
    soup_main = BeautifulSoup(res_main.text, 'html.parser')
    page_title = soup_main.title.string if soup_main.title else '取得不可'
    title = page_title.replace(' - Yahoo!ニュース', '').strip() if page_title else '取得不可'
    date_tag = soup_main.find('time')
    article_date = date_tag.text.strip() if date_tag else '取得不可'
    
    # コメント取得（Selenium使用）
    comments = []
    comment_page = 1
    print("  - Scraping comments with Selenium...")
    while True:
        comment_url = f"{base_url}/comments?page={comment_page}"
        browser.get(comment_url)
        time.sleep(2)

        if '指定されたURLは存在しませんでした' in browser.page_source:
            break

        soup_comments = BeautifulSoup(browser.page_source, 'html.parser')
        comment_paragraphs = soup_comments.find_all('p', class_='sc-169yn8p-10 hYFULX')
        page_comments = [p.get_text(strip=True) for p in comment_paragraphs if p.get_text(strip=True)]

        if not page_comments:
            break

        comments.extend(page_comments)
        comment_page += 1
    print(f"  - Found {len(comments)} comments.")

    # 出力シートに書き込み
    try:
        current_column_idx = output_column + (idx - 1)
        
        # タイトル、投稿日、URLを1行目から書き込み
        cell_updates = []
        cell_updates.append((1, current_column_idx, title))
        cell_updates.append((2, current_column_idx, article_date))
        cell_updates.append((3, current_column_idx, base_url))
        
        # 本文を4行目以降に書き込み
        for i, body in enumerate(article_bodies, start=4):
            cell_updates.append((i, current_column_idx, body))

        # コメントを20行目以降に書き込み
        for i, comment in enumerate(comments, start=20):
            cell_updates.append((i, current_column_idx, comment))

        for row, col, value in cell_updates:
            date_ws.update_cell(row, col, value)

        print(f"  - Successfully wrote data for URL {idx} to column {current_column_idx}")

    except Exception as e:
        print(f"  - Error writing to Google Sheets for URL {idx}: {e}")
        date_ws.update_cell(1, output_column + (idx - 1), 'ERROR')

browser.quit()
print("--- Scraping job finished ---")
