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
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)

# 記事本文のセレクタ候補リスト
ARTICLE_BODY_SELECTORS = [
    'div[data-testid="article-body"] p',
    'div.sc-7b29a27c-4 > p.sc-7b29a27c-3',
    'div.article_body > p',
    'div.sc-7b29a27c-4 p',
    'main p'
]

def get_article_body_with_multiple_selectors(soup):
    """複数のセレクタを試して記事本文を取得する関数"""
    for selector in ARTICLE_BODY_SELECTORS:
        body_paragraphs = soup.select(selector)
        if body_paragraphs:
            return "\n".join([p.text.strip() for p in body_paragraphs])
    return ""

try:
    # ✅ 入力スプレッドシートからURLを取得
    INPUT_SPREADSHEET_ID = '1yjHpQMHfJt7shjqZ6SYQNNlHougbrw0ZCgWpFUgv3Sc'
    input_ws = gc.open_by_key(INPUT_SPREADSHEET_ID).worksheet('URLS')
    article_url = input_ws.acell('A2').value
    
    if not article_url:
        print("⚠️ A2セルにURLがありません。処理を終了します。")
    else:
        print(f"🔍 URL: {article_url} の記事本文を取得します。")

        # ✅ 記事ページにアクセスして本文を取得
        article_body = ""
        driver.get(article_url)
        
        # クッキー同意ポップアップの処理
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.sc-f584f1b4-2.bQjFpQ'))
            ).click()
            print("ℹ️ クッキー同意ポップアップを閉じました。")
        except (TimeoutException, NoSuchElementException):
            print("ℹ️ クッキー同意ポップアップは表示されませんでした。")

        # ページが完全に読み込まれるまで待機
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        article_body = get_article_body_with_multiple_selectors(soup)

        if article_body:
            # 取得した本文の文字数を確認
            print("✅ 記事本文の取得に成功しました。")
            print(f"　取得した本文の文字数: {len(article_body)}文字")
            print(f"　取得した本文の冒頭: {article_body[:50]}...")
        else:
            print("⚠️ 記事本文の取得に失敗しました。")
            article_body = "記事本文が見つかりませんでした。"

        # ✅ 出力スプレッドシートに書き込み
        OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
        output_ws = gc.open_by_key(OUTPUT_SPREADSHEET_ID).worksheet('Base')
        
        try:
            # 記事本文が長すぎる場合、50000文字に制限して書き込む
            if len(article_body) > 50000:
                truncated_body = article_body[:50000] + "..."
                output_ws.update('B6', truncated_body)
                print("✅ 記事本文が長いため、50000文字に制限してB6セルに書き込みました。")
            else:
                output_ws.update('B6', article_body)
                print("✅ B6セルに記事本文を書き込みました。")
        except Exception as e:
            print(f"⚠️ 書き込み失敗: {e}")

finally:
    driver.quit()
    print("✅ 完了")
