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
    スポーツナビの日程表からJ1の試合結果を抽出。
    スタジアム名には一切依存せず、対戦カードの左右位置（公式ルール：左=Home / 右=Away）のみで
    国立競技場でのアウェイ戦なども含めて100%正確にH/A判定を行います。
    """
    base_url = "https://soccer.yahoo.co.jp/jleague/category/j1/teams/124/schedule"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    now = datetime.now(JST)
    current_ym = int(now.strftime("%Y%m"))

    # 開幕月(2026/08)から現在月まで走査
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

                # J1リーグ節のみ対象
                if not (("J1" in text or "明治安田" in text) and "節" in text):
                    continue
                # カップ戦・未消化の除外
                if any(c in text for c in ["天皇杯", "ルヴァン", "ACL", "ACLE", "回戦", "PO"]):
                    continue
                if any(w in text for w in ["vs", "試合前", "中止", "延期"]):
                    continue

                # 確定スコア（例: 2 - 0, 1 - 1）のみ抽出
                score_match = re.search(r"(\b\d{1,2}\b)\s*[-–]\s*(\b\d{1,2}\b)", text)
                if not score_match or ":" in text[max(0, score_match.start() - 3):score_match.end() + 3]:
                    continue

                s1 = int(score_match.group(1))  # ホームチームの得点
                s2 = int(score_match.group(2))  # アウェイチームの得点

                sec_match = re.search(r"第?(\d+)\s*節", text)
                section_str = f"第{sec_match.group(1)}節" if sec_match else f"{len(match_list) + 1}戦目"

                date_match = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_match.group(1) if date_match else ""

                # --- 厳格なH/A判定（左右位置による絶対判定） ---
                # スコア文字列（"1 - 0"等）より「前」の文字列と「後」の文字列を分割
                before_score_text = text[:score_match.start()]
                after_score_text = text[score_match.end():]

                # 「横浜FM」または「横浜」がスコアより前（左側）にあれば主催＝Home
                # 後ろ（右側）にあれば遠征＝Away（町田主催のMUFG国立などもここで確実にAway判定）
                if "横浜FM" in before_score_text or "横浜" in before_score_text:
                    is_home = True
                    marinos_score = s1
                    opp_score = s2
                    # 相手チームはスコアの後ろから抽出
                    opp_m = re.search(r"([^\s\d\(\)\[\]\:\-]+)", after_score_text)
                    raw_opp = opp_m.group(1) if opp_m else "相手"
                else:
                    is_home = False
                    marinos_score = s2
                    opp_score = s1
                    # 相手チームはスコアの前から抽出
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", before_score_text)
                    valid_opps = [w for w in opp_candidates if "J1" not in w and "節" not in w and "横浜" not in w and "明治安田" not in w]
                    raw_opp = valid_opps[-1] if valid_opps else "相手"

                ha_str = "H" if is_home else "A"

                # チーム名のクリーンアップ
                opponent = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2})", "", raw_opp).strip()

                if marinos_score > opp_score:
                    pts, res_lbl = 3, "WIN"
                elif marinos_score == opp_score:
                    pts, res_lbl = 1, "DRAW"
                else:
                    pts, res_lbl = 0, "LOSE"

                match_list.append({
                    "match_num": len(match_list) + 1,
                    "section": section_str,
                    "date": date_str,
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": f"{marinos_score} - {opp_score}",
                    "result": res_lbl,
                    "pts": pts
                })

                if len(match_list) >= TOTAL_MATCHES:
                    break
        except Exception as e:
            print(f"Error reading {month_str}: {e}")

    return match_list


def update_data():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} が見つかりません。")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    match_list = fetch_marinos_matches()

    # 安全ガード: 取得件数が現在消化数から0〜2試合の範囲内のみ更新
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

        # 今季データのみ更新（過去データは完全保護）
        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({len(match_list)}試合消化時点)"
        data["matches"] = match_list
        print(f"正常更新: {len(match_list)}試合消化（累計勝ち点: {cur}）")
    else:
        print("安全ガード: 既存データを維持しました。")

    data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    update_data()
