import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 1. 既存の data.json を読み込む
data_file = 'data.json'
if os.path.exists(data_file):
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    raise FileNotFoundError("data.json が見つかりません。")

# 2. 試合結果・勝ち点の取得ロジック
# （※外部サイトからの取得や公式データ等の更新処理をここで行います）
# ここでは動作テスト用に、既存データが存在することを確認しつつ日付を更新する構成にしています
current_points = data.get("currentPoints", [])

# 例: データ更新日時の更新
today_str = datetime.now().strftime('%Y-%m-%d %H:%M')
data["updated_at"] = today_str
data["currentSeasonLabel"] = f"2026シーズン (第{len(current_points)}節終了時点 / 自動更新: {today_str})"

# 3. data.json を上書き保存
with open(data_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("data.json の更新が完了しました。")
