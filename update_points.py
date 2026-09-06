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
    スポーツナビから横浜F・マリノスの直近試合結果をスクレイピングする関数。
    J1リーグ戦のみを抽出し、カップ戦（ルヴァン、天皇杯、ACL等）を除外します。
    """
    url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    match_points = []

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # 試合日程テーブルの各行を走査
        rows = soup.find_all("tr")
        for row in rows:
            text = row.get_text()

            # J1リーグ戦以外の大会（ルヴァン杯、天皇杯、ACLなど）はスキップ
            # 大会欄に「ルヴァン」「天皇杯」「ACL」等が含まれている行、またはJ1表記がない場合は除外
            if any(cup in text for cup in ["ルヴァン", "天皇杯", "ACL", "ACLE"]):
                continue

            # スコア表記（例: 2 - 1, 0 - 0）を探索
            score_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
            if score_match:
                score1 = int(score_match.group(1))
                score2 = int(score_match.group(2))

                # ホーム/アウェイの判定
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
        print("試合結果が取得できなかったため、既存データを維持します。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json を更新しました。")


if __name__ == "__main__":
    update_data()
