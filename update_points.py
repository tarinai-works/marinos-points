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
    スポーツナビの月別日程を巡回し、J1リーグ戦の終了スコア・詳細情報を時系列順に抽出します。
    """
    base_url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 2026年8月〜2027年6月
    months = [f"2026{m:02d}" for m in range(8, 13)] + [f"2027{m:02d}" for m in range(1, 7)]
    
    match_list = []

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

                # J1リーグ戦のみ対象
                if not (("J1" in text or "明治安田" in text) and "節" in text):
                    continue
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"]):
                    continue

                # スコア表記を抽出
                score_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
                if not score_match:
                    continue

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                # 第○節を抽出
                sec_match = re.search(r"第?(\d+)\s*節", text)
                section_str = f"第{sec_match.group(1)}節" if sec_match else f"{len(match_list) + 1}戦目"

                # 日付を抽出（例: 8/7, 9/2 等）
                date_match = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_match.group(1) if date_match else ""

                # ホーム / アウェイ判定
                pos_yfm = text.find("横浜FM")
                pos_score = score_match.start()
                is_home = (pos_yfm != -1 and pos_yfm < pos_score)

                if is_home:
                    marinos_score, opp_score = s1, s2
                    ha_str = "H"
                    # 対戦相手の抽出（スコアより後ろのチーム名）
                    after_text = text[score_match.end():]
                    opp_m = re.search(r"([^\s\d\(\)\[\]]+)", after_text)
                    opponent = opp_m.group(1) if opp_m else "相手"
                else:
                    marinos_score, opp_score = s2, s1
                    ha_str = "A"
                    # 対戦相手の抽出（スコアより前のチーム名）
                    before_text = text[:pos_score]
                    opp_m = re.findall(r"([^\s\d\(\)\[\]]+)", before_text)
                    # 横浜FM以外の最後の単語を相手とする
                    valid_opps = [w for w in opp_m if "J1" not in w and "節" not in w and "横浜" not in w]
                    opponent = valid_opps[-1] if valid_opps else "相手"

                # 勝敗判定
                if marinos_score > opp_score:
                    pts = 3
                    result_label = "WIN"
                elif marinos_score == opp_score:
                    pts = 1
                    result_label = "DRAW"
                else:
                    pts = 0
                    result_label = "LOSE"

                score_display = f"{marinos_score} - {opp_score}"

                match_list.append({
                    "match_num": len(match_list) + 1,
                    "section": section_str,
                    "date": date_str,
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": score_display,
                    "result": result_label,
                    "pts": pts
                })

                if len(match_list) >= TOTAL_MATCHES:
                    break

        except Exception as e:
            print(f"Error fetching month {month_str}: {e}")

        if len(match_list) >= TOTAL_MATCHES:
            break

    return match_list


def update_data():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} が見つかりません。")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_marinos_matches()

    if match_list and len(match_list) > 0:
        cumulative = []
        current = 0
        for m in match_list:
            current += m["pts"]
            m["cumulative_pts"] = current
            cumulative.append(current)

        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        played_count = len(match_list)
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({played_count}試合消化時点)"
        data["matches"] = match_list  # 試合詳細スコアのリストを追加
        print(f"更新成功: {played_count}試合消化（累計勝ち点: {current}）")
    else:
        print("有効な試合スコアが取得できなかったため、既存データを維持します。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json の更新処理が完了しました。")


if __name__ == "__main__":
    update_data()
