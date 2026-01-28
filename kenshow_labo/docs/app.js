(function () {
  "use strict";

  /** @type {any} */
  var gSqlJs = null;

  /** @type {any} */
  var gDb = null;

  /** @type {string|null} */
  var gLoadedFileName = null;

  function $(id) {
    return document.getElementById(id);
  }

  function setText(id, text) {
    var el = $(id);
    if (el) {
      el.textContent = text;
    }
  }

  function enable(id, enabled) {
    var el = $(id);
    if (el) {
      el.disabled = !enabled;
    }
  }

  function escapeHtml(s) {
    if (s == null) {
      return "";
    }
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatRaceRow(row) {
    // row: [race_id, race_date, track_name, race_no, race_name, surface_type, distance_m, class_simple, win5_flg]
    var raceId = row[0];
    var raceDate = row[1];
    var trackName = row[2];
    var raceNo = row[3];
    var raceName = row[4];
    var surface = row[5];
    var dist = row[6];
    var cls = row[7];
    var win5 = row[8];

    var badge = "";
    if (win5 === 1) {
      badge = '<span class="badge">WIN5</span>';
    }

    return (
      '<div class="item" data-race-id="' +
      escapeHtml(raceId) +
      '">' +
      '<div class="item-title">' +
      escapeHtml(raceDate) +
      " " +
      escapeHtml(trackName) +
      " " +
      escapeHtml(raceNo) +
      "R " +
      escapeHtml(raceName) +
      " " +
      badge +
      "</div>" +
      '<div class="item-sub muted">' +
      escapeHtml(surface) +
      " " +
      escapeHtml(dist) +
      "m / " +
      escapeHtml(cls) +
      "</div>" +
      "</div>"
    );
  }

  /**
   * sql.js 初期化
   */
  function initSqlJsIfNeeded() {
    if (gSqlJs != null) {
      return Promise.resolve(gSqlJs);
    }

    if (typeof initSqlJs !== "function") {
      return Promise.reject(new Error("sql.js が読み込まれていません。"));
    }

    setText("db-status", "sql.js 初期化中...");

    return initSqlJs({
      locateFile: function (file) {
        // CDN利用時の wasm 解決
        return "https://cdn.jsdelivr.net/npm/sql.js@1.10.3/dist/" + file;
      }
    }).then(function (SQL) {
      gSqlJs = SQL;
      return SQL;
    });
  }

  /**
   * ファイルを ArrayBuffer で読み込む
   */
  function readFileAsArrayBuffer(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        resolve(reader.result);
      };
      reader.onerror = function () {
        reject(reader.error || new Error("FileReader error"));
      };
      reader.readAsArrayBuffer(file);
    });
  }

  /**
   * DBを閉じる
   */
  function closeDb() {
    if (gDb != null) {
      try {
        gDb.close();
      } catch (e) {
        // ignore
      }
      gDb = null;
    }
  }

  /**
   * SQLiteファイルをロードする
   */
  function loadDbFromFile(file) {
    return initSqlJsIfNeeded().then(function (SQL) {
      return readFileAsArrayBuffer(file).then(function (buf) {
        closeDb();

        var u8 = new Uint8Array(buf);
        gDb = new SQL.Database(u8);
        gLoadedFileName = file.name;

        setText("db-status", "ロード完了: " + gLoadedFileName);
        enable("btn-counts", true);
        enable("btn-search", true);
        enable("btn-weekend", true);

        // ついでに初回は週末一覧も押せるようにする
        setText("search-status", "");
        setText("weekend-status", "");
        setText("race-detail", "未選択");
        setText("newspaper", "未選択");
      });
    });
  }

  /**
   * 1本だけ SELECT を実行して rows を返す
   */
  function queryAll(sql, params) {
    if (gDb == null) {
      throw new Error("DBが未ロードです。");
    }

    var stmt = gDb.prepare(sql);
    try {
      if (params && params.length > 0) {
        stmt.bind(params);
      }

      var rows = [];
      while (stmt.step()) {
        rows.push(stmt.get());
      }
      return rows;
    } finally {
      stmt.free();
    }
  }

  /**
   * 件数確認
   */
  function showCounts() {
    var lines = [];

    var tables = [
      "dim_race",
      "fact_race_result",
      "fact_payout",
      "fact_race_entry",
      "fact_race_expectation",
      "dim_horse_pedigree"
    ];

    var i;
    for (i = 0; i < tables.length; i++) {
      var t = tables[i];
      var rows = queryAll("SELECT COUNT(*) FROM " + t + ";", []);
      var cnt = rows.length === 1 ? rows[0][0] : 0;
      lines.push(t + ": " + cnt);
    }

    var weekend = queryAll("SELECT COUNT(*) FROM dim_race WHERE has_entry = 1;", []);
    lines.push("weekend(has_entry=1): " + (weekend.length === 1 ? weekend[0][0] : 0));

    setText("counts-output", lines.join("\n"));
  }

  /**
   * IN句用のプレースホルダを作る
   */
  function buildInPlaceholders(n) {
    var a = [];
    var i;
    for (i = 0; i < n; i++) {
      a.push("?");
    }
    return a.join(",");
  }

  /**
   * 場コードCSVを正規化（'6'→'06'）
   */
  function normalizeJyoCdsCsv(csv) {
    if (!csv) {
      return [];
    }

    var parts = csv.split(",");
    var out = [];
    var i;
    for (i = 0; i < parts.length; i++) {
      var s = parts[i].trim();
      if (s.length === 0) {
        continue;
      }
      if (s.length === 1) {
        s = "0" + s;
      }
      out.push(s);
    }
    return out;
  }

  /**
   * 過去レース検索
   */
  function searchRaces() {
    var from = $("q-from").value;
    var to = $("q-to").value;
    var jyoCsv = $("q-jyo").value;
    var surface = $("q-surface").value;
    var distance = $("q-distance").value;
    var win5Only = $("q-win5").value;

    if (!from || !to) {
      setText("search-status", "期間 From/To を入力してください。");
      return;
    }

    var jyoCds = normalizeJyoCdsCsv(jyoCsv);
    if (jyoCds.length === 0) {
      setText("search-status", "場コードを入力してください（例: 05,06,09）。");
      return;
    }

    var params = [];
    params.push(from);
    params.push(to);

    var inClause = buildInPlaceholders(jyoCds.length);
    var i;
    for (i = 0; i < jyoCds.length; i++) {
      params.push(jyoCds[i]);
    }

    // 任意フィルタ
    var surfaceParam = null;
    if (surface) {
      surfaceParam = surface;
    }
    var distanceParam = null;
    if (distance) {
      distanceParam = Number(distance);
    }
    var win5 = win5Only === "1" ? 1 : 0;

    var sql =
      "SELECT race_id, race_date, track_name, race_no, race_name, surface_type, distance_m, class_simple, win5_flg " +
      "FROM dim_race " +
      "WHERE has_result = 1 " +
      "  AND race_date BETWEEN ? AND ? " +
      "  AND jyo_cd IN (" + inClause + ") ";

    if (surfaceParam != null) {
      sql += " AND surface_type = ? ";
      params.push(surfaceParam);
    }
    if (distanceParam != null && !isNaN(distanceParam)) {
      sql += " AND distance_m = ? ";
      params.push(distanceParam);
    }
    if (win5 === 1) {
      sql += " AND win5_flg = 1 ";
    }

    sql += " ORDER BY race_date DESC, jyo_cd, race_no LIMIT 200;";

    var rows = queryAll(sql, params);

    setText("search-status", "件数: " + rows.length);

    var listEl = $("race-list");
    listEl.innerHTML = "";

    if (rows.length === 0) {
      listEl.innerHTML = '<div class="muted">該当なし</div>';
      return;
    }

    for (i = 0; i < rows.length; i++) {
      listEl.insertAdjacentHTML("beforeend", formatRaceRow(rows[i]));
    }

    // クリックで詳細
    listEl.querySelectorAll(".item").forEach(function (item) {
      item.addEventListener("click", function () {
        var raceId = item.getAttribute("data-race-id");
        showRaceDetail(raceId);
      });
    });
  }

  /**
   * 過去レース詳細（結果 + 払戻）
   */
  function showRaceDetail(raceId) {
    var header = queryAll(
      "SELECT race_date, track_name, race_no, race_name, surface_type, distance_m, class_simple, win5_flg " +
      "FROM dim_race WHERE race_id = ? LIMIT 1;",
      [raceId]
    );

    var titleHtml = "";
    if (header.length === 1) {
      var h = header[0];
      titleHtml =
        "<div class='detail-title'><strong>" +
        escapeHtml(h[0]) + " " +
        escapeHtml(h[1]) + " " +
        escapeHtml(h[2]) + "R " +
        escapeHtml(h[3]) +
        "</strong></div>" +
        "<div class='muted'>" +
        escapeHtml(h[4]) + " " + escapeHtml(h[5]) + "m / " + escapeHtml(h[6]) +
        (h[7] === 1 ? " / WIN5" : "") +
        "</div>";
    } else {
      titleHtml = "<div class='detail-title'><strong>" + escapeHtml(raceId) + "</strong></div>";
    }

    var results = queryAll(
      "SELECT wakuban, umaban, horse_name, finish_pos, time_text, odds, popularity " +
      "FROM fact_race_result WHERE race_id = ? " +
      "ORDER BY finish_pos, umaban;",
      [raceId]
    );

    var payouts = queryAll(
      "SELECT bet_type, combo_text, payout_yen, popularity " +
      "FROM fact_payout WHERE race_id = ? " +
      "ORDER BY bet_type, combo_text;",
      [raceId]
    );

    var html = "";
    html += titleHtml;

    // 結果
    html += "<h4>着順</h4>";
    if (results.length === 0) {
      html += "<div class='muted'>結果なし</div>";
    } else {
      html += "<table class='tbl'><thead><tr>" +
        "<th>着</th><th>枠</th><th>馬</th><th>馬名</th><th>時計</th><th>オッズ</th><th>人気</th>" +
        "</tr></thead><tbody>";
      results.forEach(function (r) {
        html += "<tr>" +
          "<td>" + escapeHtml(r[3]) + "</td>" +
          "<td>" + escapeHtml(r[0]) + "</td>" +
          "<td>" + escapeHtml(r[1]) + "</td>" +
          "<td>" + escapeHtml(r[2]) + "</td>" +
          "<td>" + escapeHtml(r[4]) + "</td>" +
          "<td>" + escapeHtml(r[5]) + "</td>" +
          "<td>" + escapeHtml(r[6]) + "</td>" +
          "</tr>";
      });
      html += "</tbody></table>";
    }

    // 払戻
    html += "<h4>払戻（単複）</h4>";
    if (payouts.length === 0) {
      html += "<div class='muted'>払戻なし</div>";
    } else {
      html += "<table class='tbl'><thead><tr>" +
        "<th>式別</th><th>組番</th><th>払戻</th><th>人気</th>" +
        "</tr></thead><tbody>";
      payouts.forEach(function (p) {
        html += "<tr>" +
          "<td>" + escapeHtml(p[0]) + "</td>" +
          "<td>" + escapeHtml(p[1]) + "</td>" +
          "<td>" + escapeHtml(p[2]) + "</td>" +
          "<td>" + escapeHtml(p[3]) + "</td>" +
          "</tr>";
      });
      html += "</tbody></table>";
    }

    var el = $("race-detail");
    el.classList.remove("muted");
    el.innerHTML = html;
  }

  /**
   * 週末レース一覧（has_entry=1）
   */
  function showWeekendList() {
    var rows = queryAll(
      "SELECT race_id, race_date, track_name, race_no, race_name, surface_type, distance_m, class_simple, win5_flg " +
      "FROM dim_race WHERE has_entry = 1 " +
      "ORDER BY race_date DESC, jyo_cd, race_no;",
      []
    );

    setText("weekend-status", "件数: " + rows.length);

    var listEl = $("weekend-list");
    listEl.innerHTML = "";

    if (rows.length === 0) {
      listEl.innerHTML = '<div class="muted">週末データがありません（has_entry=1 が0件）</div>';
      return;
    }

    var i;
    for (i = 0; i < rows.length; i++) {
      listEl.insertAdjacentHTML("beforeend", formatRaceRow(rows[i]));
    }

    listEl.querySelectorAll(".item").forEach(function (item) {
      item.addEventListener("click", function () {
        var raceId = item.getAttribute("data-race-id");
        showNewspaper(raceId);
      });
    });
  }

  /**
   * 週末新聞（vw_newspaper_rows）
   */
  function showNewspaper(raceId) {
    var header = queryAll(
      "SELECT race_date, track_name, race_no, race_name, surface_type, distance_m, class_simple, win5_flg " +
      "FROM dim_race WHERE race_id = ? LIMIT 1;",
      [raceId]
    );

    var titleHtml = "";
    if (header.length === 1) {
      var h = header[0];
      titleHtml =
        "<div class='detail-title'><strong>" +
        escapeHtml(h[0]) + " " +
        escapeHtml(h[1]) + " " +
        escapeHtml(h[2]) + "R " +
        escapeHtml(h[3]) +
        "</strong></div>" +
        "<div class='muted'>" +
        escapeHtml(h[4]) + " " + escapeHtml(h[5]) + "m / " + escapeHtml(h[6]) +
        (h[7] === 1 ? " / WIN5" : "") +
        "</div>";
    } else {
      titleHtml = "<div class='detail-title'><strong>" + escapeHtml(raceId) + "</strong></div>";
    }

    var rows = queryAll(
      "SELECT wakuban, umaban, horse_name, jockey_name, weight_carried, " +
      "expected_100, ability, mult_course, mult_style, mult_frame, mult_blood, mult_jockey, " +
      "sire, dam, siresire " +
      "FROM vw_newspaper_rows WHERE race_id = ? " +
      "ORDER BY umaban;",
      [raceId]
    );

    var html = "";
    html += titleHtml;

    html += "<h4>競馬新聞</h4>";
    if (rows.length === 0) {
      html += "<div class='muted'>新聞データがありません</div>";
    } else {
      html += "<table class='tbl'><thead><tr>" +
        "<th>枠</th><th>馬</th><th>馬名</th><th>騎手</th><th>斤量</th>" +
        "<th>期待(100)</th><th>能力</th>" +
        "<th>父</th><th>母</th><th>父父</th>" +
        "</tr></thead><tbody>";

      rows.forEach(function (r) {
        html += "<tr>" +
          "<td>" + escapeHtml(r[0]) + "</td>" +
          "<td>" + escapeHtml(r[1]) + "</td>" +
          "<td>" + escapeHtml(r[2]) + "</td>" +
          "<td>" + escapeHtml(r[3]) + "</td>" +
          "<td>" + escapeHtml(r[4]) + "</td>" +
          "<td>" + escapeHtml(r[5]) + "</td>" +
          "<td>" + escapeHtml(r[6]) + "</td>" +
          "<td>" + escapeHtml(r[12]) + "</td>" +
          "<td>" + escapeHtml(r[13]) + "</td>" +
          "<td>" + escapeHtml(r[14]) + "</td>" +
          "</tr>";
      });

      html += "</tbody></table>";
    }

    var el = $("newspaper");
    el.classList.remove("muted");
    el.innerHTML = html;
  }

  function bindEvents() {
    var fileInput = $("sqlite-file");
    var btnLoad = $("btn-load");

    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files.length > 0) {
        enable("btn-load", true);
      } else {
        enable("btn-load", false);
      }
    });

    btnLoad.addEventListener("click", function () {
      if (!fileInput.files || fileInput.files.length === 0) {
        return;
      }

      var file = fileInput.files[0];
      setText("db-status", "読み込み中: " + file.name + " ...");

      loadDbFromFile(file).catch(function (e) {
        console.error(e);
        setText("db-status", "ロード失敗: " + (e && e.message ? e.message : String(e)));
      });
    });

    $("btn-counts").addEventListener("click", function () {
      try {
        showCounts();
      } catch (e) {
        console.error(e);
        setText("counts-output", "エラー: " + (e && e.message ? e.message : String(e)));
      }
    });

    $("btn-search").addEventListener("click", function () {
      try {
        searchRaces();
      } catch (e) {
        console.error(e);
        setText("search-status", "エラー: " + (e && e.message ? e.message : String(e)));
      }
    });

    $("btn-weekend").addEventListener("click", function () {
      try {
        showWeekendList();
      } catch (e) {
        console.error(e);
        setText("weekend-status", "エラー: " + (e && e.message ? e.message : String(e)));
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindEvents();

    // 初期状態
    enable("btn-load", false);
    enable("btn-counts", false);
    enable("btn-search", false);
    enable("btn-weekend", false);

    setText("db-status", "SQLiteファイルを選択してください。");
  });
})();
