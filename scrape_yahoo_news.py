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
            
        # 最初のページ（page=1）にアクセスしてタイトルと投稿日時を取得
        try:
            driver.get(base_url)
            time.sleep(3) # ページの描画を待つために一時停止を追加
            initial_soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # ✅ B3にタイトルを書き込み (titleタグから取得し、不要な部分を削除)
            page_title = initial_soup.title.string if initial_soup.title else '取得不可'
            news_title = page_title.replace(' - Yahoo!ニュース', '').strip() if ' - Yahoo!ニュース' in page_title else page_title.strip()
            output_ws.update('B3', [[news_title]])
            print(f"✅ B3セルにタイトルを書き込みました: {news_title}")

            # ✅ B4にURLを書き込み
            output_ws.update('B4', [[base_url]])
            print(f"✅ B4セルにURLを書き込みました: {base_url}")

            # ✅ B5に投稿日時を書き込み
            date_tag = initial_soup.find('time')
            news_date = date_tag.text.strip() if date_tag else '取得不可'
            output_ws.update('B5', [[news_date]])
            print(f"✅ B5セルに投稿日時を書き込みました: {news_date}")
            
        except Exception as e:
            print(f"⚠️ タイトル、URL、投稿日時の取得または書き込みに失敗しました: {e}")
            
        # 記事本文（複数ページ対応）の取得と書き込み
        page_number = 1
        while True:
            if page_number == 1:
                article_url = base_url
            else:
                article_url = f"{base_url}?page={page_number}"

            print(f"🔍 URL: {article_url} の記事本文を取得します。")

            article_body = ""
            driver.get(article_url)

            if "指定されたURLは存在しませんでした。" in driver.page_source:
                print(f"ℹ️ {page_number}ページ目は存在しませんでした。本文の取得を終了します。")
                break

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

            try:
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
            
            page_number += 1

        # ✅ コメントの取得と書き込み
        print("-" * 20)
        print("🔍 コメントの取得を開始します。")
        all_comments = []
        comment_page_number = 1
        while True:
            # コメントページのURLを構築
            if comment_page_number == 1:
                comment_url = f"{base_url}/comments"
            else:
                comment_url = f"{base_url}/comments?page={comment_page_number}"

            print(f"🔍 URL: {comment_url} のコメントを取得します。")
            driver.get(comment_url)
            
            # ページが存在しない場合のチェック
            if "指定されたURLは存在しませんでした。" in driver.page_source:
                print(f"ℹ️ コメントの{comment_page_number}ページ目は存在しませんでした。コメントの取得を終了します。")
                break
            
            try:
                # コメントのコンテナが読み込まれるまで待機
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.ca-list-item'))
                )
                comment_soup = BeautifulSoup(driver.page_source, 'html.parser')
                # 各コメントのテキストを取得
                comments_on_page = comment_soup.select('.ca-list-item')
                if comments_on_page:
                    for comment_item in comments_on_page:
                        comment_text = comment_item.find('p', class_='ca-body').text.strip()
                        all_comments.append(comment_text)
                    print(f"✅ コメントの{comment_page_number}ページ目から{len(comments_on_page)}件取得しました。")
                else:
                    print(f"ℹ️ コメントの{comment_page_number}ページ目にコメントはありませんでした。")
                    break

            except (TimeoutException, NoSuchElementException) as e:
                print(f"⚠️ コメントの取得に失敗しました: {e}")
                break

            comment_page_number += 1

        # ✅ 取得したコメントの総数をB18に書き込み
        try:
            output_ws.update('B18', [[len(all_comments)]])
            print(f"✅ B18セルにコメント総数（{len(all_comments)}件）を書き込みました。")
        except Exception as e:
            print(f"⚠️ コメント総数の書き込みに失敗しました: {e}")

        # ✅ 取得したコメントをB19以降に書き込み
        if all_comments:
            try:
                # コメントのリストを書き込み用に変換
                comments_to_write = [[c] for c in all_comments]
                output_ws.update('B19', comments_to_write)
                print(f"✅ B19セル以降に{len(all_comments)}件のコメントを書き込みました。")
            except Exception as e:
                print(f"⚠️ コメントの書き込みに失敗しました: {e}")
        else:
            print("ℹ️ 取得したコメントはありませんでした。")
finally:
    driver.quit()
    print("✅ 完了")
