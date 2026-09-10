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
    今シーズンの開幕（8月）から「現在の年月」までの日程のみを巡回し、
    終了済みのJ1リーグ戦スコアのみを正確に抽出します。
    """
    base_url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    now = datetime.now(JST)
    current_year_month = int(now.strftime("%Y%m"))

    # 開幕（2026年8月）から現在月までの月リストのみ生成（未来の月はアクセスしない）
    candidate_months = []
    # 2026年8月〜12月
    for m in range(8, 13):
        ym = 2026 * 100 + m
        if ym <= current_year_month:
            candidate_months.append(str(ym))
    # 2027年1月〜6月
    for m in range(1, 7):
        ym = 2027 * 100 + m
        if ym <= current_year_month:
            candidate_months.append(str(ym))

    match_list = []

    for month_str in candidate_months:
        url = f"{base_url}?gk=2&month={month_str}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")

            rows = soup.find_all("tr")
            for row in rows:
                text = row.get_text()

                # J1リーグ節のみ対象
                if not (("J1" in text or "明治安田" in text) and "節" in text):
                    continue
                # カップ戦・未消化の除外
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"]):
                    continue
                if "vs" in text or "試合前" in text or "中止" in text or "延期" in text:
                    continue

                # 厳格なスコア形式のみ抽出 (1桁〜2桁の得点 - 得点)
                score_match = re.search(r"(\b\d{1,2}\b)\s*[-–]\s*(\b\d{1,2}\b)", text)
                if not score_match:
                    continue

                # 時刻表示（例: 19:00 等）の誤検知を防止
                if ":" in text[max(0, score_match.start() - 3):score_match.end() + 3]:
                    continue

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                # 第○節
                sec_match = re.search(r"第?(\d+)\s*節", text)
                section_str = f"第{sec_match.group(1)}節" if sec_match else f"{len(match_list) + 1}戦目"

                # 日付
                date_match = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_match.group(1) if date_match else ""

                # ホーム / アウェイ判定
                pos_yfm = text.find("横浜FM")
                pos_score = score_match.start()
                is_home = (pos_yfm != -1 and pos_yfm < pos_score)

                if is_home:
                    marinos_score, opp_score = s1, s2
                    ha_str = "H"
                    after_text = text[score_match.end():]
                    opp_m = re.search(r"([^\s\d\(\)\[\]\:\-]+)", after_text)
                    opponent = opp_m.group(1) if opp_m else "相手"
                else:
                    marinos_score, opp_score = s2, s1
                    ha_str = "A"
                    before_text = text[:pos_score]
                    opp_m = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", before_text)
                    valid_opps = [w for w in opp_m if "J1" not in w and "節" not in w and "横浜" not in w]
                    opponent = valid_opps[-1] if valid_opps else "相手"

                if marinos_score > opp_score:
                    pts = 3
                    result_label = "WIN"
                elif marinos_score == opp_score:
                    pts = 1
                    result_label = "DRAW"
                else:
                    pts = 0
                    result_label = "LOSE"

                match_list.append({
                    "match_num": len(match_list) + 1,
                    "section": section_str,
                    "date": date_str,
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": f"{marinos_score} - {opp_score}",
                    "result": result_label,
                    "pts": pts
                })

                if len(match_list) >= TOTAL_MATCHES:
                    break

        except Exception as e:
            print(f"Error fetching month {month_str}: {e}")

    return match_list


def update_data():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} が見つかりません。")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_marinos_matches()

    # 安全ガード: 取得件数が異常（0件、または急に20試合以上増えるなど）な場合は上書きしない
    current_played = len([p for p in data.get("currentPoints", []) if p is not None])
    
    if match_list and len(match_list) >= current_played and len(match_list) <= current_played + 2:
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
        data["matches"] = match_list
        print(f"安全ガード通過: {played_count}試合消化（勝ち点: {current}）を正常更新")
    else:
        print(f"安全ガード発動: 取得件数が異常値（{len(match_list) if match_list else 0}件）のため上書きを防止しました。")

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    data["updated_at"] = now_str

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json の整合性チェック・書き込みが完了しました。")


if __name__ == "__main__":
    update_data()
