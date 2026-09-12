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
        "team_id": "130",
        "keywords": ["G大阪", "ガンバ大阪", "ガンバ"],
        "data_file": "data_gamba.json"
    }
]

def fetch_team_matches(team_id, keywords):
    """
    スポーツナビの日程・結果ページからJ1の確定試合を抽出。
    HTMLのタグ形式（table/tr または ul/li/div）に左右されず、
    テキストブロック全体から試合ブロックを正規表現で正確にパースします。
    """
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

            # 行単位（trまたはli、divブロック）を広範囲に取得
            items = soup.find_all(["tr", "li", "section"])
            for item in items:
                text = item.get_text(separator=" ", strip=True)

                # リーグ戦の節表記がなければ除外
                if not ("J1" in text and "節" in text):
                    continue
                # カップ戦・未消化の除外
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO", "vs", "対戦データ", "試合前", "中止", "延期"]):
                    continue
                # 試合中表示の除外
                if any(w in text for w in ["前半", "後半", "速報中"]):
                    continue

                # スコア形式の抽出 (例: 1 - 1, 0 - 2, 1 - 1. 等)
                score_match = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", text)
                if not score_match:
                    continue

                s1 = int(score_match.group(1))  # ホーム得点
                s2 = int(score_match.group(2))  # アウェイ得点

                # 節番号の抽出
                sec_m = re.search(r"第?(\d+)\s*節", text)
                if not sec_m:
                    continue
                sec_num = int(sec_m.group(1))
                section_str = f"第{sec_num}節"

                # 既に同一節がリストにあればスキップ（重複防止）
                if any(m["section"] == section_str for m in match_list):
                    continue

                # 日程の抽出 (例: 9/12)
                date_m = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_m.group(1) if date_m else ""

                # スコア位置の前と後でチームを判定
                before_score = text[:score_match.start()]
                after_score = text[score_match.end():]

                # ホーム判定：スコアの前に自クラブ名があるか
                is_home = any(kw in before_score for kw in keywords)

                if is_home:
                    my_score, opp_score = s1, s2
                    ha_str = "H"
                    clean_opp = re.sub(r"(試合終了|詳細|DAZN|NHK|BS|\.|\d+)", " ", after_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w]
                    raw_opp = valid[0] if valid else "相手"
                else:
                    my_score, opp_score = s2, s1
                    ha_str = "A"
                    clean_opp = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|試合終了)", " ", before_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w]
                    raw_opp = valid[-1] if valid else "相手"

                opponent = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|スタジアム|競技場)", "", raw_opp).strip()

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

        except Exception as e:
            print(f"Error reading {team_id} ({month_str}): {e}")

    # 節順にソート
    match_list.sort(key=lambda x: int(re.search(r"\d+", x["section"]).group()))
    for idx, m in enumerate(match_list):
        m["match_num"] = idx + 1

    return match_list[:TOTAL_MATCHES]


def process_team(team_cfg):
    file_path = team_cfg["data_file"]
    if not os.path.exists(file_path):
        print(f"スキップ: {file_path} が見つかりません。")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_team_matches(team_cfg["team_id"], team_cfg["keywords"])
    current_played = len([p for p in data.get("currentPoints", []) if p is not None])

    print(f"[{team_cfg['name']}] 取得件数: {len(match_list)}試合 (既存: {current_played}試合)")

    if len(match_list) >= current_played and len(match_list) > 0:
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
        print(f"[{team_cfg['name']}] 更新対象なし、または取得件数不足のため維持")

    data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    for t in TEAMS:
        process_team(t)
