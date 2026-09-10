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
    J1リーグの終了した試合を消化順に取得し、
    スポーツナビ公式の勝敗マーク（○/●/△）をダイレクトに判定して正確な勝ち点を返します。
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

            # 未消化（予定）の試合はスキップ（確定マークまたは結果表記がある行のみ）
            has_result_mark = any(m in text for m in ["○", "●", "△", "PK"])
            if not has_result_mark and "終了" not in text and "結果" not in text:
                continue

            # --- 最優先：スポーツナビの勝敗マークによる直接判定 ---
            pts = None
            if "○" in text:
                pts = 3  # 勝利
            elif "△" in text:
                pts = 1  # 引分
            elif "●" in text:
                pts = 0  # 敗戦

            # 勝敗マークがテキストから拾えなかった場合の予備判定（スコア解析）
            if pts is None:
                matches = re.findall(r"(?<!\d:)(\b[0-9]\b)\s*[-–]\s*(\b[0-9]\b)(?!\d)", text)
                if matches:
                    s1, s2 = int(matches[0][0]), int(matches[0][1])
                    if s1 == s2:
                        pts = 1
                    else:
                        # アウェイ（@表記または横浜FMが右側）を正確に判定
                        is_away = ("@" in text) or (text.find("横浜FM") > text.find(f"{s1}") if "横浜FM" in text else False)
                        marinos_score = s2 if is_away else s1
                        opponent_score = s1 if is_away else s2
                        pts = 3 if marinos_score > opponent_score else 0

            # 有効な試合結果であれば追加
            if pts is not None:
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

        # 38戦分を None で埋める
        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        played_count = len(match_points)
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({played_count}試合消化時点)"
        print(f"最新データを正常に反映しました: {played_count}試合消化時点（獲得勝ち点推移: {cumulative[:played_count]}）")
    else:
        print("試合結果が取得できなかったため、既存データを維持します。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json を更新しました。")


if __name__ == "__main__":
    update_data()
