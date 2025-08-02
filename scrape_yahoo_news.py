import chromedriver_autoinstaller
chromedriver_autoinstaller.install()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import time

# ✅ Google認証情報を環境変数から読み込む
credentials_json = os.getenv('GOOGLE_CREDENTIALS')
if credentials_json is None:
    raise ValueError("環境変数 GOOGLE_CREDENTIALS が設定されていません")

credentials_dict = json.loads(credentials_json)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)

# ✅ Chrome設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev_shm_usage')
driver = webdriver.Chrome(options=options)

try:
    # ✅ 入力スプレッドシートからURLをすべて取得
    INPUT_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
    input_ws = gc.open_by_key(INPUT_SPREADSHEET_ID).worksheet('URLS')
    # A2以降のA列の値をすべて取得
    urls = input_ws.col_values(1)[1:]

    # ✅ 出力スプレッドシートを開く
    OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
    output_ws = gc.open_by_key(OUTPUT_SPREADSHEET_ID).worksheet('Base')

    for base_url in urls:
        if not base_url:
            continue

        page_number = 1
        while True:
            # ページ番号に応じてURLを構築
            if page_number == 1:
                article_url = base_url
            else:
                # URLの末尾に「?page=」とページ番号を追加
                article_url = f"{base_url}?page={page_number}"

            print(f"🔍 URL: {article_url} の記事本文を取得します。")

            article_body = ""
            driver.get(article_url)

            # ページが存在しない場合のチェック
            if "指定されたURLは存在しませんでした。" in driver.page_source:
                print(f"ℹ️ {page_number}ページ目は存在しませんでした。処理を終了します。")
                break

            # クッキー同意ポップアップの処理
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.sc-f584f1b4-2.bQjFpQ'))
                ).click()
                print("ℹ️ クッキー同意ポップアップを閉じました。")
            except (TimeoutException, NoSuchElementException):
                print("ℹ️ クッキー同意ポップアップは表示されませんでした。")

            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'article'))
                )
                article_soup = BeautifulSoup(driver.page_source, 'html.parser')
                article_container = article_soup.find('article')
                if article_container:
                    article_body = article_container.get_text(separator='\n', strip=True)
                    print(f"✅ {page_number}ページ目の記事本文の取得に成功しました。")
                    print(f"　取得した本文の文字数: {len(article_body)}文字")
                    print(f"　取得した本文の冒頭: {article_body[:50]}...")
                else:
                    raise NoSuchElementException(f"{page_number}ページ目の記事本文が見つかりませんでした。")
            except (TimeoutException, NoSuchElementException) as e:
                print(f"⚠️ {page_number}ページ目の記事本文の取得に失敗しました: {e}")
                print("--- デバッグ情報（HTMLソースの冒頭500文字） ---")
                print(driver.page_source[:500])
                print("-------------------------------------------------")
                article_body = "記事本文が見つかりませんでした。"

            # ✅ 出力スプレッドシートに書き込み
            try:
                # B6セルから書き込みを開始
                row_to_write = f'B{5 + page_number}'

                if len(article_body) > 50000:
                    truncated_body = article_body[:50000] + "..."
                    output_ws.update(row_to_write, [[truncated_body]])
                    print(f"✅ 記事本文が長いため、50000文字に制限して{row_to_write}セルに書き込みました。")
                else:
                    output_ws.update(row_to_write, [[article_body]])
                    print(f"✅ {row_to_write}セルに記事本文を書き込みました。")
            except Exception as e:
                print(f"⚠️ 書き込み失敗: {e}")
            
            # 次のページへ
            page_number += 1

finally:
    driver.quit()
    print("✅ 完了")
