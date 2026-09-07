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
    スポーツナビの日程表から横浜F・マリノスの公式戦一覧を取得。
    J1リーグ戦かつ「試合終了」の確定スコアのみを、開催された時系列順に抽出します。
    日程の前後（前倒し・延期）があっても、実際に消化された順番で累積計算されます。
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

        rows = soup.find_all("tr")
        for row in rows:
            text = row.get_text()

            # J1リーグかつ第○節の表記がある行に限定
            is_j1 = ("J1" in text or "明治安田" in text) and ("節" in text)
            is_cup = any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"])
            if not is_j1 or is_cup:
                continue

            # 未消化（予定）の試合はスキップ。「終了」「結果」または勝敗記号がある確定行のみ
            if "終了" not in text and "結果" not in text and not any(mark in text for mark in ["○", "●", "△", "PK"]):
                continue

            # スコアの抽出
            score_elem = row.find(string=re.compile(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$"))
            score1, score2 = None, None

            if score_elem:
                m = re.search(r"(\d+)\s*[-–]\s*(\d+)", score_elem)
                score1, score2 = int(m.group(1)), int(m.group(2))
            else:
                matches = re.findall(r"(?<!\d:)(\b[0-9]\b)\s*[-–]\s*(\b[0-9]\b)(?!\d)", text)
                if matches:
                    score1, score2 = int(matches[0][0]), int(matches[0][1])

            if score1 is not None and score2 is not None:
                is_home = text.find("横浜FM") < text.find(f"{score1}") if "横浜FM" in text else True
                marinos_score = score1 if is_home else score2
                opponent_score = score2 if is_home else score1

                if marinos_score > opponent_score:
                    pts = 3
                elif marinos_score == opponent_score:
                    pts = 1
                else:
                    pts = 0

                # 開催順に追加
                match_points.append(pts)

                if len(match_points) >= TOTAL_MATCHES:
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

    match_points = fetch_marinos_matches()

    if match_points and len(match_points) > 0:
        cumulative = []
        current = 0
        for pts in match_points:
            current += pts
            cumulative.append(current)

        # 未消化分は None で埋める
        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        played_count = len(match_points)
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026シーズン ({played_count}試合消化時点)"
        print(f"最新データを反映しました: {played_count}試合消化時点（勝ち点: {current}）")
    else:
        print("試合結果が取得できなかったため、既存データを維持します。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json を更新しました。")


if __name__ == "__main__":
    update_data()
