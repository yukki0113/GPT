"""Official NAR racelist.csv header (66 columns, manual updated 2026-05-21)."""

COLUMNS = (
    "競馬場", "競走年月日", "レース番号", "発走時刻", "競走種類名称", "レース名",
    *(f"副賞名{i}" for i in range(1, 16)),
    "芝ダート区分", "回り", "距離", "天候", "馬場", "頭数", "条件",
    "1着賞金(円)", "2着賞金(円)", "3着賞金(円)", "4着賞金(円)", "5着賞金(円)",
    "上がり4F", "上がり3F",
    *(f"ハロンタイム{i}" for i in range(1, 16)),
    *(f"コーナー名称{i}" for i in range(1, 9)),
    *(f"コーナー通過順{i}" for i in range(1, 9)),
)
