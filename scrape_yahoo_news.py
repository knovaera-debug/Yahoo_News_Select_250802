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
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

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
driver = webdriver.Chrome(options=chrome_options)

# 入力スプレッドシートからURL取得
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
for idx, base_url in enumerate(urls, start=1):
    if not base_url or not base_url.startswith(('http://', 'https://')):
        print(f'Skipping invalid or empty URL at index {idx}: {base_url}')
        continue

    headers = {'User-Agent': 'Mozilla/5.0'}

    # 記事の複数ページを取得
    article_bodies = []
    page = 1
    print(f"  - Processing article body for: {base_url}")
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
    print(f"  - Article Title: {title}")

    date_tag = soup_main.find('time')
    article_date = date_tag.text.strip() if date_tag else '取得不可'
    print(f"  - Article Date: {article_date}")

    # コメント取得（Selenium使用）
    comments = []
    comment_page = 1
    print("  - Scraping comments with Selenium...")
    while True:
        comment_url = f"{base_url}/comments?page={comment_page}"
        driver.get(comment_url)
        time.sleep(2)

        if '指定されたURLは存在しませんでした' in driver.page_source:
            break

        soup_comments = BeautifulSoup(driver.page_source, 'html.parser')
        comment_paragraphs = soup_comments.find_all('p', class_='sc-169yn8p-10 hYFULX')
        page_comments = [p.get_text(strip=True) for p in comment_paragraphs if p.get_text(strip=True)]

        if not page_comments:
            break

        comments.extend(page_comments)
        comment_page += 1
    print(f"  - Found {len(comments)} comments.")

    # 個別シート作成とデータ挿入（Google Sheetsへ）
    sheet_title = str(idx)
    print(f"  - Writing data to Google Sheet '{sheet_title}'...")
    try:
        # 既存シートを削除
        if sheet_title in [ws.title for ws in sh_output.worksheets()]:
            sh_output.del_worksheet(sh_output.worksheet(sheet_title))
            print(f"    - Deleted old sheet: {sheet_title}")
        
        new_ws = sh_output.add_worksheet(title=sheet_title, rows="200", cols="5")
        
        df_rows = [['項目', '内容']]
        df_rows.append(['タイトル', title])
        df_rows.append(['投稿日時', article_date])
        df_rows.append(['URL', base_url])
        
        for idx_page, body in enumerate(article_bodies, start=1):
            page_label = '本文' if idx_page == 1 else f'本文{idx_page}ページ目'
            df_rows.append([page_label, body])
        
        df_rows.append(['コメント数', len(comments)])
        
        # データを一括で書き込み
        new_ws.update('A1', df_rows)
        
        # コメントを16行目以降に追加
        comment_data = []
        for i, comment in enumerate(comments, start=1):
            comment_data.append([f'コメント{i}', comment])
        
        if comment_data:
            start_row = len(df_rows) + 2
            new_ws.update(f'A{start_row}', comment_data)
        
        # コメント数を出力シートに記載
        date_ws.update_cell(idx + 2, 6, len(comments))
        
        print(f"  - Successfully wrote data for URL {idx}")

    except Exception as e:
        print(f"  - Error writing to Google Sheets for URL {idx}: {e}")
        date_ws.update_cell(idx + 2, 6, 'ERROR')

driver.quit()
print("--- Scraping job finished ---")
