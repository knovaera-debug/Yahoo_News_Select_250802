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
        
        try:
            # 記事本文の段落が読み込まれるまで最大30秒待機
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="article-body"] p'))
            )
            article_soup = BeautifulSoup(driver.page_source, 'html.parser')
            body_paragraphs = article_soup.select('div[data-testid="article-body"] p')
            article_body = "\n".join([p.text.strip() for p in body_paragraphs])
            print("✅ 記事本文の取得に成功しました。")
            print(f"　取得した本文の冒頭: {article_body[:50]}...")
        except (TimeoutException, NoSuchElementException):
            print("⚠️ 記事本文の取得に失敗しました。")

        # ✅ 出力スプレッドシートに書き込み
        OUTPUT_SPREADSHEET_ID = '1ff9j8Dr2G6UO2GjsLNpgC8bW0KJmX994iJruw4X_qVM'
        output_ws = gc.open_by_key(OUTPUT_SPREADSHEET_ID).worksheet('Base')
        
        try:
            # 記事本文が空の場合でもエラーにならないように、空文字列を書き込む
            output_ws.update('B6', article_body)
            print("✅ B6セルに記事本文を書き込みました。")
        except Exception as e:
            print(f"⚠️ 書き込み失敗: {e}")

finally:
    driver.quit()
    print("✅ 完了")
