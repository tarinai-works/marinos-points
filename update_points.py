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
    スポーツナビから横浜F・マリノスの公式戦一覧を取得。
    J1リーグ戦かつ「試合終了」となっている確定スコアのみを抽出します。
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

            # 未消化の試合（試合前・予定）は除外。「終了」の文字がある行、またはスコア確定行のみを対象とする
            # スポーツナビでは終了した試合に「終了」または勝敗マークが入ります
            if "終了" not in text and "結果" not in text and not any(mark in text for mark in ["○", "●", "△", "PK"]):
                # 時間表記（例: 19:00）のみでまだ行われていない試合をスキップ
                continue

            # スコア部分を厳密に抽出（「数字 - 数字」かつ、キックオフ時刻の 00 等と誤判定しない）
            # 通常スコアリンクやスコア表示要素（クラス名やtd要素）を走査
            score_elem = row.find(string=re.compile(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$"))
            score1, score2 = None, None

            if score_elem:
                m = re.search(r"(\d+)\s*[-–]\s*(\d+)", score_elem)
                score1, score2 = int(m.group(1)), int(m.group(2))
            else:
                # 行全体テキストから探索（ただし 19:00 のような時刻を除外するため「 - 」前後の数字）
                # スポーツナビのスコアは通常 0〜9 程度の点数
                matches = re.findall(r"(?<!\d:)(\b[0-9]\b)\s*[-–]\s*(\b[0-9]\b)(?!\d)", text)
                if matches:
                    score1, score2 = int(matches[0][0]), int(matches[0][1])

            if score1 is not None and score2 is not None:
                # 横浜FMのホーム/アウェイ判定
                is_home = text.find("横浜FM") < text.find(f"{score1}") if "横浜FM" in text else True
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

    new_results = fetch_marinos_matches()

    if new_results and len(new_results) > 0:
        cumulative = []
        current = 0
        for pts in new_results:
            current += pts
            cumulative.append(current)

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
