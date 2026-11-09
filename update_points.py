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

# J1全チームのマスター定義（今後チームを増やす際はここに追加するだけ）
TEAMS = [
    {
        "id_key": "marinos",
        "name": "横浜F・マリノス",
        "keywords": ["横浜FM", "横浜F・マリノス", "横浜"],
        "data_file": "data.json"
    },
    {
        "id_key": "gamba",
        "name": "ガンバ大阪",
        "keywords": ["G大阪", "ガンバ大阪", "ガンバ"],
        "data_file": "data_gamba.json"
    },
    {
        "id_key": "kashima",
        "name": "鹿島アントラーズ",
        "keywords": ["鹿島", "鹿島アントラーズ"],
        "data_file": "data_kashima.json"
    },
    {
        "id_key": "urawa",
        "name": "浦和レッズ",
        "keywords": ["浦和", "浦和レッズ"],
        "data_file": "data_urawa.json"
    }
    # 他チーム追加例:
    # {
    #     "id_key": "kawasaki",
    #     "name": "川崎フロンターレ",
    #     "keywords": ["川崎F", "川崎フロンターレ", "川崎"],
    #     "data_file": "data_kawasaki.json"
    # }
]

STADIUM_MAP = {
    "MUFG国立": "MUFGスタジアム", "MUFGスタジアム": "MUFGスタジアム", "MUFG": "MUFGスタジアム", "国立": "MUFGスタジアム",
    "日産ス": "日産スタジアム", "日産スタジアム": "日産スタジアム", "ニッパツ": "ニッパツ三ツ沢球技場",
    "味スタ": "味の素スタジアム", "味の素": "味の素スタジアム", "味フィ西": "味の素フィールド西が丘", "西が丘": "味の素フィールド西が丘",
    "埼玉": "埼玉スタジアム2002", "埼スタ": "埼玉スタジアム2002", "駒場": "浦和駒場スタジアム",
    "U等々力": "Uvanceとどろきスタジアム by Fujitsu", "等々力": "Uvanceとどろきスタジアム by Fujitsu",
    "三協F柏": "三協フロンテア柏スタジアム", "日立柏": "三協フロンテア柏スタジアム", "フクアリ": "フクダ電子アリーナ",
    "Gスタ": "町田GIONスタジアム", "町田": "町田GIONスタジアム", "レモンS": "レモンガススタジアム平塚", "平塚": "レモンガススタジアム平塚",
    "ハナサカ": "YANMAR HANASAKA STADIUM", "HANASAKA": "YANMAR HANASAKA STADIUM", "ヨドコウ": "YANMAR HANASAKA STADIUM",
    "ヤンマー": "ヤンマースタジアム長居", "パナスタ": "パナソニック スタジアム 吹田", "吹田S": "パナソニック スタジアム 吹田",
    "ノエスタ": "ノエビアスタジアム神戸", "サンガS": "サンガスタジアム by KYOCERA", "アイスタ": "IAIスタジアム日本平",
    "日本平": "IAIスタジアム日本平", "ヤマハ": "ヤマハスタジアム", "豊田ス": "豊田スタジアム", "豊スタ": "豊田スタジアム",
    "デンカS": "デンカビッグスワンスタジアム", "カシマ": "県立カシマサッカースタジアム", "大和ハウス": "大和ハウス プレミストドーム",
    "ユアスタ": "ユアテックスタジアム仙台", "Eピース": "エディオンピースウイング広島", "ピースタ": "PEACE STADIUM Connected by SoftBank",
    "ベススタ": "ベスト電器スタジアム", "駅スタ": "駅前不動産スタジアム"
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

def normalize_stadium(raw_text):
    if not raw_text:
        return ""
    sorted_keys = sorted(STADIUM_MAP.keys(), key=lambda k: len(k), reverse=True)
    for k in sorted_keys:
        if k in raw_text:
            return STADIUM_MAP[k]
    m = re.search(r"([^\s\d\(\)\[\]\:\-]+(?:スタジアム|競技場|球技場|アリーナ|ドーム|アルウィン|パーク|STADIUM))", raw_text)
    return m.group(1).strip() if m else raw_text.strip()

def fetch_match_scorers(detail_url):
    """1つの試合詳細ページからホーム・アウェイ双方の得点者を一度に取得"""
    scorers = {"home": [], "away": []}
    if not detail_url:
        return scorers

    try:
        time.sleep(0.4)
        res = requests.get(detail_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return scorers

        soup = BeautifulSoup(res.text, "html.parser")
        score_board = soup.find(class_=re.compile(r"(score|matchHeader|gameSummary)", re.I))
        if score_board:
            items = score_board.find_all(class_=re.compile(r"(scorer|point|goal)", re.I))
            for item in items:
                txt = item.get_text(separator=" ", strip=True)
                if txt:
                    cls_str = " ".join(item.get("class", [])).lower()
                    if "home" in cls_str:
                        scorers["home"].append(txt)
                    elif "away" in cls_str:
                        scorers["away"].append(txt)

        if not scorers["home"] and not scorers["away"]:
            event_rows = soup.find_all(["li", "tr"], class_=re.compile(r"(event|timeline|detail)", re.I))
            for er in event_rows:
                etxt = er.get_text(separator=" ", strip=True)
                if any(w in etxt for w in ["ゴール", "得点", "GOAL"]):
                    time_m = re.search(r"(\d+分|\d+\+\d+分)", etxt)
                    t_str = time_m.group(1) if time_m else ""
                    clean_text = re.sub(r"(ゴール|得点|GOAL|!|！|\d+分|\d+\+\d+分)", "", etxt).strip()
                    label = f"{clean_text} ({t_str})" if t_str else clean_text
                    if "home" in " ".join(er.get("class", [])).lower():
                        scorers["home"].append(label)
                    else:
                        scorers["away"].append(label)
    except Exception as e:
        print(f"得点者取得エラー ({detail_url}): {e}")

    return scorers

def find_team_config(team_name):
    for t in TEAMS:
        if any(kw in team_name for kw in t["keywords"]):
            return t
    return None

def fetch_all_matches_from_schedule():
    """J1の節一覧ページ（第1節〜第38節）を巡回し、終了した試合を全チーム分まとめて抽出"""
    all_team_matches = {t["id_key"]: {} for t in TEAMS}
    
    # 既存データのキャッシュをロード（詳細ページの無駄アクセス防止）
    cached_scorers = {}
    for t in TEAMS:
        if os.path.exists(t["data_file"]):
            try:
                with open(t["data_file"], "r", encoding="utf-8") as f:
                    d = json.load(f)
                    for m in d.get("matches", []):
                        sec_num = int(re.search(r"\d+", m.get("section", "0")).group(0))
                        cached_scorers[(t["id_key"], sec_num)] = m.get("scorers", {})
            except Exception:
                pass

    print("J1 日程・結果一覧の走査を開始します...")

    # 第1節〜第38節をチェック（未来の試合ばかりになったら早期終了）
    consecutive_future_sections = 0

    for sec in range(1, TOTAL_MATCHES + 1):
        url = f"https://soccer.yahoo.co.jp/jleague/category/j1/schedule/{sec}/1"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.find_all("tr")
            if not rows:
                rows = soup.find_all("li")

            section_has_finished = False

            for row in rows:
                text = row.get_text(separator=" ", strip=True)
                if "試合前" in text or "中止" in text or "延期" in text or "速報中" in text:
                    continue

                score_match = re.search(r"(?<!:)(?<!\d)(\d{1,2})\s*[-–]\s*(\d{1,2})(?!\d)(?!:)", text)
                if not score_match:
                    continue

                home_score = int(score_match.group(1))
                away_score = int(score_match.group(2))
                section_has_finished = True

                # 日付・時間・スタジアム
                date_m = re.search(r"(\d{1,2}/\d{1,2})", text)
                date_str = date_m.group(1) if date_m else ""

                time_m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
                kickoff = time_m.group(1) if time_m else ""

                # チーム名抽出
                before_score = text[:score_match.start()]
                after_score = text[score_match.end():]

                home_team_cfg = None
                away_team_cfg = None
                for t in TEAMS:
                    if any(kw in before_score for kw in t["keywords"]):
                        home_team_cfg = t
                    if any(kw in after_score for kw in t["keywords"]):
                        away_team_cfg = t

                # 対象外チーム同士の対戦ならスキップ
                if not home_team_cfg and not away_team_cfg:
                    continue

                # スタジアム名（一覧ページには末尾や特定セルに記載がある）
                stadium = ""
                for td in row.find_all(["td", "span", "div"]):
                    t_str = td.get_text(strip=True)
                    if any(k in t_str for k in STADIUM_MAP.keys()):
                        stadium = normalize_stadium(t_str)
                        break
                if not stadium:
                    stadium = normalize_stadium(text)

                # 詳細リンク（得点者用）
                link_tag = row.find("a", href=re.compile(r"(/jleague/category/j1/|/game/)"))
                detail_url = ""
                if link_tag and link_tag.get("href"):
                    href = link_tag.get("href")
                    detail_url = href if href.startswith("http") else f"https://soccer.yahoo.co.jp{href}"

                # 得点者キャッシュチェック
                need_fetch = True
                home_scorers_data = None
                away_scorers_data = None

                if home_team_cfg and (home_team_cfg["id_key"], sec) in cached_scorers:
                    c = cached_scorers[(home_team_cfg["id_key"], sec)]
                    if c.get("my_team") or c.get("opponent") or (home_score == 0 and away_score == 0):
                        home_scorers_data = c
                        need_fetch = False

                if away_team_cfg and (away_team_cfg["id_key"], sec) in cached_scorers:
                    c = cached_scorers[(away_team_cfg["id_key"], sec)]
                    if c.get("my_team") or c.get("opponent") or (home_score == 0 and away_score == 0):
                        away_scorers_data = c
                        if not home_team_cfg:
                            need_fetch = False

                if need_fetch:
                    sc = fetch_match_scorers(detail_url)
                    home_scorers_data = {"my_team": sc["home"], "opponent": sc["away"]}
                    away_scorers_data = {"my_team": sc["away"], "opponent": sc["home"]}

                # ホームチーム側のデータを記録
                if home_team_cfg:
                    pts = 3 if home_score > away_score else (1 if home_score == away_score else 0)
                    res_lbl = "WIN" if pts == 3 else ("DRAW" if pts == 1 else "LOSE")
                    opp_name = away_team_cfg["name"] if away_team_cfg else "相手"
                    all_team_matches[home_team_cfg["id_key"]][sec] = {
                        "sec_num": sec,
                        "section": f"第{sec}節",
                        "date": date_str,
                        "kickoff": kickoff,
                        "stadium": stadium,
                        "dt": parse_match_date(date_str),
                        "opponent": opp_name,
                        "ha": "H",
                        "score": f"{home_score} - {away_score}",
                        "result": res_lbl,
                        "pts": pts,
                        "scorers": home_scorers_data
                    }

                # アウェイチーム側のデータを記録
                if away_team_cfg:
                    pts = 3 if away_score > home_score else (1 if away_score == home_score else 0)
                    res_lbl = "WIN" if pts == 3 else ("DRAW" if pts == 1 else "LOSE")
                    opp_name = home_team_cfg["name"] if home_team_cfg else "相手"
                    all_team_matches[away_team_cfg["id_key"]][sec] = {
                        "sec_num": sec,
                        "section": f"第{sec}節",
                        "date": date_str,
                        "kickoff": kickoff,
                        "stadium": stadium,
                        "dt": parse_match_date(date_str),
                        "opponent": opp_name,
                        "ha": "A",
                        "score": f"{away_score} - {home_score}",
                        "result": res_lbl,
                        "pts": pts,
                        "scorers": away_scorers_data
                    }

            if section_has_finished:
                consecutive_future_sections = 0
            else:
                consecutive_future_sections += 1
                if consecutive_future_sections >= 3:
                    # 終了試合のない節が3連続したらそれ以降の節は未消化とみなして中断（高速化）
                    break

            time.sleep(0.3)
        except Exception as e:
            print(f"第{sec}節の取得エラー: {e}")

    return all_team_matches

def save_team_data(team_cfg, matches_dict):
    file_path = team_cfg["data_file"]
    
    # ファイルがなければ新規作成
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "updated_at": "",
            "currentSeasonLabel": "",
            "currentPoints": [],
            "matches": []
        }

    sorted_matches = sorted(matches_dict.values(), key=lambda x: (x["dt"], x["sec_num"]))
    match_list = []
    cur = 0
    cumulative = []

    for idx, item in enumerate(sorted_matches):
        item_copy = dict(item)
        item_copy["match_num"] = idx + 1
        item_copy.pop("dt", None)
        item_copy.pop("sec_num", None)
        cur += item_copy["pts"]
        item_copy["cumulative_pts"] = cur
        cumulative.append(cur)
        match_list.append(item_copy)

    if len(match_list) > 0:
        while len(cumulative) < TOTAL_MATCHES:
            cumulative.append(None)

        data["currentPoints"] = cumulative
        data["currentSeasonLabel"] = f"2026 - 27 シーズン ({len(match_list)}試合消化時点)"
        data["matches"] = match_list
        data["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        print(f"[{team_cfg['name']}] 正常更新: 消化試合数={len(match_list)}, 累計勝ち点={cur}")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        print(f"[{team_cfg['name']}] 試合結果なし")

if __name__ == "__main__":
    all_matches = fetch_all_matches_from_schedule()
    for t in TEAMS:
        if t["id_key"] in all_matches:
            save_team_data(t, all_matches[t["id_key"]])
