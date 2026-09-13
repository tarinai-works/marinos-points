import json
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

TOTAL_MATCHES = 38
JST = timezone(timedelta(hours=9))

TEAMS = [
    {
        "name": "横浜F・マリノス",
        "team_id": "124",
        "keywords": ["横浜FM", "横浜F・マリノス", "横浜"],
        "data_file": "data.json"
    },
    {
        "name": "ガンバ大阪",
        "team_id": "128",
        "keywords": ["G大阪", "ガンバ大阪", "ガンバ"],
        "data_file": "data_gamba.json"
    }
]

def parse_match_date(date_str):
    """
    '8/7' や '2/14' などの日付文字列を秋春制（2026-27）の完全な datetime オブジェクトに変換する
    """
    m = re.search(r"(\d{1,2})/(\d{1,2})", date_str)
    if not m:
        return datetime(2099, 1, 1)
    month = int(m.group(1))
    day = int(m.group(2))
    # 7月〜12月は2026年、1月〜6月は2027年として扱う
    year = 2026 if month >= 7 else 2027
    return datetime(year, month, day)

def fetch_team_matches(team_id, keywords):
    base_url = f"https://soccer.yahoo.co.jp/jleague/category/j1/teams/{team_id}/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    now = datetime.now(JST)
    current_ym = int(now.strftime("%Y%m"))

    candidate_months = []
    for m in range(8, 13):
        ym = 2026 * 100 + m
        if ym <= current_ym:
            candidate_months.append(str(ym))
    for m in range(1, 7):
        ym = 2027 * 100 + m
        if ym <= current_ym:
            candidate_months.append(str(ym))

    # 節番号 (int) をキーにして重複を排除する辞書
    matches_dict = {}

    for month_str in candidate_months:
        url = f"{base_url}?gk=2&month={month_str}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")

            rows = soup.find_all("tr")
            if not rows:
                rows = soup.find_all("li")

            for row in rows:
                text = row.get_text(separator=" ", strip=True)

                if not ("J1" in text and "節" in text):
                    continue
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO", "vs", "対戦データ", "試合前", "中止", "延期", "前半", "後半", "速報中"]):
                    continue

                sec_m = re.search(r"第?(\d+)\s*節", text)
                if not sec_m:
                    continue
                sec_num = int(sec_m.group(1))

                # すでに取得済みの節はスキップ（多重カウント防止）
                if sec_num in matches_dict:
                    continue

                score_match = re.search(r"(?<!:)(?<!\d)(\d{1,2})\s*[-–]\s*(\d{1,2})(?!\d)(?!:)", text)
                if not score_match:
                    continue

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                date_m = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_m.group(1) if date_m else ""

                before_score = text[:score_match.start()]
                after_score = text[score_match.end():]

                is_home = any(kw in before_score for kw in keywords)

                if is_home:
                    my_score, opp_score = s1, s2
                    ha_str = "H"
                    clean_opp = re.sub(r"(試合終了|公式記録|詳細|チケット販売中|DAZN|NHK|BS|\.|\d+)", " ", after_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w and "日産" not in w and "吹田" not in w]
                    raw_opp = valid[0] if valid else "相手"
                else:
                    my_score, opp_score = s2, s1
                    ha_str = "A"
                    clean_opp = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|試合終了|LIVE)", " ", before_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w and "MUFG" not in w]
                    raw_opp = valid[-1] if valid else "相手"

                opponent = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|スタジアム|競技場)", "", raw_opp).strip()

                if my_score > opp_score:
                    pts, res_lbl = 3, "WIN"
                elif my_score == opp_score:
                    pts, res_lbl = 1, "DRAW"
                else:
                    pts, res_lbl = 0, "LOSE"

                matches_dict[sec_num] = {
                    "sec_num": sec_num,
                    "section": f"第{sec_num}節",
                    "date": date_str,
                    "dt": parse_match_date(date_str),
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": f"{my_score} - {opp_score}",
                    "result": res_lbl,
                    "pts": pts
                }
        except Exception as e:
            print(f"Error reading {team_id} ({month_str}): {e}")

    # ★ここを変更：節番号ではなく「実際の日程順（時系列）」でソート
    sorted_matches = sorted(matches_dict.values(), key=lambda x: (x["dt"], x["sec_num"]))

    match_list = []
    for idx, item in enumerate(sorted_matches):
        item_copy = dict(item)
        item_copy["match_num"] = idx + 1
        item_copy.pop("dt", None)       # JSON出力用に一時的なdatetimeを削除
        item_copy.pop("sec_num", None)  # JSON出力用に一時的な数値を削除
        match_list.append(item_copy)

    return match_list[:TOTAL_MATCHES]


def process_team(team_cfg):
    file_path = team_cfg["data_file"]
    if not os.path.exists(file_path):
        print(f"スキップ: {file_path} が見つかりません。")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_team_matches(team_cfg["team_id"], team_cfg["keywords"])

    print(f"[{team_cfg['name']}] 確定試合数: {len(match_list)}試合")

    if len(match_list) > 0:
        cumulative = []
        cur = 0
        for m in match_list:
            cur += m["pts"]
            m["cumulative_pts"] = cur
            cumulative.append(cur)

        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({len(match_list)}試合消化時点)"
        data["matches"] = match_list
        print(f"[{team_cfg['name']}] 正常更新: 累計勝ち点 {cur}")
    else:
        print(f"[{team_cfg['name']}] 取得結果が0件のため既存データを維持")

    data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    for t in TEAMS:
        process_team(t)
