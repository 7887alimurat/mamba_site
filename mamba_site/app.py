import os
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, render_template, g, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mamba.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB (для видео-обоев)

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

DEFAULT_SETTINGS = {
    "user_name": "Mamba",
    "greeting": "Добро пожаловать",
    "lms_link": "https://lms.astanait.edu.kz",
    "mydu_link": "https://my-du.astanait.edu.kz",
    "instagram": "",
    "tiktok": "",
    "youtube": "",
    "telegram": "",
    "github_profile": "",  # ссылка на твой GitHub-аккаунт (показывается на Главной)
    "home_photo": "",  # ячейка "фото" на Главной
    "home_gif_1": "",  # ячейка "gif 1" на Главной
    "home_gif_2": "",  # ячейка "gif 2" на Главной
    "sidebar_media": "",  # медиа в свободном месте боковой панели
    "background_type": "color",   # color | image | gif | video
    "background_value": "",       # путь к файлу или hex-цвет
    "accent": "#3ECF8E",
}


# ---------------------------------------------------------------- database

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,          -- 0 = Пн ... 6 = Вс
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            kind TEXT DEFAULT ''                -- лекция / практика / лаб и т.д.
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT DEFAULT '',
            deadline TEXT NOT NULL,             -- ISO datetime
            link TEXT DEFAULT '',
            done INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS planner (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,                 -- YYYY-MM-DD
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            description TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            github_link TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    cur = db.execute("SELECT COUNT(*) FROM settings")
    if cur.fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            list(DEFAULT_SETTINGS.items()),
        )
    db.commit()
    db.close()


# ----------------------------------------------------------------- helpers

def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


def get_all_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    for r in rows:
        settings[r["key"]] = r["value"]
    return settings


def next_deadline_info(settings=None):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM assignments WHERE done = 0 ORDER BY deadline ASC"
    ).fetchall()
    return [row_to_dict(r) for r in rows]


# -------------------------------------------------------------- page routes

@app.route("/")
def page_index():
    settings = get_all_settings()
    today = datetime.now().strftime("%Y-%m-%d")
    db = get_db()
    plans = db.execute(
        "SELECT * FROM planner WHERE date = ? ORDER BY sort_order ASC, time_start ASC",
        (today,),
    ).fetchall()
    deadlines = db.execute(
        "SELECT * FROM assignments WHERE done = 0 ORDER BY deadline ASC LIMIT 5"
    ).fetchall()
    projects = db.execute(
        "SELECT * FROM portfolio ORDER BY sort_order ASC, id DESC LIMIT 3"
    ).fetchall()
    weekday_today = datetime.now().weekday()
    today_pairs = db.execute(
        "SELECT * FROM schedule WHERE weekday = ? ORDER BY time_start ASC",
        (weekday_today,),
    ).fetchall()
    return render_template(
        "index.html",
        settings=settings,
        plans=plans,
        deadlines=deadlines,
        projects=projects,
        today_pairs=today_pairs,
        today_label=today,
    )


@app.route("/schedule")
def page_schedule():
    settings = get_all_settings()
    db = get_db()
    rows = db.execute(
        "SELECT * FROM schedule ORDER BY weekday ASC, time_start ASC"
    ).fetchall()
    by_day = {i: [] for i in range(7)}
    for r in rows:
        by_day[r["weekday"]].append(row_to_dict(r))
    deadlines = db.execute(
        "SELECT * FROM assignments ORDER BY done ASC, deadline ASC"
    ).fetchall()
    return render_template(
        "schedule.html",
        settings=settings,
        by_day=by_day,
        weekdays=WEEKDAYS,
        deadlines=deadlines,
    )


@app.route("/planner")
def page_planner():
    settings = get_all_settings()
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    db = get_db()
    plans = db.execute(
        "SELECT * FROM planner WHERE date = ? ORDER BY sort_order ASC, time_start ASC",
        (date,),
    ).fetchall()
    return render_template(
        "planner.html", settings=settings, plans=plans, date=date
    )


@app.route("/portfolio")
def page_portfolio():
    settings = get_all_settings()
    db = get_db()
    projects = db.execute(
        "SELECT * FROM portfolio ORDER BY sort_order ASC, id DESC"
    ).fetchall()
    return render_template("portfolio.html", settings=settings, projects=projects)


@app.route("/social")
def page_social():
    settings = get_all_settings()
    return render_template("social.html", settings=settings)


@app.route("/settings")
def page_settings():
    settings = get_all_settings()
    uploads = []
    if os.path.isdir(UPLOAD_DIR):
        uploads = sorted(os.listdir(UPLOAD_DIR), reverse=True)
    return render_template("settings.html", settings=settings, uploads=uploads)


