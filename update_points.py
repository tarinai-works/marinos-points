import json
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

DATA_FILE = "data.json"
TOTAL_MATCHES = 38
JST = timezone(timedelta(hours=9))

def fetch_marinos_matches():
    """
    スポーツナビの月別日程を巡回し、J1リーグ戦の終了スコアを時系列順に正確に抽出します。
    """
    base_url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # シーズン全月（8月〜翌年6月）のリスト
    # 例: 202608, 202609 ... 202706
    months = [f"2026{m:02d}" for m in range(8, 13)] + [f"2027{m:02d}" for m in range(1, 7)]
    
    match_results = []

    for month_str in months:
        url = f"{base_url}?gk=2&month={month_str}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")

            rows = soup.find_all("tr")
            for row in rows:
                text = row.get_text()

                # J1リーグかつ第○節の表記がある行
                if not (("J1" in text or "明治安田" in text) and "節" in text):
                    continue
                # カップ戦除外
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"]):
                    continue

                # スコア表記（例: "1 - 0", "0 - 2"）を抽出
                score_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
                if not score_match:
                    continue  # 試合前（キックオフ時刻のみ）の行はスキップ

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                # スコアの前後に横浜FMがあるかでホーム/アウェイを判定
                # 横浜FMがスコアより前ならホーム（左がマリノス得点）
                pos_yfm = text.find("横浜FM")
                pos_score = score_match.start()

                if pos_yfm != -1 and pos_yfm < pos_score:
                    # ホーム戦: s1がマリノス、s2が相手
                    marinos_score, opp_score = s1, s2
                else:
                    # アウェイ戦: s2がマリノス、s1が相手
                    marinos_score, opp_score = s2, s1

                if marinos_score > opp_score:
                    pts = 3
                elif marinos_score == opp_score:
                    pts = 1
                else:
                    pts = 0

                match_results.append(pts)
                if len(match_results) >= TOTAL_MATCHES:
                    break

        except Exception as e:
            print(f"Error fetching month {month_str}: {e}")

        if len(match_results) >= TOTAL_MATCHES:
            break

    return match_results


def update_data():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} が見つかりません。")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_points = fetch_marinos_matches()

    if match_points and len(match_points) > 0:
        cumulative = []
        current = 0
        for pts in match_points:
            current += pts
            cumulative.append(current)

        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        played_count = len(match_points)
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({played_count}試合消化時点)"
        print(f"更新成功: {played_count}試合消化（勝ち点推移: {cumulative[:played_count]}）")
    else:
        print("有効な試合スコアが取得できなかったため、既存データを維持します。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json の更新処理が完了しました。")


if __name__ == "__main__":
    update_data()
