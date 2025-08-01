import gspread
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from datetime import datetime
import os

# Google Sheetsからキーワード取得
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
client = gspread.authorize(creds)

SHEET_ID = "xxxxx"  # ← あなたのスプレッドシートID
worksheet = client.open_by_key(SHEET_ID).worksheet("keywords")
keywords = worksheet.col_values(1)[1:]  # A2以降

today = datetime.now().strftime("%y%m%d")
wb = Workbook()
ws = wb.active
ws.append(["キーワード", "タイトル", "URL", "本文", "コメント数", "日付"])

for keyword in keywords:
    url = f"https://news.yahoo.co.jp/search?p={keyword}"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, "html.parser")
    articles = soup.select("li.newsFeed_item")[:5]  # 上位5件だけ

    for article in articles:
        title = article.select_one(".newsFeed_item_title").text
        link = article.select_one("a").get("href")
        date = article.select_one("time").text if article.select_one("time") else ""
        # 本文取得（詳細ページへ）
        body = ""
        try:
            detail = requests.get(link)
            detail_soup = BeautifulSoup(detail.content, "html.parser")
            body_tag = detail_soup.select_one("p.ynDetailText") or detail_soup.select_one(".article_body")
            body = body_tag.text if body_tag else ""
        except:
            pass
        ws.append([keyword, title, link, body[:100], "", date])

output_file = f"{today}.xlsx"
wb.save(output_file)
