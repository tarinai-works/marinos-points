import json
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

TOTAL_MATCHES = 38
JST = timezone(timedelta(hours=9))

# 複数クラブの設定一覧
TEAMS = [
    {
        "name": "横浜F・マリノス",
        "team_id": "124",
        "search_name": ["横浜FM", "横浜"],
        "data_file": "data.json"
    },
    {
        "name": "ガンバ大阪",
        "team_id": "128",
        "search_name": ["G大阪", "ガンバ"],
        "data_file": "data_gamba.json"
    }
]

def fetch_team_matches(team_id, search_names):
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

    match_list = []

    for month_str in candidate_months:
        url = f"{base_url}?gk=2&month={month_str}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")

            for row in soup.find_all("tr"):
                text = row.get_text()

                if not (("J1" in text or "明治安田" in text) and "節" in text):
                    continue
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"]):
                    continue
                if any(w in text for w in ["vs", "試合前", "中止", "延期"]):
                    continue

                score_match = re.search(r"(\b\d{1,2}\b)\s*[-–]\s*(\b\d{1,2}\b)", text)
                if not score_match or ":" in text[max(0, score_match.start() - 3):score_match.end() + 3]:
                    continue

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                sec_match = re.search(r"第?(\d+)\s*節", text)
                section_str = f"第{sec_match.group(1)}節" if sec_match else f"{len(match_list) + 1}戦目"

                date_match = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_match.group(1) if date_match else ""

                before_score = text[:score_match.start()]
                after_score = text[score_match.end():]

                # 自クラブがスコアの前にあればHome、後ろにあればAway
                is_home = any(name in before_score for name in search_names)

                if is_home:
                    my_score, opp_score = s1, s2
                    ha_str = "H"
                    opp_m = re.search(r"([^\s\d\(\)\[\]\:\-]+)", after_score)
                    raw_opp = opp_m.group(1) if opp_m else "相手"
                else:
                    my_score, opp_score = s2, s1
                    ha_str = "A"
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", before_score)
                    valid_opps = [w for w in opp_candidates if "J1" not in w and "節" not in w and not any(n in w for n in search_names) and "明治安田" not in w]
                    raw_opp = valid_opps[-1] if valid_opps else "相手"

                opponent = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2})", "", raw_opp).strip()

                if my_score > opp_score:
                    pts, res_lbl = 3, "WIN"
                elif my_score == opp_score:
                    pts, res_lbl = 1, "DRAW"
                else:
                    pts, res_lbl = 0, "LOSE"

                match_list.append({
                    "match_num": len(match_list) + 1,
                    "section": section_str,
                    "date": date_str,
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": f"{my_score} - {opp_score}",
                    "result": res_lbl,
                    "pts": pts
                })

                if len(match_list) >= TOTAL_MATCHES:
                    break
        except Exception as e:
            print(f"Error reading {team_id} ({month_str}): {e}")

    return match_list


def process_team(team_cfg):
    file_path = team_cfg["data_file"]
    if not os.path.exists(file_path):
        print(f"スキップ: {file_path} が見つかりません。")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_team_matches(team_cfg["team_id"], team_cfg["search_name"])
    current_played = len([p for p in data.get("currentPoints", []) if p is not None])

    if match_list and len(match_list) >= current_played and len(match_list) <= current_played + 2:
        cumulative = []
        cur = 0
        for m in match_list:
            cur += m["pts"]
            m["cumulative_pts"] = cur
            cumulative.append(cur)

        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        # 今季データのみ更新（過去データは完全温存）
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({len(match_list)}試合消化時点)"
        data["matches"] = match_list
        print(f"[{team_cfg['name']}] 正常更新: {len(match_list)}試合消化（勝ち点: {cur}）")
    else:
        print(f"[{team_cfg['name']}] 安全ガード: 既存データを維持しました。")

    data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    for t in TEAMS:
        process_team(t)
