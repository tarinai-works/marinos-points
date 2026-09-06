import json
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

DATA_FILE = "data.json"
TOTAL_ROUNDS = 38
JST = timezone(timedelta(hours=9))

def fetch_marinos_matches():
    """
    スポーツナビやJリーグ関連速報等から横浜F・マリノスの直近試合結果をスクレイピングする関数。
    ※ 取得先のHTML構造変更に耐えられるよう、正規表現と安全なフォールバックを備えています。
    """
    # 取得用URL（スポーツナビ J1日程・結果）
    url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    match_points = []

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # 試合行（テーブル行またはリストアイテム）の解析
        rows = soup.find_all("tr")
        for row in rows:
            text = row.get_text()
            # スコア表記（例: 2 - 1, 0 - 0）を探索
            score_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
            if score_match:
                # 横浜FMがホーム側かアウェイ側かを判定して得失点比較
                score1 = int(score_match.group(1))
                score2 = int(score_match.group(2))
                
                # スコア前後のチーム名から横浜FMの位置を特定
                is_home = text.find("横浜FM") < text.find(score_match.group(0)) if "横浜FM" in text else True
                marinos_score = score1 if is_home else score2
                opponent_score = score2 if is_home else score1

                if marinos_score > opponent_score:
                    match_points.append(3)
                elif marinos_score == opponent_score:
                    match_points.append(1)
                else:
                    match_points.append(0)

                if len(match_points) >= TOTAL_ROUNDS:
                    break

    except Exception as e:
        print(f"スクレイピング中にエラーが発生しました: {e}")
        return None

    return match_points


def update_data():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} が見つかりません。")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 試合結果を取得
    new_results = fetch_marinos_matches()

    # 取得に成功し、かつ1試合以上の結果が取れた場合のみ反映
    if new_results and len(new_results) > 0:
        cumulative = []
        current = 0
        for pts in new_results:
            current += pts
            cumulative.append(current)

        # 未消化の節は None で埋める
        while len(cumulative) < TOTAL_ROUNDS:
            cumulative.append(None)

        completed_rounds = len(new_results)
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026シーズン (第{completed_rounds}節終了時点)"
        print(f"最新データを反映しました: 第{completed_rounds}節終了時点（勝ち点: {current}）")
    else:
        print("最新の試合結果の取得が行えなかったため、既存の currentPoints を維持します。")

    # 更新日時の更新
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json を更新しました。")


if __name__ == "__main__":
    update_data()
