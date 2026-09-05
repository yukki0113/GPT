#!/usr/bin/env python3
"""RaceNote JRDB converter v0.2.

PACI ZIP (BAC/KYI/CHA/CYB/ZED/ZKB) を直接読み込み、GPT向けの
1レース1JSON、manifest、validation report を出力する。
固定長の位置指定は常に raw bytes に対して行い、その後 CP932 で復号する。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jrdb_raw import Parser as CommonParser
from jrdb_raw import read_fixed_records as common_read_fixed_records

SCHEMA_VERSION = "0.2"
RECORD_LENGTHS = {"BAC": 184, "KYI": 1024, "CHA": 64, "CYB": 96, "ZED": 376, "ZKB": 304}
REQUIRED_PREFIXES = tuple(RECORD_LENGTHS)


def _map(**kwargs: str) -> dict[str, str]:
    return {key.replace("_", ""): value for key, value in kwargs.items()}


VENUES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
    "21": "旭川", "22": "札幌", "23": "門別", "24": "函館", "25": "盛岡",
    "26": "水沢", "27": "上山", "28": "新潟", "29": "三条", "30": "足利",
    "31": "宇都", "32": "高崎", "33": "浦和", "34": "船橋", "35": "大井",
    "36": "川崎", "37": "金沢", "38": "笠松", "39": "名古", "40": "中京",
    "41": "園田", "42": "姫路", "43": "益田", "44": "福山", "45": "高知",
    "46": "佐賀", "47": "荒尾", "48": "中津", "61": "英国", "62": "愛国",
    "63": "仏国", "64": "伊国", "65": "独国", "66": "米国", "67": "加国",
    "68": "UAE", "69": "豪州", "70": "新国", "71": "香港", "72": "チリ",
    "73": "星国", "74": "典国", "75": "マカ", "76": "墺国", "77": "土国",
    "78": "華国", "79": "韓国",
}
RUNNING_STYLE = {"1": "逃げ", "2": "先行", "3": "差し", "4": "追込", "5": "好位差し", "6": "自在"}
DISTANCE_FIT = {"1": "短距離", "2": "中距離", "3": "長距離", "5": "マイル", "6": "万能"}
THREE_LEVEL = {"1": "◎", "2": "○", "3": "△"}
IMPROVEMENT = {"1": "AA", "2": "A", "3": "B", "4": "C", "5": "?"}
TRAINING_ARROW = {"1": "デキ抜群", "2": "上昇", "3": "平行線", "4": "やや下降気味", "5": "デキ落ち"}
STABLE_EVAL = {"1": "超強気", "2": "強気", "3": "現状維持", "4": "弱気"}
HOOF = {"01": "大ベタ", "02": "中ベタ", "03": "小ベタ", "04": "細ベタ", "05": "大立", "06": "中立", "07": "小立", "08": "細立", "09": "大標準", "10": "中標準", "11": "小標準", "12": "細標準", "17": "大標起", "18": "中標起", "19": "小標起", "20": "細標起", "21": "大標ベ", "22": "中標ベ", "23": "小標ベ"}
JRDB_CLASS = {
    "01": "芝G1", "02": "芝G2", "03": "芝G3", "04": "芝オープンA", "05": "芝オープンB", "06": "芝オープンC",
    "07": "芝3勝A", "08": "芝3勝B", "09": "芝3勝C", "10": "芝2勝A", "11": "芝2勝B", "12": "芝2勝C",
    "13": "芝1勝A", "14": "芝1勝B", "15": "芝1勝C", "16": "芝未勝利A", "17": "芝未勝利B", "18": "芝未勝利C",
    "21": "ダートG1", "22": "ダートG2", "23": "ダートG3", "24": "ダートオープンA", "25": "ダートオープンB", "26": "ダートオープンC",
    "27": "ダート3勝A", "28": "ダート3勝B", "29": "ダート3勝C", "30": "ダート2勝A", "31": "ダート2勝B", "32": "ダート2勝C",
    "33": "ダート1勝A", "34": "ダート1勝B", "35": "ダート1勝C", "36": "ダート未勝利A", "37": "ダート未勝利B", "38": "ダート未勝利C",
    "51": "障害G1", "52": "障害G2", "53": "障害G3", "54": "障害オープンA", "55": "障害オープンB", "56": "障害オープンC",
    "57": "障害1勝A", "58": "障害1勝B", "59": "障害1勝C", "60": "障害未勝利A", "61": "障害未勝利B", "62": "障害未勝利C",
}
SURFACE = {"1": "芝", "2": "ダート", "3": "障害"}
TURN = {"1": "右", "2": "左", "3": "直線", "9": "その他"}
COURSE_LAYOUT = {"1": "通常（内）", "2": "外", "3": "直線ダート", "9": "その他"}
TRACK_CONDITION = {"10": "良", "11": "速良", "12": "遅良", "20": "稍重", "21": "速稍重", "22": "遅稍重", "30": "重", "31": "速重", "32": "遅重", "40": "不良", "41": "速不良", "42": "遅不良", "1": "良", "2": "稍重", "3": "重", "4": "不良"}
RACE_TYPE = {"11": "2歳", "12": "3歳", "13": "3歳以上", "14": "4歳以上", "20": "障害", "99": "その他"}
RACE_CLASS = {"04": "1勝クラス", "05": "1勝クラス", "08": "2勝クラス", "09": "2勝クラス", "10": "2勝クラス", "15": "3勝クラス", "16": "3勝クラス", "A1": "新馬", "A2": "未出走", "A3": "未勝利", "OP": "オープン"}
WEIGHT_RULE = {"1": "ハンデ", "2": "別定", "3": "馬齢", "4": "定量"}
GRADE = {"1": "G1", "2": "G2", "3": "G3", "4": "重賞", "5": "特別", "6": "L"}
MARK = {"0": None, "1": "◎", "2": "○", "3": "▲", "4": "注", "5": "△", "6": "△", "7": None, "9": "☆"}
ABNORMAL = {"0": "異常なし", "1": "取消", "2": "除外", "3": "中止", "4": "失格", "5": "降着", "6": "再騎乗"}
LANE = {"1": "最内", "2": "内", "3": "中", "4": "外", "5": "大外"}
BODY_CONDITION = {"1": "太い", "2": "余裕", "3": "良い", "4": "普通", "5": "細い", "6": "張り", "7": "緩い"}
WEATHER = {"1": "晴", "2": "曇", "3": "小雨", "4": "雨", "5": "小雪", "6": "雪"}
REST_REASON = {"01": "放牧", "02": "放牧（故障・骨折等）", "03": "放牧（不安・ソエ等）", "04": "放牧（病気）", "05": "放牧（再審査）", "06": "放牧（出走停止）", "07": "放牧（手術）", "11": "調整", "12": "調整（故障・骨折等）", "13": "調整（不安・ソエ等）", "14": "調整（病気）", "15": "調整（再審査）", "16": "調整（出走停止）", "21": "その他"}
TRAINING_COURSE = {"01": "美浦坂路", "02": "南W", "03": "南D", "04": "南芝", "08": "美浦障害芝", "09": "美浦プール", "10": "南ポリトラック", "11": "栗東坂路", "12": "CW", "13": "DW", "14": "栗B", "15": "栗E", "16": "栗芝", "17": "栗東ポリトラック", "18": "栗東障害", "19": "栗東プール", "21": "札幌ダ", "22": "札幌芝", "23": "函館ダ", "24": "函館芝", "25": "函館W", "26": "福島芝", "27": "福島ダ", "28": "新潟芝", "29": "新潟ダ", "30": "東京芝", "31": "東京ダ", "32": "中山芝", "33": "中山ダ", "34": "中京芝", "35": "中京ダ", "36": "京都芝", "37": "京都ダ", "38": "阪神芝", "39": "阪神ダ", "40": "小倉芝", "41": "小倉ダ", "42": "福島障害", "43": "新潟障害", "44": "東京障害", "45": "中山障害", "46": "中京障害", "47": "京都障害", "48": "阪神障害", "49": "小倉障害", "50": "地方競馬", "61": "障害試験", "68": "美障害ダ", "81": "美ゲート", "82": "栗ゲート", "88": "牧場", "93": "白井ダ", "A1": "連闘", "B1": "その他"}
TRAINING_STATE = {"01": "流す", "02": "余力あり", "03": "終い抑え", "04": "一杯", "05": "バテる", "06": "伸びる", "07": "テンのみ", "08": "鋭く伸び", "09": "強目", "10": "終い重点", "11": "8分追い", "12": "追って伸", "13": "向正面", "14": "ゲート", "15": "障害練習", "16": "中間軽め", "17": "キリ", "21": "引っ張る", "22": "掛かる", "23": "掛りバテ", "24": "テン掛る", "25": "掛り一杯", "26": "ササル", "27": "ヨレル", "28": "バカつく", "29": "手間取る", "99": "その他"}
WORKOUT_STRENGTH = {"1": "一杯", "2": "強目", "3": "馬なり"}
RIDER_TYPE = {"1": "助手", "2": "調教師", "3": "本番騎手", "4": "調教騎手", "5": "見習"}
PAIR_RESULT = {"1": "先着", "2": "同入", "3": "遅れ"}
BLINKER = {"1": "初装着", "2": "再装着", "3": "ブリンカー"}
PACE = {"H": "ハイ", "M": "平均", "S": "スロー"}
PACE_SYMBOL = {"0": "その他", "1": "逃げ馬", "2": "最速上がり", "3": "上位上がり", "4": "要確認"}

# PACI260815 で頻出する代表コード。辞書に無いコードは推測せず warning へ記録する。
TOKKI = {"033": "口向き悪い", "034": "放馬", "035": "落鉄", "037": "揉まれ弱い", "038": "芝向き", "039": "ダート向き", "040": "心房細動", "043": "鼻出血", "044": "ソエ", "051": "根性有り", "053": "頭高い（レース中）", "055": "外枠×", "056": "内枠○", "057": "外枠○", "058": "スタート良い", "059": "スタート悪い", "060": "内もたれ", "061": "外もたれ", "062": "ハナ条件", "071": "芝軽い○", "072": "芝軽い×", "078": "ズブイ", "079": "シブトイ", "080": "折り合い○", "081": "折り合い×", "082": "先行力○", "084": "瞬発力○", "085": "瞬発力×", "087": "大トビ", "090": "左回り○", "092": "馬込み×", "096": "物見", "097": "鐙外れ", "098": "ソラ使う", "101": "ダート×", "102": "芝×", "103": "左モタレ", "104": "右モタレ", "106": "落馬", "112": "ジリ脚", "114": "ローカル向き", "115": "外逃げる", "119": "コーナーワーク×", "120": "小回り向き", "123": "追って甘い", "124": "坂○", "126": "走る気ない", "130": "終い甘い", "131": "他馬気にする", "144": "器用さ欠く", "145": "使い込む×", "146": "手前替え×", "149": "後方から", "150": "終い確実", "151": "展開待ち", "152": "砂被る○", "153": "砂被る×", "154": "コーナーワーク○", "155": "坂×", "156": "ふらつく", "157": "ダッシュ○", "158": "ダッシュ×", "159": "フワフワ", "160": "中山向き", "161": "府中向き", "162": "腰甘い", "167": "気難しい", "168": "小頭数○", "169": "ノメル", "171": "追って頭上げる", "172": "砂被り頭上げる", "173": "広いコース向き", "174": "ラチ接触", "177": "追ってしっかり", "179": "外被せられる×", "182": "一頭だと気を抜く", "186": "首使い×", "189": "フットワーク×", "191": "中間挫跖", "192": "気性成長", "194": "気性若い", "198": "直線長いコース向き", "199": "外から被せられる×", "202": "飛越×", "209": "立ち回り○", "210": "立ち回り×", "213": "平地力×", "215": "スタミナ○", "216": "スタミナ×", "222": "芝向き", "224": "ダート向き", "251": "去勢", "252": "初出走", "254": "転厩初戦", "301": "距離短縮", "303": "距離延長", "304": "休み明け", "305": "叩き2走目", "321": "格上挑戦", "329": "降級", "343": "ブリンカー", "345": "チークピーシズ", "351": "馬体増", "358": "馬体減", "360": "去勢明け", "366": "転厩", "367": "初ダート", "368": "初芝", "370": "初障害", "384": "地方転入", "385": "地方交流", "387": "休養明け", "388": "連闘", "391": "輸送", "392": "長距離輸送", "395": "調教良い", "396": "調教悪い", "397": "馬体良い", "398": "馬体細い", "399": "馬体太い", "400": "気配良い", "401": "気配悪い", "403": "道悪○", "404": "道悪×", "413": "ハミ替え", "415": "馬具変更", "418": "初コース", "419": "得意コース", "420": "苦手コース", "421": "小回り", "422": "広いコース", "425": "右回り", "428": "左回り", "432": "速い馬場", "433": "遅い馬場", "434": "芝替り", "435": "ダート替り", "436": "距離適性", "437": "展開向く", "440": "展開不向き", "441": "相手強化", "442": "相手弱化", "443": "斤量増", "444": "斤量減", "445": "騎手強化", "448": "騎手替り", "449": "厩舎期待", "450": "調教注目", "451": "状態上向き", "452": "状態下降", "453": "好調", "459": "不調", "461": "逃げ有利", "462": "差し有利", "465": "外枠有利", "472": "内枠有利", "474": "混戦", "477": "少頭数", "478": "多頭数", "480": "重賞", "481": "特別戦", "484": "新馬戦", "485": "未勝利戦", "486": "条件戦", "487": "オープン", "490": "昇級", "491": "降級", "517": "道悪", "518": "良馬場", "519": "暑さ", "553": "寒さ", "555": "夏場", "556": "冬場", "557": "叩き良化", "704": "出遅れ", "705": "不利", "706": "前残り", "711": "差し届かず", "718": "直線不利", "722": "展開不向き", "723": "展開向く", "724": "馬場不向き", "725": "馬場向く", "728": "距離不向き", "729": "距離向く", "730": "コース不向き", "732": "コース向く", "733": "騎手不向き", "734": "騎手向く", "735": "調教師注目", "736": "仕上がり良", "739": "仕上がり途上", "760": "ブリンカー効果", "770": "馬具効果", "772": "ハミ替え効果", "781": "去勢効果", "782": "転厩効果", "785": "休養効果", "787": "前走不利", "789": "前走好内容", "795": "前走凡走", "797": "相手なり", "798": "気性難", "804": "骨折明け", "806": "手術明け", "809": "放牧明け", "810": "入厩初戦", "811": "入厩2走目", "812": "再入厩", "816": "長欠明け", "817": "短期放牧", "818": "中間順調", "819": "中間一息", "820": "中間軽め", "844": "調教強化", "869": "坂路中心", "871": "ウッド中心", "872": "併せ馬", "873": "単走", "874": "ゲート練習", "880": "追い切り注目", "881": "追い切り平凡", "882": "一週前好時計", "883": "一週前平凡", "884": "終い重点", "885": "長め追い", "886": "軽め調整", "887": "厩舎コメント", "888": "馬体確認", "889": "パドック注目", "951": "初勝利期待", "955": "上位争い", "957": "穴候補", "958": "大穴候補", "964": "連下候補", "966": "押さえ候補", "985": "能力上位", "988": "成長期待", "993": "条件好転", "994": "クラス上位の内容", "996": "格上挑戦", "997": "直前で騎手が変更"}
TOKKI.update({"234": "時計掛○", "309": "他馬と接触", "136": "腰悪い", "349": "タイムオーバー", "332": "使い込む○", "125": "体質弱い", "226": "飛越△", "848": "背ったる", "049": "気悪", "065": "ダ軽い○", "240": "終いダ○", "045": "恐がり", "218": "道悪×", "364": "札幌向き", "365": "函館向き", "108": "馬込ダメ", "501": "感冒", "089": "右回り○", "791": "トビ綺麗", "890": "後ろから行く○", "471": "食い細", "740": "追いかけられる○", "344": "滞在競馬○", "488": "軟ら芝○", "183": "ラチ頼る", "340": "夏○", "141": "ゲート悪い", "707": "フットワーク○", "968": "アテにしづらい", "064": "ダ重い×", "164": "足元弱い", "249": "背が低い", "324": "レース中故障（入線）", "073": "芝滑る○", "050": "素直", "987": "ワンターン向き", "967": "乗り難しい", "476": "ゲート音怖がる", "163": "怯む", "069": "芝重い○", "105": "センスある", "341": "夏×", "322": "喉弱い", "147": "小回り×", "184": "耳絞る", "075": "芝少し掛○", "217": "道悪○", "371": "小倉向き"})
# 特記コード表（2026.04.13）の「内容」列で PACI260815 に出現したコードを上書きする。
# 旧PoC由来の別コード体系との混同を防ぐため、未知コードは従来どおり warning とする。
TOKKI.update({
    "053": "頭高い(レース中)", "114": "ローカル向", "150": "お終い確実", "172": "砂被頭上げる",
    "222": "バンケット×", "224": "バンケット○", "251": "連続障害○", "252": "連続障害×", "254": "踏み切り×",
    "301": "非力", "303": "トモ良化", "304": "高脚使う", "305": "平坦向き", "321": "脚を外に振って走る",
    "324": "レース中故障(入線)", "329": "連闘○", "343": "(競争中)鼻出血", "345": "リズム悪い", "351": "舌がハミ越す",
    "358": "疲れ気味", "360": "ブリ効果あり", "366": "福島向き", "367": "新潟向き", "368": "中京向き", "370": "京都向き",
    "384": "渋馬場○", "385": "渋馬場×", "387": "不利", "388": "アオル", "391": "距離長", "392": "距離短",
    "395": "スピード有", "396": "スピード無", "397": "集中力出る", "398": "集中力ない", "399": "下を気にする",
    "400": "内側に斜行", "401": "外側に斜行", "403": "(道中)息入る", "404": "(道中)息入らず", "413": "躓く", "415": "大外回る",
    "418": "急仕上げ", "419": "掛かる", "420": "掛かり気味", "421": "突っ張る", "422": "行きたがる", "425": "調教再審査",
    "428": "枠内駐立不良", "432": "連闘×", "433": "パワー○", "434": "スタート芝×", "435": "息切れ", "436": "逆手前", "437": "気を抜く",
    "440": "追い通し", "441": "余力なし", "442": "いい脚長く使う", "443": "落ち着きほしい", "444": "落ち着きでる", "445": "レースせず",
    "448": "バランス崩す", "449": "ペース速い○", "450": "ペース速い×", "451": "ペース遅い○", "452": "ペース遅い×",
    "453": "モタつく", "459": "口割る", "461": "減量効果あり", "462": "いい脚少しだけ", "465": "馬込平気", "472": "瞬発力△",
    "474": "エンジン掛遅", "477": "軟ら芝×", "478": "次走良化気配", "480": "芝大丈夫", "481": "ダ大丈夫", "484": "前行くとダメ",
    "485": "見せ場なし", "486": "後方まま", "487": "中間熱発", "490": "馬込△", "491": "フットワーク△",
    "517": "左前肢挫創", "518": "右後肢挫創", "519": "左後肢挫創", "553": "両前裂蹄", "555": "右寛跛行", "556": "左寛跛行", "557": "右肩跛行",
    "704": "つかみどころない", "705": "内側に逃避", "706": "外側に逃避", "711": "空馬影響", "718": "道中外々", "722": "勝負所モタつく",
    "723": "適距離", "724": "ゲート練習", "725": "障害練習", "728": "時計速○", "729": "時計速×", "730": "脚使処難", "732": "レース振スムーズ",
    "733": "一本調子", "734": "完歩小さい", "735": "芝ダＯＫ", "736": "スムーズさ欠", "739": "水浮ダ○", "760": "転厩", "770": "頭上げる",
    "772": "フラフラ", "781": "直線追うのやめる", "782": "異常歩様", "785": "仕掛け遅れる", "787": "ゴチャつく", "789": "併せる形○",
    "795": "脚抜きいいダ○", "797": "乾いたダ○", "798": "乾いたダ×", "804": "直線余力あり", "806": "ヨレる", "809": "荒れ馬場○",
    "810": "荒れ馬場△", "811": "荒れ馬場×", "812": "ハナこだわらず", "816": "仕掛け早い", "817": "馬場良い所通る", "818": "馬場悪い所通る",
    "819": "展開厳しい", "820": "展開恵まれ", "844": "馬場入り嫌がる", "869": "緩急苦手", "871": "高速馬場×", "872": "上がり速い○",
    "873": "上がり速い×", "874": "上がり掛かる○", "880": "完勝", "881": "距離○", "882": "展開向かず", "883": "追って案外", "884": "４角一杯",
    "885": "出ムチ入る", "886": "展開向く", "887": "二の脚速い", "888": "後ろから行くとダメ", "889": "前に行く○", "951": "インベタを徹底",
    "955": "蓋される", "957": "直線で前が壁", "958": "寄られる", "964": "道中ブレーキ踏む", "966": "騎手と手が合う", "985": "休養効果あり",
    "988": "ツーターン向き", "993": "次走は危険",
})
EQUIPMENT = {"000": "ノーマルハミ", "001": "ブリンカー", "002": "シャドーロール", "003": "リングハミ", "004": "Dハミ", "005": "エッグハミ", "006": "枝ハミ", "007": "バンテージ", "008": "メンコ", "009": "ガムチェーン", "010": "ハートハミ", "011": "ハミ吊", "012": "ビットガード", "013": "ノートンハミ", "014": "ジョウハミ", "015": "スライド", "016": "てこハミ", "017": "イタイタ", "018": "ノーズバンド", "019": "チェーンシャンク", "020": "パドックブリンカー", "021": "舌くくる", "022": "上唇くくる", "023": "馬気", "024": "下痢", "025": "二度汗", "026": "頭高い", "028": "毛艶良い", "030": "毛艶悪い", "031": "ミックレム頭絡", "032": "引き返し", "036": "レバーノーズバンド", "037": "保護テープ", "038": "キネトンノーズバンド", "039": "アダプターパッド", "040": "ノーマルハミポチつき", "041": "皮膚病", "042": "玉腫れる", "043": "フケ", "044": "スリーリングハミ", "045": "ソエ焼く", "047": "半鉄", "048": "連尾鉄", "049": "四分の三蹄鉄（曲）", "050": "鉄橋鉄", "054": "四分の三蹄鉄", "055": "目の下黒い", "056": "エクイロックス", "061": "骨瘤大", "062": "骨瘤小", "063": "ソエ腫れ大", "064": "ソエ腫れ小", "067": "サイテーションハミ", "068": "ネックストラップ", "069": "ホライゾネット（レース）", "070": "ホライゾネット（パドック）", "071": "ハナゴム", "072": "ユニバーサルハミ", "073": "蹄鉄なし", "074": "チークピース", "075": "追突防止パッド", "076": "新エクイロックス", "077": "スプーンヒール鉄", "078": "柿元鉄", "079": "耳当て", "080": "体毛剃る", "081": "プラスチックカップ", "082": "マウスネット", "083": "ブロウピース", "084": "ヒールパッド", "085": "リバーシブル鉄", "087": "歯ぎしり", "088": "リーグルハミ", "089": "ホートンハミ", "090": "トライアハミ", "091": "シガフース蹄鉄", "092": "ピーウィーハミ", "094": "裂蹄", "095": "蹄底パッド", "096": "アイシールド", "097": "e（HS社ハミ）", "098": "タンプレートハミ", "099": "耳栓"}
LEG_CONDITION = {"000": "バンテージ腕節まで", "001": "蹄汚い", "002": "球節腫れる", "003": "交突バ繋部分", "004": "交突防止帯", "005": "蹄鉄浮く", "006": "蹄冠部全面裂蹄防止テープ", "007": "蹄壁部裂蹄防止テープ", "008": "ブーツ", "009": "バンテージ外す", "010": "バンテージ巻く", "011": "ソエ焼き", "012": "半鉄", "013": "連尾鉄", "014": "曲鉄", "015": "鉄橋", "017": "四分の三鉄", "018": "脚腫れる", "019": "繋ぎキズ", "020": "ソエ傷", "021": "アダプターパッド", "022": "調教バンテージ", "023": "左前球節キズ", "024": "バンテージ巻き跡", "025": "交突蹄冠部分", "026": "蹄冠部キズ", "027": "裏筋腫れる", "028": "骨瘤", "029": "骨瘤腫れ小", "030": "ソエ腫れる", "031": "ソエ腫れ小", "032": "膝焼く", "033": "膝キズ", "034": "膝裏焼く", "035": "エクイロックス", "036": "裏筋傷", "037": "骨瘤焼く", "038": "水ブリスター", "040": "裸足", "041": "追突防止パッド", "042": "新エクイロックス", "043": "蹄欠損", "045": "スプーンヒール鉄", "046": "柿元鉄", "047": "飛節焼き治療", "048": "蹄切り込み線", "049": "着地時に蹄をひねる", "050": "着地時に蹄踵が浮く", "051": "球節が沈む", "057": "球節バンテージ", "100": "痛そうな歩様", "104": "トモ流れる", "108": "両前バンテージ外す", "109": "両前バンテージ巻く", "113": "脚部不安", "117": "膝硬い", "118": "後肢躓く", "119": "交差する歩様"}
LEG_CONDITION.update({"054": "鉄唇３つ", "060": "繋弾く"})


def load_bundled_codebooks() -> None:
    """Load official tables generated by generate_jrdb_codebooks.py.

    TOKKI と ASHIMOTO は同じ3桁コードでも別体系であり、相互に混在させない。
    旧版の部分辞書は互換fallbackだけにし、同梱マスタを優先する。
    """
    path = Path(__file__).with_name("jrdb_codebooks.json")
    if not path.is_file():
        logging.warning("公式コードブックが見つからないため互換辞書を使用します: %s", path)
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tokki = data["TOKKI"]
        ashimoto = data["ASHIMOTO"]
        if not isinstance(tokki, dict) or not isinstance(ashimoto, dict):
            raise ValueError("TOKKI/ASHIMOTO が辞書ではありません")
        TOKKI.update({str(code): str(value) for code, value in tokki.items()})
        LEG_CONDITION.update({str(code): str(value) for code, value in ashimoto.items()})
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"公式コードブックを読み込めません: {path}") from exc


load_bundled_codebooks()


@dataclass
class Audit:
    warnings: Counter[str] = field(default_factory=Counter)
    record_length_errors: Counter[str] = field(default_factory=Counter)
    duplicate_key_errors: Counter[str] = field(default_factory=Counter)
    bundle_errors: list[str] = field(default_factory=list)
    required_field_missing: Counter[str] = field(default_factory=Counter)
    target_result_contamination: int = 0
    decoded: Counter[str] = field(default_factory=Counter)
    horse_trait_duplicates: int = 0
    all_null_pace_ranks_races: int = 0
    abnormal_zero_values: int = 0

    def unknown(self, kind: str, code: str) -> None:
        if code:
            self.warnings[f"unknown_{kind}:{code}"] += 1


def decode(code: str | None, table: dict[str, str | None], kind: str, audit: Audit) -> str | None:
    if code is None or not str(code).strip():
        return None
    code = str(code).strip()
    if code not in table:
        audit.unknown(kind, code)
        return None
    audit.decoded[kind] += 1
    return table[code]


def unique_in_order(values: Iterable[str]) -> list[str]:
    """空値を除き、初出順を保って文字列値だけ重複除去する。"""
    seen: set[str] = set()
    return [value for value in values if value and not (value in seen or seen.add(value))]


def text_field(record: bytes, start: int, length: int) -> str | None:
    raw = record[start - 1:start - 1 + length]
    value = raw.decode("cp932", errors="replace").replace("\u3000", " ").strip()
    return value or None


def raw_field(record: bytes, start: int, length: int) -> str:
    return record[start - 1:start - 1 + length].decode("ascii", errors="replace").strip()


def number_field(record: bytes, start: int, length: int) -> int | float | None:
    value = raw_field(record, start, length).replace(",", "")
    if not value:
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return None


def tenths(record: bytes, start: int, length: int) -> float | None:
    value = number_field(record, start, length)
    return None if value is None else float(value) / 10


def ymd(value: str | None) -> str | None:
    if not value or len(value) != 8 or not value.isdigit():
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def hhmm(value: str | None) -> str | None:
    if not value or len(value) != 4 or not value.isdigit():
        return None
    return f"{value[:2]}:{value[2:]}"


def race_key(record: bytes) -> str:
    return raw_field(record, 1, 8)


def race_horse_key(record: bytes) -> str:
    return race_key(record) + raw_field(record, 9, 2)


def result_key(record: bytes) -> str:
    return raw_field(record, 11, 8) + raw_field(record, 19, 8)


def race_key_parts(key: str) -> dict[str, Any]:
    return {"venue_code": key[:2], "year_yy": key[2:4], "meeting": key[4:5], "day_raw": key[5:6], "race_no": int(key[6:8]) if key[6:8].isdigit() else None}


def read_fixed_records(zf: zipfile.ZipFile, member: str, prefix: str, audit: Audit) -> list[bytes]:
    """Compatibility facade; fixed-record splitting is owned by jrdb_raw."""
    return common_read_fixed_records(zf, member, prefix, audit)


class Parser:
    """固定長BYTE位置のみを扱う層。意味変換は Normalizer に委譲する。"""

    def __init__(self, audit: Audit) -> None:
        self.audit = audit

    def bac(self, record: bytes) -> dict[str, Any]:
        return {"race_key_raw": race_key(record), "date_raw": raw_field(record, 9, 8), "post_time_raw": raw_field(record, 17, 4), "distance_raw": raw_field(record, 21, 4), "surface_code": raw_field(record, 25, 1), "turn_code": raw_field(record, 26, 1), "layout_code": raw_field(record, 27, 1), "race_type_code": raw_field(record, 28, 2), "race_class_code": raw_field(record, 30, 2), "symbol_code": raw_field(record, 32, 3), "weight_rule_code": raw_field(record, 35, 1), "grade_code": raw_field(record, 36, 1), "race_name": text_field(record, 37, 50), "meeting": text_field(record, 87, 8), "field_size": number_field(record, 95, 2), "course_code": raw_field(record, 97, 1)}

    def kyi(self, record: bytes) -> dict[str, Any]:
        previous = [{"result_key": raw_field(record, 204 + index * 16, 16), "race_key_raw": raw_field(record, 284 + index * 8, 8)} for index in range(5)]
        return {"race_key_raw": race_key(record), "race_horse_key": race_horse_key(record), "horse_no": number_field(record, 9, 2), "blood_registration_no": raw_field(record, 11, 8), "horse_name": text_field(record, 19, 36), "idm": number_field(record, 55, 5), "jockey_index": number_field(record, 60, 5), "info_index": number_field(record, 65, 5), "total_index": number_field(record, 85, 5), "running_style_code": raw_field(record, 90, 1), "distance_fit_code": raw_field(record, 91, 1), "improvement_code": raw_field(record, 92, 1), "rotation_interval": number_field(record, 93, 3), "base_win_odds": number_field(record, 96, 5), "base_win_rank": number_field(record, 101, 2), "base_place_odds": number_field(record, 103, 5), "base_place_rank": number_field(record, 108, 2), "training_index": number_field(record, 145, 5), "stable_index": number_field(record, 150, 5), "training_arrow_code": raw_field(record, 155, 1), "stable_evaluation_code": raw_field(record, 156, 1), "jockey_expected_top2_rate": number_field(record, 157, 4), "longshot_index": number_field(record, 161, 3), "hoof_code": raw_field(record, 164, 2), "heavy_track_fit_code": raw_field(record, 166, 1), "jrdb_class_code": raw_field(record, 167, 2), "blinker_code": raw_field(record, 171, 1), "jockey": text_field(record, 172, 12), "carried_weight_tenths": number_field(record, 184, 3), "apprentice_code": raw_field(record, 187, 1), "trainer": text_field(record, 188, 12), "trainer_base": text_field(record, 200, 4), "previous": previous, "frame_no": number_field(record, 324, 1), "marks": {"total": raw_field(record, 327, 1), "idm": raw_field(record, 328, 1), "info": raw_field(record, 329, 1), "jockey": raw_field(record, 330, 1), "stable": raw_field(record, 331, 1), "training": raw_field(record, 332, 1), "longshot": raw_field(record, 333, 1)}, "turf_fit_code": raw_field(record, 334, 1), "dirt_fit_code": raw_field(record, 335, 1), "jockey_code": raw_field(record, 336, 5), "trainer_code": raw_field(record, 341, 5), "pace_indices": {"front": number_field(record, 359, 5), "pace": number_field(record, 364, 5), "late": number_field(record, 369, 5), "position": number_field(record, 374, 5)}, "pace_ranks": {"front": number_field(record, 453, 2), "pace": number_field(record, 455, 2), "late": number_field(record, 457, 2), "position": number_field(record, 459, 2)}, "forecast_pace_code": raw_field(record, 379, 1), "forecast_positions": {"mid": (number_field(record, 380, 2), number_field(record, 382, 2), raw_field(record, 384, 1)), "last3f": (number_field(record, 385, 2), number_field(record, 387, 2), raw_field(record, 389, 1)), "finish": (number_field(record, 390, 2), number_field(record, 392, 2), raw_field(record, 394, 1))}, "symbol_code": raw_field(record, 395, 1), "start_index": number_field(record, 520, 4), "late_break_rate": number_field(record, 524, 4), "rest_reason_code": raw_field(record, 542, 2), "farm_name": text_field(record, 573, 50), "farm_rank": raw_field(record, 623, 1), "farm_index_rank": number_field(record, 624, 1), "trait_codes": [raw_field(record, pos, 3) for pos in (502, 505, 508, 511, 514, 517)]}

    def cha(self, record: bytes) -> dict[str, Any]:
        return {"race_horse_key": race_horse_key(record), "date_raw": raw_field(record, 13, 8), "course_code": raw_field(record, 22, 2), "strength_code": raw_field(record, 24, 1), "state_code": raw_field(record, 25, 2), "rider_type_code": raw_field(record, 27, 1), "furlongs": number_field(record, 28, 1), "clock": {"front": tenths(record, 29, 3), "middle": tenths(record, 32, 3), "last": tenths(record, 35, 3)}, "clock_index": {"front": number_field(record, 38, 3), "middle": number_field(record, 41, 3), "last": number_field(record, 44, 3), "total": number_field(record, 47, 3)}, "pair": {"result_code": raw_field(record, 50, 1), "strength_code": raw_field(record, 51, 1), "age": number_field(record, 52, 2), "class_code": raw_field(record, 54, 2)}}

    def cyb(self, record: bytes) -> dict[str, Any]:
        return {"race_horse_key": race_horse_key(record), "course_counts": {"slope": number_field(record, 14, 2), "wood": number_field(record, 16, 2), "dirt": number_field(record, 18, 2), "turf": number_field(record, 20, 2), "pool": number_field(record, 22, 2), "obstacle": number_field(record, 24, 2), "polytrack": number_field(record, 26, 2)}, "distance_pattern_code": raw_field(record, 28, 1), "focus_code": raw_field(record, 29, 1), "training_index": number_field(record, 30, 3), "condition_index": number_field(record, 33, 3), "volume_grade": raw_field(record, 36, 1), "condition_change_code": raw_field(record, 37, 1), "comment": text_field(record, 38, 40), "comment_date_raw": raw_field(record, 78, 8), "training_grade_code": raw_field(record, 86, 1), "one_week_ago_index": number_field(record, 87, 3), "one_week_ago_course": raw_field(record, 90, 2)}

    def zed(self, record: bytes) -> dict[str, Any]:
        return {"race_key_raw": race_key(record), "result_key": result_key(record), "date_raw": raw_field(record, 19, 8), "race_name": text_field(record, 81, 50), "distance_m": number_field(record, 63, 4), "surface_code": raw_field(record, 67, 1), "turn_code": raw_field(record, 68, 1), "layout_code": raw_field(record, 69, 1), "track_condition_code": raw_field(record, 70, 2), "race_type_code": raw_field(record, 72, 2), "race_class_code": raw_field(record, 74, 2), "grade_code": raw_field(record, 80, 1), "field_size": number_field(record, 131, 2), "finish": number_field(record, 141, 2), "abnormal_code": raw_field(record, 143, 1), "time_raw": raw_field(record, 144, 4), "carried_weight_tenths": number_field(record, 148, 3), "jockey": text_field(record, 151, 12), "final_win_odds": number_field(record, 175, 6), "final_popularity_raw": raw_field(record, 181, 2), "final_popularity": number_field(record, 181, 2), "idm": number_field(record, 183, 3), "metrics": {"raw_score": number_field(record, 186, 3), "track_diff": number_field(record, 189, 3), "pace_score": number_field(record, 192, 3), "late_break_score": number_field(record, 195, 3), "position_score": number_field(record, 198, 3), "trouble_score": number_field(record, 201, 3), "prev_trouble_score": number_field(record, 204, 3), "mid_trouble_score": number_field(record, 207, 3), "late_trouble_score": number_field(record, 210, 3), "race_score": number_field(record, 213, 3), "front_index": number_field(record, 224, 5), "late_index": number_field(record, 229, 5), "pace_index": number_field(record, 234, 5), "race_pace_index": number_field(record, 239, 5)}, "course_lane_code": raw_field(record, 216, 1), "corners": [number_field(record, p, 2) for p in (309, 311, 313, 315)], "first3f_sec": tenths(record, 259, 3), "last3f_sec": tenths(record, 262, 3), "race_pace_code": raw_field(record, 222, 1), "horse_pace_code": raw_field(record, 223, 1), "body_weight_kg": number_field(record, 333, 3), "body_weight_change_kg": number_field(record, 336, 3), "weather_code": raw_field(record, 339, 1), "body_condition_code": raw_field(record, 220, 1)}

    def zkb(self, record: bytes) -> dict[str, Any]:
        return {"result_key": result_key(record), "tokki_codes": [raw_field(record, 27 + i * 3, 3) for i in range(6)], "equipment_codes": [raw_field(record, 45 + i * 3, 3) for i in range(8)], "leg_codes": {"overall": raw_field(record, 69, 3), "left_front": raw_field(record, 78, 3), "right_front": raw_field(record, 87, 3), "left_hind": raw_field(record, 96, 3), "right_hind": raw_field(record, 105, 3)}, "paddock_comment": text_field(record, 114, 40), "leg_comment": text_field(record, 154, 40), "equipment_comment": text_field(record, 194, 40), "race_comment": text_field(record, 234, 40)}


# Keep the old implementation only as a temporary characterization oracle.
LegacyParser = Parser
# Production fixed-width parsing is owned by the common JRDB reader.
Parser = CommonParser


class Normalizer:
    """コードから日本語値を作る層。raw code はこの層より外へ渡さない。"""

    def __init__(self, audit: Audit) -> None:
        self.audit = audit

    def race(self, raw: dict[str, Any]) -> dict[str, Any]:
        parts = race_key_parts(raw["race_key_raw"])
        return {"date": ymd(raw["date_raw"]), "venue": decode(parts["venue_code"], VENUES, "venue", self.audit), "meeting": parts["meeting"], "day": parts["day_raw"], "race_no": parts["race_no"], "post_time": hhmm(raw["post_time_raw"]), "race_name": raw["race_name"], "surface": decode(raw["surface_code"], SURFACE, "surface", self.audit), "distance_m": raw["distance_raw"] and int(raw["distance_raw"]) if raw["distance_raw"].isdigit() else None, "turn": decode(raw["turn_code"], TURN, "turn", self.audit), "course_layout": decode(raw["layout_code"], COURSE_LAYOUT, "course_layout", self.audit), "race_type": decode(raw["race_type_code"], RACE_TYPE, "race_type", self.audit), "class": decode(raw["race_class_code"], RACE_CLASS, "race_class", self.audit), "race_conditions": self.symbols(raw["symbol_code"]), "weight_rule": decode(raw["weight_rule_code"], WEIGHT_RULE, "weight_rule", self.audit), "grade": decode(raw["grade_code"], GRADE, "grade", self.audit), "field_size": raw["field_size"]}

    def symbols(self, code: str) -> list[str]:
        if not code:
            return []
        sets = ({"1": "混合", "2": "父内国産", "3": "市・抽選", "4": "九州産限定", "5": "国際混合"}, {"1": "牡馬限定", "2": "牝馬限定", "3": "牡・せん馬限定", "4": "牡・牝馬限定"}, {"1": "指定", "2": "地方指定", "3": "特別指定", "4": "若手騎手"})
        return [sets[i][c] for i, c in enumerate(code.zfill(3)[-3:]) if c != "0" and c in sets[i]]

    def horse(self, raw: dict[str, Any], cha: dict[str, Any] | None, cyb: dict[str, Any] | None) -> dict[str, Any]:
        fp = raw["forecast_positions"]
        def pos(item: tuple[Any, Any, str]) -> dict[str, Any]:
            return {"order": item[0], "margin": item[1], "lane": decode(item[2], LANE, "forecast_lane", self.audit)}
        traits = [decode(c, TOKKI, "tokki", self.audit) for c in raw["trait_codes"] if c and c != "000"]
        unique_traits = unique_in_order(traits)
        self.audit.horse_trait_duplicates += len([x for x in traits if x]) - len(unique_traits)
        return {"basic": {"frame_no": raw["frame_no"], "horse_no": raw["horse_no"], "horse_name": raw["horse_name"], "jockey": raw["jockey"], "carried_weight_kg": None if raw["carried_weight_tenths"] is None else raw["carried_weight_tenths"] / 10, "apprentice": {"1": "☆", "2": "△", "3": "▲", "4": "★", "9": "◇"}.get(raw["apprentice_code"]), "trainer": raw["trainer"], "trainer_base": raw["trainer_base"], "blinker": decode(raw["blinker_code"], BLINKER, "blinker", self.audit)}, "ability": {"idm": raw["idm"], "total_index": raw["total_index"], "running_style": decode(raw["running_style_code"], {**RUNNING_STYLE, "0": None}, "running_style", self.audit), "distance_fit": decode(raw["distance_fit_code"], {**DISTANCE_FIT, "0": None}, "distance_fit", self.audit), "surface_fit": {"turf": decode(raw["turf_fit_code"], THREE_LEVEL, "turf_fit", self.audit), "dirt": decode(raw["dirt_fit_code"], THREE_LEVEL, "dirt_fit", self.audit)}, "heavy_track_fit": decode(raw["heavy_track_fit_code"], THREE_LEVEL, "heavy_track_fit", self.audit), "jrdb_class": decode(raw["jrdb_class_code"], JRDB_CLASS, "jrdb_class", self.audit)}, "condition": {"improvement": decode(raw["improvement_code"], IMPROVEMENT, "improvement", self.audit), "rotation_interval": raw["rotation_interval"], "stable_evaluation": decode(raw["stable_evaluation_code"], STABLE_EVAL, "stable_evaluation", self.audit), "farm": {"name": raw["farm_name"], "rank": raw["farm_rank"] or None, "index_rank": raw["farm_index_rank"]}, "rest_reason": decode(raw["rest_reason_code"], REST_REASON, "rest_reason", self.audit), "horse_traits": unique_traits}, "pace": {"start_index": raw["start_index"], "late_break_rate": raw["late_break_rate"], "forecast_pace": decode(raw["forecast_pace_code"], PACE, "forecast_pace", self.audit), "indices": raw["pace_indices"], "ranks": raw["pace_ranks"], "forecast_positions": {"mid": pos(fp["mid"]), "last3f": pos(fp["last3f"]), "finish": pos(fp["finish"])}, "symbol": decode(raw["symbol_code"], PACE_SYMBOL, "pace_symbol", self.audit)}, "training": {"summary": {"training_index": raw["training_index"], "training_arrow": decode(raw["training_arrow_code"], TRAINING_ARROW, "training_arrow", self.audit)}, "main_workout": self.workout(cha), "analysis": self.training_analysis(cyb)}, "market": {"base_win_odds": raw["base_win_odds"], "base_win_rank": raw["base_win_rank"], "base_place_odds": raw["base_place_odds"], "base_place_rank": raw["base_place_rank"]}, "jrdb_ratings": {"jockey_index": raw["jockey_index"], "info_index": raw["info_index"], "stable_index": raw["stable_index"], "longshot_index": raw["longshot_index"], "jockey_expected_top2_rate": raw["jockey_expected_top2_rate"], "marks": {key: decode(value, MARK, "mark", self.audit) for key, value in raw["marks"].items()}}, "recent_runs": []}

    def workout(self, raw: dict[str, Any] | None) -> dict[str, Any] | None:
        if raw is None:
            return None
        return {"date": ymd(raw["date_raw"]), "course": decode(raw["course_code"], TRAINING_COURSE, "training_course", self.audit), "strength": decode(raw["strength_code"], WORKOUT_STRENGTH, "workout_strength", self.audit), "state": decode(raw["state_code"], TRAINING_STATE, "training_state", self.audit), "rider_type": decode(raw["rider_type_code"], RIDER_TYPE, "rider_type", self.audit), "furlongs": raw["furlongs"], "clock": raw["clock"], "clock_index": raw["clock_index"], "pair": {"result": decode(raw["pair"]["result_code"], PAIR_RESULT, "pair_result", self.audit), "strength": decode(raw["pair"]["strength_code"], WORKOUT_STRENGTH, "pair_strength", self.audit), "age": raw["pair"]["age"], "class": decode(raw["pair"]["class_code"], RACE_CLASS, "pair_class", self.audit)}}

    def training_analysis(self, raw: dict[str, Any] | None) -> dict[str, Any] | None:
        if raw is None:
            return None
        return {"course_counts": raw["course_counts"], "distance_pattern": {"1": "長め", "2": "普通", "3": "短め", "4": "2本", "0": "その他"}.get(raw["distance_pattern_code"]), "focus": {"1": "テン", "2": "中間", "3": "終い", "4": "平均", "0": "その他"}.get(raw["focus_code"]), "training_index": raw["training_index"], "condition_index": raw["condition_index"], "volume_grade": raw["volume_grade"] or None, "condition_change": None, "comment": raw["comment"], "comment_date": ymd(raw["comment_date_raw"]), "training_grade": {"1": "◎", "2": "○", "3": "△"}.get(raw["training_grade_code"]), "one_week_ago": {"index": raw["one_week_ago_index"], "course": decode(raw["one_week_ago_course"], TRAINING_COURSE, "one_week_course", self.audit)}}

    def history(self, raw: dict[str, Any], notes: dict[str, Any] | None) -> dict[str, Any]:
        parts = race_key_parts(raw["race_key_raw"])
        time_sec = None
        if raw["time_raw"].isdigit() and len(raw["time_raw"]) == 4:
            time_sec = int(raw["time_raw"][0]) * 60 + int(raw["time_raw"][1:]) / 10
        # 取消・除外・中止・失格では、ゼロ埋めの未成立値を実値として出さない。
        # 降着・再騎乗は実走値を持ち得るため、ここでは保持する。
        incomplete = raw["abnormal_code"] in {"1", "2", "3", "4"}
        finish = raw["finish"]
        final_win_odds = raw["final_win_odds"]
        final_popularity = None if raw["final_popularity_raw"] == "00" else raw["final_popularity"]
        if incomplete:
            for value in (finish, time_sec, final_win_odds, final_popularity):
                if value == 0 or value == 0.0:
                    self.audit.abnormal_zero_values += 1
            finish = None if finish == 0 else finish
            time_sec = None if time_sec == 0.0 else time_sec
            final_win_odds = None if final_win_odds == 0 else final_win_odds
            final_popularity = None if final_popularity == 0 else final_popularity
        n = notes or {"tokki_codes": [], "equipment_codes": [], "leg_codes": {"overall": "", "left_front": "", "right_front": "", "left_hind": "", "right_hind": ""}, "paddock_comment": None, "leg_comment": None, "equipment_comment": None, "race_comment": None}
        leg_condition = {position: ([decoded] if (code and code != "000" and (decoded := decode(code, LEG_CONDITION, "leg_condition", self.audit))) else []) for position, code in n["leg_codes"].items()}
        return {"race": {"date": ymd(raw["date_raw"]), "venue": decode(parts["venue_code"], VENUES, "venue", self.audit), "race_no": parts["race_no"], "race_name": raw["race_name"], "surface": decode(raw["surface_code"], SURFACE, "surface", self.audit), "distance_m": raw["distance_m"], "turn": decode(raw["turn_code"], TURN, "turn", self.audit), "course_layout": decode(raw["layout_code"], COURSE_LAYOUT, "course_layout", self.audit), "track_condition": decode(raw["track_condition_code"], TRACK_CONDITION, "track_condition", self.audit), "race_type": decode(raw["race_type_code"], RACE_TYPE, "race_type", self.audit), "class": decode(raw["race_class_code"], RACE_CLASS, "race_class", self.audit), "grade": decode(raw["grade_code"], GRADE, "grade", self.audit), "field_size": raw["field_size"], "weather": decode(raw["weather_code"], WEATHER, "weather", self.audit)}, "result": {"finish": finish, "abnormal": decode(raw["abnormal_code"], ABNORMAL, "abnormal", self.audit), "time_sec": time_sec, "carried_weight_kg": None if raw["carried_weight_tenths"] is None else raw["carried_weight_tenths"] / 10, "jockey": raw["jockey"], "final_win_odds": final_win_odds, "final_popularity": final_popularity}, "performance": {"idm": raw["idm"], "corners": raw["corners"], "first3f_sec": raw["first3f_sec"], "last3f_sec": raw["last3f_sec"], "race_pace": decode(raw["race_pace_code"], PACE, "race_pace", self.audit), "horse_pace": decode(raw["horse_pace_code"], PACE, "horse_pace", self.audit), "course_lane": decode(raw["course_lane_code"], LANE, "course_lane", self.audit)}, "body": {"body_weight_kg": raw["body_weight_kg"], "body_weight_change_kg": raw["body_weight_change_kg"], "body_condition": decode(raw["body_condition_code"], BODY_CONDITION, "body_condition", self.audit), "hoof": None}, "jrdb_metrics": raw["metrics"], "notes": {"special_notes": [x for x in (decode(c, TOKKI, "tokki", self.audit) for c in n["tokki_codes"] if c and c != "000") if x], "equipment": [x for x in (decode(c, EQUIPMENT, "equipment", self.audit) for c in n["equipment_codes"] if c and c != "000") if x], "leg_condition": leg_condition, "paddock_comment": n["paddock_comment"], "leg_comment": n["leg_comment"], "equipment_comment": n["equipment_comment"], "race_comment": n["race_comment"]}}


class BundleBuilder:
    """正規化済みモデルを RaceNote v0.2 bundle に結合する層。"""

    def __init__(self, parsed: dict[str, list[dict[str, Any]]], audit: Audit) -> None:
        self.parsed, self.audit, self.normalizer = parsed, audit, Normalizer(audit)
        self.cha = self._index(parsed["CHA"], "race_horse_key", "CHA")
        self.cyb = self._index(parsed["CYB"], "race_horse_key", "CYB")
        self.zed = self._index(parsed["ZED"], "result_key", "ZED")
        self.zkb = self._index(parsed["ZKB"], "result_key", "ZKB")
        self.join = Counter()

    def _index(self, rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = row[key]
            if not value:
                continue
            if value in out:
                self.audit.duplicate_key_errors[label] += 1
                continue
            out[value] = row
        return out

    def build(self, race_raw: dict[str, Any], horses_raw: list[dict[str, Any]]) -> dict[str, Any]:
        race = self.normalizer.race(race_raw)
        if not race["date"] or not race["venue"] or race["race_no"] is None:
            raise ValueError(f"race required fields missing: {race_raw['race_key_raw']}")
        horses: list[dict[str, Any]] = []
        for hraw in sorted(horses_raw, key=lambda x: x["horse_no"] or 99):
            key = hraw["race_horse_key"]
            cha, cyb = self.cha.get(key), self.cyb.get(key)
            self.join["cha_expected"] += 1
            self.join["cyb_expected"] += 1
            self.join["cha_matched"] += cha is not None
            self.join["cyb_matched"] += cyb is not None
            horse = self.normalizer.horse(hraw, cha, cyb)
            if not horse["basic"]["horse_name"]:
                self.audit.required_field_missing["horse_name"] += 1
            for order, previous in enumerate(hraw["previous"], 1):
                previous_key = previous["result_key"]
                if not previous_key:
                    continue
                self.join["zed_expected"] += 1
                zed = self.zed.get(previous_key)
                if zed is None:
                    continue
                # 前走リンクだけを採用し、対象日以降の結果が混ざる場合は除外する。
                if zed["date_raw"] >= race_raw["date_raw"]:
                    self.audit.target_result_contamination += 1
                    continue
                self.join["zed_matched"] += 1
                self.join["zkb_expected"] += 1
                zkb = self.zkb.get(previous_key)
                self.join["zkb_matched"] += zkb is not None
                horse["recent_runs"].append(self.normalizer.history(zed, zkb))
            if len(horse["recent_runs"]) > 5:
                self.audit.bundle_errors.append(f"recent_runs exceeds five: {key}")
                horse["recent_runs"] = horse["recent_runs"][:5]
            horses.append(horse)
        if race["field_size"] != len(horses):
            self.audit.bundle_errors.append(f"field_size mismatch {race['venue']}{race['race_no']} BAC={race['field_size']} KYI={len(horses)}")
        if horses and all(all(value is None for value in horse["pace"]["ranks"].values()) for horse in horses):
            self.audit.all_null_pace_ranks_races += 1
        return {"schema_version": SCHEMA_VERSION, "metadata": {"source": "JRDB PACI", "race_date": race["date"], "data_phase": "pre_race", "generated_at": datetime.now(timezone.utc).isoformat()}, "race": race, "horses": horses}


def find_members(zf: zipfile.ZipFile) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in zf.namelist():
        base = Path(name).name.upper()
        for prefix in REQUIRED_PREFIXES:
            if base.startswith(prefix) and base.endswith(".TXT"):
                found[prefix] = name
    missing = [prefix for prefix in REQUIRED_PREFIXES if prefix not in found]
    if missing:
        raise ValueError(f"PACI ZIPに必須ファイルがありません: {', '.join(missing)}")
    return found


def parse_zip(zip_path: Path, audit: Audit) -> dict[str, list[dict[str, Any]]]:
    parser = Parser(audit)
    method: dict[str, Callable[[bytes], dict[str, Any]]] = {"BAC": parser.bac, "KYI": parser.kyi, "CHA": parser.cha, "CYB": parser.cyb, "ZED": parser.zed, "ZKB": parser.zkb}
    with zipfile.ZipFile(zip_path) as zf:
        members = find_members(zf)
        return {prefix: [method[prefix](row) for row in read_fixed_records(zf, members[prefix], prefix, audit)] for prefix in REQUIRED_PREFIXES}


def percent(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 2) if denominator else None


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert JRDB PACI ZIP to RaceNote v0.2 JSON bundles")
    p.add_argument("zip_path", type=Path, help="PACIyyMMdd.zip")
    p.add_argument("--race", help="例: 札幌1 / 札幌1R（指定時は1Rのみ）")
    p.add_argument("--output", type=Path, default=Path("."), help="出力親フォルダ (default: .)")
    p.add_argument("--format", choices=["json"], default="json", help="出力形式（将来Markdownを追加予定）")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if not args.zip_path.is_file():
            raise ValueError(f"ZIPが見つかりません: {args.zip_path}")
        audit = Audit()
        parsed = parse_zip(args.zip_path, audit)
        date_raw = parsed["BAC"][0]["date_raw"] if parsed["BAC"] else None
        if not date_raw:
            raise ValueError("BACから対象日を取得できません")
        target_date = ymd(date_raw)
        out_dir = args.output / f"RaceNote_{date_raw}"
        out_dir.mkdir(parents=True, exist_ok=True)
        horses_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for horse in parsed["KYI"]:
            horses_by_race[horse["race_key_raw"]].append(horse)
        builder = BundleBuilder(parsed, audit)
        generated: list[tuple[str, dict[str, Any]]] = []
        selected = (args.race or "").replace("R", "").replace("Ｒ", "").replace(" ", "")
        for bac in parsed["BAC"]:
            key = bac["race_key_raw"]
            parts = race_key_parts(key)
            venue = decode(parts["venue_code"], VENUES, "venue", audit) or parts["venue_code"]
            label = f"{venue}{parts['race_no']}"
            if selected and selected != label:
                continue
            try:
                bundle = builder.build(bac, horses_by_race.get(key, []))
                filename = f"race_bundle_{date_raw}_{venue}{parts['race_no']}R.json"
                write_json(out_dir / filename, bundle)
                generated.append((filename, bundle))
            except Exception as exc:
                audit.bundle_errors.append(f"{label}: {type(exc).__name__}: {exc}")
        all_errors = list(audit.bundle_errors)
        if not selected and len(generated) != len(parsed["BAC"]):
            all_errors.append(f"bundle count mismatch BAC={len(parsed['BAC'])} generated={len(generated)}")
        report = {"schema_version": SCHEMA_VERSION, "date": target_date, "record_counts": {name: len(rows) for name, rows in parsed.items()}, "bac_race_count": len(parsed["BAC"]), "kyi_horse_count": len(parsed["KYI"]), "bundle_count": len(generated), "joins": {"KYI_to_CHA": {"matched": builder.join["cha_matched"], "expected": builder.join["cha_expected"], "rate": percent(builder.join["cha_matched"], builder.join["cha_expected"])}, "KYI_to_CYB": {"matched": builder.join["cyb_matched"], "expected": builder.join["cyb_expected"], "rate": percent(builder.join["cyb_matched"], builder.join["cyb_expected"])}, "KYI_previous_to_ZED": {"matched": builder.join["zed_matched"], "expected": builder.join["zed_expected"], "rate": percent(builder.join["zed_matched"], builder.join["zed_expected"])}, "KYI_previous_to_ZKB": {"matched": builder.join["zkb_matched"], "expected": builder.join["zkb_expected"], "rate": percent(builder.join["zkb_matched"], builder.join["zkb_expected"])}}, "unknown_code_count": sum(audit.warnings.values()), "unknown_codes": dict(audit.warnings.most_common()), "decoded_code_counts": {kind: audit.decoded[kind] for kind in ("tokki", "equipment", "leg_condition")}, "decoded_unable_code_count": sum(audit.warnings[k] for k in audit.warnings if k.startswith(("unknown_tokki:", "unknown_equipment:", "unknown_leg_condition:"))), "code_mapping_conflicts": 0, "record_length_errors": dict(audit.record_length_errors), "duplicate_key_errors": dict(audit.duplicate_key_errors), "field_size_mismatch": [x for x in audit.bundle_errors if x.startswith("field_size mismatch")], "required_field_missing": dict(audit.required_field_missing), "target_race_result_contamination": audit.target_result_contamination, "content_validation": {"all_null_pace_ranks_races": audit.all_null_pace_ranks_races, "horse_trait_duplicates_removed": audit.horse_trait_duplicates, "abnormal_zero_values_nullified": audit.abnormal_zero_values}, "bundle_generation_errors": all_errors}
        manifest_warnings: list[Any] = list(audit.warnings.most_common())
        if audit.all_null_pace_ranks_races:
            manifest_warnings.append({"all_null_pace_ranks_races": audit.all_null_pace_ranks_races})
        manifest = {"schema_version": SCHEMA_VERSION, "date": target_date, "race_count": len(parsed["BAC"]), "horse_count": len(parsed["KYI"]), "generated_races": len(generated), "venues": dict(Counter(bundle["race"]["venue"] for _, bundle in generated)), "errors": all_errors, "warnings": manifest_warnings}
        write_json(out_dir / "manifest.json", manifest)
        write_json(out_dir / "validation_report.json", report)
        logging.info("generated=%s output=%s", len(generated), out_dir)
        return 0 if not all_errors else 2
    except (ValueError, zipfile.BadZipFile) as exc:
        logging.error("%s", exc)
        return 2
    except Exception as exc:
        logging.exception("unexpected error: %s", exc)
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