# --------------------------------------------------------------- API: settings

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    db = get_db()
    if request.method == "GET":
        return jsonify(get_all_settings())
    data = request.get_json(force=True) or {}
    for key, value in data.items():
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    db.commit()
    return jsonify(get_all_settings())


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "Файл не найден"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Пустое имя файла"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Недопустимый формат файла"}), 400
    fname = f"{uuid.uuid4().hex}.{ext}"
    fname = secure_filename(fname)
    file.save(os.path.join(UPLOAD_DIR, fname))
    kind = "video" if ext in {"mp4", "webm", "mov"} else ("gif" if ext == "gif" else "image")
    return jsonify({"path": f"/static/uploads/{fname}", "kind": kind})


# --------------------------------------------------------------- API: schedule

@app.route("/api/schedule", methods=["GET", "POST"])
def api_schedule():
    db = get_db()
    if request.method == "GET":
        rows = db.execute("SELECT * FROM schedule ORDER BY weekday, time_start").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    d = request.get_json(force=True)
    cur = db.execute(
        "INSERT INTO schedule (weekday, time_start, time_end, subject, room, teacher, kind) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            d.get("weekday", 0),
            d.get("time_start", ""),
            d.get("time_end", ""),
            d.get("subject", ""),
            d.get("room", ""),
            d.get("teacher", ""),
            d.get("kind", ""),
        ),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid})


@app.route("/api/schedule/<int:item_id>", methods=["PUT", "DELETE"])
def api_schedule_item(item_id):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM schedule WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    d = request.get_json(force=True)
    db.execute(
        "UPDATE schedule SET weekday=?, time_start=?, time_end=?, subject=?, room=?, "
        "teacher=?, kind=? WHERE id=?",
        (
            d.get("weekday", 0),
            d.get("time_start", ""),
            d.get("time_end", ""),
            d.get("subject", ""),
            d.get("room", ""),
            d.get("teacher", ""),
            d.get("kind", ""),
            item_id,
        ),
    )
    db.commit()
    return jsonify({"ok": True})


# ------------------------------------------------------------- API: assignments

@app.route("/api/assignments", methods=["GET", "POST"])
def api_assignments():
    db = get_db()
    if request.method == "GET":
        rows = db.execute("SELECT * FROM assignments ORDER BY done ASC, deadline ASC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    d = request.get_json(force=True)
    cur = db.execute(
        "INSERT INTO assignments (title, subject, deadline, link, done) VALUES (?, ?, ?, ?, 0)",
        (d.get("title", ""), d.get("subject", ""), d.get("deadline", ""), d.get("link", "")),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid})


@app.route("/api/assignments/<int:item_id>", methods=["PUT", "DELETE"])
def api_assignment_item(item_id):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM assignments WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    d = request.get_json(force=True)
    fields, values = [], []
    for key in ("title", "subject", "deadline", "link", "done"):
        if key in d:
            fields.append(f"{key} = ?")
            values.append(d[key])
    if fields:
        values.append(item_id)
        db.execute(f"UPDATE assignments SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- API: planner

@app.route("/api/planner", methods=["GET", "POST"])
def api_planner():
    db = get_db()
    if request.method == "GET":
        date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
        rows = db.execute(
            "SELECT * FROM planner WHERE date = ? ORDER BY sort_order ASC, time_start ASC",
            (date,),
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    d = request.get_json(force=True)
    cur = db.execute(
        "INSERT INTO planner (date, time_start, time_end, description, done, sort_order) "
        "VALUES (?, ?, ?, ?, 0, ?)",
        (
            d.get("date", datetime.now().strftime("%Y-%m-%d")),
            d.get("time_start", ""),
            d.get("time_end", ""),
            d.get("description", ""),
            d.get("sort_order", 0),
        ),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid})


@app.route("/api/planner/<int:item_id>", methods=["PUT", "DELETE"])
def api_planner_item(item_id):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM planner WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    d = request.get_json(force=True)
    fields, values = [], []
    for key in ("date", "time_start", "time_end", "description", "done", "sort_order"):
        if key in d:
            fields.append(f"{key} = ?")
            values.append(d[key])
    if fields:
        values.append(item_id)
        db.execute(f"UPDATE planner SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------- API: portfolio

@app.route("/api/portfolio", methods=["GET", "POST"])
def api_portfolio():
    db = get_db()
    if request.method == "GET":
        rows = db.execute("SELECT * FROM portfolio ORDER BY sort_order ASC, id DESC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    d = request.get_json(force=True)
    cur = db.execute(
        "INSERT INTO portfolio (title, description, github_link, tags, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            d.get("title", ""),
            d.get("description", ""),
            d.get("github_link", ""),
            d.get("tags", ""),
            d.get("sort_order", 0),
        ),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid})


@app.route("/api/portfolio/<int:item_id>", methods=["PUT", "DELETE"])
def api_portfolio_item(item_id):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM portfolio WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    d = request.get_json(force=True)
    fields, values = [], []
    for key in ("title", "description", "github_link", "tags", "sort_order"):
        if key in d:
            fields.append(f"{key} = ?")
            values.append(d[key])
    if fields:
        values.append(item_id)
        db.execute(f"UPDATE portfolio SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
