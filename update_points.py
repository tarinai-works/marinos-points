import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

TOTAL_MATCHES = 38
JST = timezone(timedelta(hours=9))

TEAMS = [
    {
        "id_key": "marinos",
        "name": "横浜F・マリノス",
        "team_id": "124",
        "keywords": ["横浜FM", "横浜F・マリノス", "横浜"],
        "data_file": "data.json"
    },
    {
        "id_key": "gamba",
        "name": "ガンバ大阪",
        "team_id": "128",
        "keywords": ["G大阪", "ガンバ大阪", "ガンバ"],
        "data_file": "data_gamba.json"
    },
    {
        "id_key": "kashima",
        "name": "鹿島アントラーズ",
        "team_id": "120",
        "keywords": ["鹿島", "鹿島アントラーズ"],
        "data_file": "data_kashima.json"
    },
    {
        "id_key": "urawa",
        "name": "浦和レッズ",
        "team_id": "122",
        "keywords": ["浦和", "浦和レッズ"],
        "data_file": "data_urawa.json"
    }
]

# 最新ネーミングライツ対応スタジアム辞書
STADIUM_MAP = {
    # 国立・首都圏
    "MUFG国立": "MUFGスタジアム",
    "MUFGスタジアム": "MUFGスタジアム",
    "MUFG": "MUFGスタジアム",
    "国立": "MUFGスタジアム",
    "日産ス": "日産スタジアム",
    "日産スタジアム": "日産スタジアム",
    "ニッパツ": "ニッパツ三ツ沢球技場",
    "味スタ": "味の素スタジアム",
    "味の素": "味の素スタジアム",
    "味フィ西": "味の素フィールド西が丘",
    "西が丘": "味の素フィールド西が丘",
    "埼玉": "埼玉スタジアム2002",
    "埼スタ": "埼玉スタジアム2002",
    "駒場": "浦和駒場スタジアム",
    "U等々力": "Uvanceとどろきスタジアム by Fujitsu",
    "等々力": "Uvanceとどろきスタジアム by Fujitsu",
    "三協F柏": "三協フロンテア柏スタジアム",
    "日立柏": "三協フロンテア柏スタジアム",
    "フクアリ": "フクダ電子アリーナ",
    "Gスタ": "町田GIONスタジアム",
    "町田": "町田GIONスタジアム",
    "レモンS": "レモンガススタジアム平塚",
    "平塚": "レモンガススタジアム平塚",

    # 関西
    "ハナサカ": "YANMAR HANASAKA STADIUM",
    "HANASAKA": "YANMAR HANASAKA STADIUM",
    "ヨドコウ": "YANMAR HANASAKA STADIUM",
    "長居球技場": "YANMAR HANASAKA STADIUM",
    "ヤンマー": "ヤンマースタジアム長居",
    "長居": "ヤンマースタジアム長居",
    "パナスタ": "パナソニック スタジアム 吹田",
    "吹田S": "パナソニック スタジアム 吹田",
    "ノエスタ": "ノエビアスタジアム神戸",
    "サンガS": "サンガスタジアム by KYOCERA",
    "西京極": "たけびしスタジアム京都",

    # 東海・甲信越・北陸
    "アイスタ": "IAIスタジアム日本平",
    "日本平": "IAIスタジアム日本平",
    "ヤマハ": "ヤマハスタジアム",
    "エコパ": "エコパスタジアム",
    "豊田ス": "豊田スタジアム",
    "豊スタ": "豊田スタジアム",
    "パロマ瑞穂": "パロマ瑞穂スタジアム",
    "瑞穂": "パロマ瑞穂スタジアム",
    "デンカS": "デンカビッグスワンスタジアム",
    "ビッグスワン": "デンカビッグスワンスタジアム",
    "サンアル": "サンプロ アルウィン",
    "富山": "富山県総合運動公園陸上競技場",
    "ゴーゴー": "金沢スタジアム",

    # 関東近郊・東北・北海道
    "カシマ": "県立カシマサッカースタジアム",
    "カシマスタジアム": "県立カシマサッカースタジアム",
    "Ksスタ": "ケーズデンキスタジアム水戸",
    "ケーズ": "ケーズデンキスタジアム水戸",
    "カンセキ": "カンセキスタジアムとちぎ",
    "グリスタ": "栃木県グリーンスタジアム",
    "正田スタ": "正田醤油スタジアム群馬",
    "NACK": "NACK5スタジアム大宮",
    "大和ハウス": "大和ハウス プレミストドーム",
    "札幌ド": "大和ハウス プレミストドーム",
    "厚別": "札幌厚別公園競技場",
    "ユアスタ": "ユアテックスタジアム仙台",
    "NDスタ": "NDソフトスタジアム山形",
    "ソユスタ": "ソユー entitiesスタジアム",
    "いわスタ": "いわぎんスタジアム",
    "ハワイアンズ": "ハワイアンズスタジアムいわき",

    # 中国・四国
    "Eピース": "エディオンピースウイング広島",
    "Eスタ": "エディオンピースウイング広島",
    "広域公園": "ホットスタッフフィールド広島",
    "シティライト": "シティライトスタジアム",
    "維新みらい": "維新みらいふスタジアム",
    "鳴門大塚": "鳴門・大塚スポーツパーク ポカリスエットスタジアム",
    "ポカリ": "鳴門・大塚スポーツパーク ポカリスエットスタジアム",
    "メグスタ": "四国化成MEGLIOスタジアム",
    "Pikara": "Pikaraスタジアム",
    "ニンスタ": "ニンジニアスタジアム",
    "ギケンス": "GIKENスタジアム",

    # 九州・沖縄
    "ベススタ": "ベスト電器スタジアム",
    "博多の森": "ベスト電器スタジアム",
    "駅スタ": "駅前不動産スタジアム",
    "鳥栖": "駅前不動産スタジアム",
    "ピースタ": "PEACE STADIUM Connected by SoftBank",
    "トラスタ": "トランスコスモススタジアム長崎",
    "えがおS": "えがお健康スタジアム",
    "レゾド": "レゾナックドーム大分",
    "白波スタ": "白波スタジアム",
    "ミクスタ": "ミクニワールドスタジアム北九州",
    "タピスタ": "タピック県総ひやごんスタジアム"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_match_date(date_str):
    m = re.search(r"(\d{1,2})/(\d{1,2})", date_str)
    if not m:
        return datetime(2099, 1, 1)
    month = int(m.group(1))
    day = int(m.group(2))
    year = 2026 if month >= 7 else 2027
    return datetime(year, month, day)

def fetch_match_scorers(detail_url, is_home):
    scorers = {
        "my_team": [],
        "opponent": []
    }
    if not detail_url:
        return scorers

    try:
        time.sleep(0.5)
        res = requests.get(detail_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return scorers

        soup = BeautifulSoup(res.text, "html.parser")
        home_scorers = []
        away_scorers = []

        score_board = soup.find(class_=re.compile(r"(score|matchHeader|gameSummary)", re.I))
        if score_board:
            items = score_board.find_all(class_=re.compile(r"(scorer|point|goal)", re.I))
            for item in items:
                txt = item.get_text(separator=" ", strip=True)
                if txt:
                    if "home" in " ".join(item.get("class", [])).lower():
                        home_scorers.append(txt)
                    elif "away" in " ".join(item.get("class", [])).lower():
                        away_scorers.append(txt)

        if not home_scorers and not away_scorers:
            event_rows = soup.find_all(["li", "tr"], class_=re.compile(r"(event|timeline|detail)", re.I))
            for er in event_rows:
                etxt = er.get_text(separator=" ", strip=True)
                if "ゴール" in etxt or "得点" in etxt or "GOAL" in etxt:
                    time_m = re.search(r"(\d+分|\d+\+\d+分)", etxt)
                    t_str = time_m.group(1) if time_m else ""
                    clean_text = re.sub(r"(ゴール|得点|GOAL|!|！|\d+分|\d+\+\d+分)", "", etxt).strip()
                    scorer_label = f"{clean_text} ({t_str})" if t_str else clean_text
                    
                    if "home" in " ".join(er.get("class", [])).lower():
                        home_scorers.append(scorer_label)
                    else:
                        away_scorers.append(scorer_label)

        if is_home:
            scorers["my_team"] = [s for s in home_scorers if s]
            scorers["opponent"] = [s for s in away_scorers if s]
        else:
            scorers["my_team"] = [s for s in away_scorers if s]
            scorers["opponent"] = [s for s in home_scorers if s]

    except Exception as e:
        print(f"得点者取得エラー ({detail_url}): {e}")

    return scorers

def extract_kickoff_and_stadium(row, full_text):
    kickoff = ""
    stadium = ""

    # キックオフ時間の抽出
    time_m = re.search(r"\b(\d{1,2}:\d{2})\b", full_text)
    if time_m:
        kickoff = time_m.group(1)

    # セルテキストの走査
    td_texts = []
    if hasattr(row, "find_all"):
        for td in row.find_all(["td", "span", "div"]):
            t = td.get_text(strip=True)
            if t and len(t) <= 30:
                td_texts.append(t)

    sorted_keys = sorted(STADIUM_MAP.keys(), key=lambda k: len(k), reverse=True)
    
    # 1. セル単位での辞書最長一致マッチング
    for txt in td_texts:
        for k in sorted_keys:
            if k in txt:
                stadium = STADIUM_MAP[k]
                break
        if stadium:
            break

    # 2. 行全体テキストからの辞書マッチング
    if not stadium:
        for k in sorted_keys:
            if k in full_text:
                stadium = STADIUM_MAP[k]
                break

    # 3. 辞書外スタジアムの正規表現フォールバック
    if not stadium:
        fallback_m = re.search(r"([^\s\d\(\)\[\]\:\-]+(?:スタジアム|競技場|球技場|アリーナ|ドーム|アルウィン|パーク|STADIUM))", full_text)
        if fallback_m:
            stadium = fallback_m.group(1).strip()

    return kickoff, stadium

def fetch_team_matches(team_id, keywords, existing_matches_dict):
    base_url = f"https://soccer.yahoo.co.jp/jleague/category/j1/teams/{team_id}/schedule"

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

    matches_dict = {}

    for month_str in candidate_months:
        url = f"{base_url}?gk=2&month={month_str}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
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

                if sec_num in matches_dict:
                    continue

                score_match = re.search(r"(?<!:)(?<!\d)(\d{1,2})\s*[-–]\s*(\d{1,2})(?!\d)(?!:)", text)
                if not score_match:
                    continue

                s1 = int(score_match.group(1))
                s2 = int(score_match.group(2))

                date_m = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_m.group(1) if date_m else ""

                kickoff_time, stadium_name = extract_kickoff_and_stadium(row, text)

                before_score = text[:score_match.start()]
                after_score = text[score_match.end():]

                is_home = any(kw in before_score for kw in keywords)

                if is_home:
                    my_score, opp_score = s1, s2
                    ha_str = "H"
                    clean_opp = re.sub(r"(試合終了|公式記録|詳細|チケット販売中|DAZN|NHK|BS|\.|\d+)", " ", after_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w and "カシマ" not in w and "日産" not in w and "吹田" not in w and "埼玉" not in w and "国立" not in w and "MUFG" not in w]
                    raw_opp = valid[0] if valid else "相手"
                else:
                    my_score, opp_score = s2, s1
                    ha_str = "A"
                    clean_opp = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|試合終了|LIVE)", " ", before_score)
                    opp_candidates = re.findall(r"([^\s\d\(\)\[\]\:\-]+)", clean_opp)
                    valid = [w for w in opp_candidates if not any(kw in w for kw in keywords) and "スタジアム" not in w and "競技場" not in w and "メルスタ" not in w and "ヨドコウ" not in w and "ハナサカ" not in w]
                    raw_opp = valid[-1] if valid else "相手"

                opponent = re.sub(r"(明治安田|J1|第\d+節|\d{1,2}/\d{1,2}|スタジアム|競技場|STADIUM)", "", raw_opp).strip()

                if my_score > opp_score:
                    pts, res_lbl = 3, "WIN"
                elif my_score == opp_score:
                    pts, res_lbl = 1, "DRAW"
                else:
                    pts, res_lbl = 0, "LOSE"

                detail_link = ""
                link_tag = row.find("a", href=re.compile(r"(/jleague/category/j1/|/game/)"))
                if link_tag and link_tag.get("href"):
                    href = link_tag.get("href")
                    detail_link = href if href.startswith("http") else f"https://soccer.yahoo.co.jp{href}"

                exist_item = existing_matches_dict.get(sec_num)
                if exist_item and "scorers" in exist_item and (exist_item["scorers"]["my_team"] or exist_item["scorers"]["opponent"] or (my_score == 0 and opp_score == 0)):
                    scorers_data = exist_item["scorers"]
                else:
                    scorers_data = fetch_match_scorers(detail_link, is_home)

                # 既存データが空文字の場合や未設定の場合は最新抽出値を優先
                final_kickoff = kickoff_time or (exist_item.get("kickoff", "") if exist_item else "")
                final_stadium = stadium_name or (exist_item.get("stadium", "") if exist_item else "")

                matches_dict[sec_num] = {
                    "sec_num": sec_num,
                    "section": f"第{sec_num}節",
                    "date": date_str,
                    "kickoff": final_kickoff,
                    "stadium": final_stadium,
                    "dt": parse_match_date(date_str),
                    "opponent": opponent,
                    "ha": ha_str,
                    "score": f"{my_score} - {opp_score}",
                    "result": res_lbl,
                    "pts": pts,
                    "scorers": scorers_data
                }
        except Exception as e:
            print(f"Error reading {team_id} ({month_str}): {e}")

    sorted_matches = sorted(matches_dict.values(), key=lambda x: (x["dt"], x["sec_num"]))

    match_list = []
    for idx, item in enumerate(sorted_matches):
        item_copy = dict(item)
        item_copy["match_num"] = idx + 1
        item_copy.pop("dt", None)
        item_copy.pop("sec_num", None)
        match_list.append(item_copy)

    return match_list[:TOTAL_MATCHES]

def process_team(team_cfg):
    file_path = team_cfg["data_file"]
    if not os.path.exists(file_path):
        print(f"スキップ: {file_path} が見つかりません。")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_matches = data.get("matches", [])
    existing_matches_dict = {}
    for m in existing_matches:
        sec_m = re.search(r"\d+", m.get("section", ""))
        if sec_m:
            existing_matches_dict[int(sec_m.group(0))] = m

    prev_match_count = len(existing_matches)

    match_list = fetch_team_matches(team_cfg["team_id"], team_cfg["keywords"], existing_matches_dict)

    print(f"[{team_cfg['name']}] 確定試合数: {len(match_list)}試合 (前回: {prev_match_count}試合)")

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

        # スタジアム名が補完された場合もJSONを最新保存
        data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    else:
        print(f"[{team_cfg['name']}] 取得結果が0件のため既存データを維持")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update football points data")
    parser.add_argument("--team", default="all", choices=["all", "marinos", "gamba", "kashima", "urawa"], help="Target team to update")
    args = parser.parse_args()

    for t in TEAMS:
        if args.team == "all" or args.team == t["id_key"]:
            process_team(t)
