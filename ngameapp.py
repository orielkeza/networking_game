# ngameapp.py — minimal, Mongo-free game server with optional Snowflake integration
from flask import Flask, request, jsonify, render_template
from networking_game import Game, User
from snowflake_client import sf_complete  # <-- FIX 1: correct import
import os, json

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Game bootstrap (in-memory) ---
game = Game()
CURRENT_USER = "Player-001"                  # anonymized demo user
user = game.register_user(CURRENT_USER)
game.assign_daily_tasks(user, num_tasks=2)
game.assign_weekly_tasks(user, num_tasks=1)

# --- Helpers ---
def add_points(u: User, pts: int):
    u.points += int(max(0, pts))
    game._update_level(u)

# --- Minimal persistence to file (optional) ---
SAVE_PATH = "save.json"

def save_all():
    try:
        game.save(SAVE_PATH)
    except Exception:
        pass

def load_all():
    try:
        if os.path.exists(SAVE_PATH):
            game.load(SAVE_PATH)
    except Exception:
        pass

# --- Pages ---
@app.route("/game")
def game_page():
    return render_template("game.html")

@app.route("/")
def root():
    return render_template("game.html")

# --- State & tasks ---
@app.route("/get_state", methods=["GET"])
def get_state():
    return jsonify(user.to_dict())

@app.route("/complete_task", methods=["POST"])
def complete_task():
    data = request.get_json(silent=True) or {}
    tid = data.get("taskId")
    try:
        game.complete_task(user, tid)
        save_all()
        return jsonify({"ok": True, "points": user.points})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- Leaderboard (seed anonymized competitors so board isn't empty) ---
@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    for alias, pts in [("Nova-A12", 220), ("Lyra-K5", 180), ("Orion-M3", 160)]:
        if alias not in game.users:
            uu = game.register_user(alias)
            uu.points = pts
            game._update_level(uu)

    rows = game.get_leaderboard(top_n=10)  # [{'username':..., 'points':...}]
    with_rank = [{"rank": i + 1, **r} for i, r in enumerate(rows)]
    return jsonify(with_rank)

# ======== Local heuristic fallback (keeps demo usable if Snowflake fails) ========
def _heuristic_score(qtype: str, text: str, choice: str = ""):
    s, tips = 0, []
    t = (text or "").lower().strip()
    ch = (choice or "").lower().strip()

    def has_any(kws): return any(k in t for k in kws)

    if qtype == "outreach":
        if len(t.split()) >= 30: s += 1
        if has_any(["accessibility","design","los angeles"," la ","ux"]): s += 2
        if has_any(["i'm","i am","student","engineer","uwaterloo","cs"]): s += 2
        if has_any(["15","15-min","15 minute","15 minutes"]): s += 2
        if has_any(["thanks","appreciate","understand if not","no worries","totally fine if not"]): s += 3
        if s < 10:
            tips += [
                "Reference their work/location directly (e.g., “your accessibility case study in LA”).",
                "Make a specific, time-boxed ask (e.g., 15 minutes next week).",
                "Add a respectful opt-out line."
            ]
    elif qtype == "coffee":
        qs = [q.strip("-• ").strip() for q in text.split("\n") if q.strip()]
        if 2 <= len(qs) <= 4: s += 3
        if any(q.endswith("?") for q in qs): s += 3
        if any(k in " ".join(qs).lower() for k in ["roadmap","a/b","experiment","tradeoff","stakeholder","impact"]): s += 2
        if len(set([q.split()[0].lower() if q else "" for q in qs])) > 1: s += 2
        if s < 10:
            tips += ["Ask ≤3 open-ended, product-specific questions (e.g., trade-offs, experiment design)."]
    elif qtype == "followup":
        if ch in ["monday","tuesday","48h","2 days","early next week"]: s += 3
        if any(k in t for k in ["thanks","great meeting","appreciate"]): s += 2
        if s < 5:
            tips += ["Follow up within 48–72 hours (e.g., Monday). Keep the subject clear and short."]
    elif qtype == "reciprocity":
        if any(k in t for k in ["share","resource","intro","connect","notes","feedback","link"]): s += 3
        if len(t.split()) >= 10: s += 2
        if s < 5:
            tips += ["Offer something concrete: relevant article, intro, or feedback summary."]

    return max(0, min(s, 10)), tips

# ======== Snowflake-powered endpoints ========
@app.route("/quest/start", methods=["POST"])
def quest_start():
    d = request.get_json(silent=True) or {}
    qtype = d.get("type", "outreach")

    # Build a single prompt string (FIX 2: no messages list)
    prompt = (
        "System: Generate a realistic, concise 2–3 sentence practice scenario for student networking. "
        "Return JSON only as: {\"prompt\":\"...\"}.\n\n"
        f"User: TASK={qtype}. Audience: student networking practice."
    )

    try:
        content = sf_complete(prompt)  # returns string
        obj = json.loads(content) if content.strip().startswith("{") else {}
        prompt_out = obj.get("prompt") or "You’re a student reaching out to a mentor about their recent project."
        source = "snowflake"
    except Exception:
        prompt_out = "You’re a student reaching out to a mentor about their recent project."
        source = "local"

    return jsonify({"type": qtype, "scenario": {"prompt": prompt_out}, "source": source})

@app.route("/quest/score", methods=["POST"])
def quest_score():
    d = request.get_json(silent=True) or {}
    qtype  = d.get("type", "outreach")
    text   = d.get("text", "")
    choice = d.get("choice", "")

    rubric = (
        "Return JSON exactly: {\"score\": <0-10>, \"tips\": [\"tip1\",\"tip2\"]}.\n"
        "Rubrics:\n"
        "- outreach: personalization(2), clarity(2), specific ask(3), respectful tone/opt-out(3).\n"
        "- coffee: relevance(3), open-ended(3), depth(2), variety(2).\n"
        "- followup: timing(3), subject clarity(2).\n"
        "- reciprocity: actionable(3), appropriate(2).\n"
    )
    prompt = (
        "System: You are a concise networking coach. Reply with compact JSON only.\n\n"
        f"User:\nTask={qtype}\nText:\n{text}\nChoice:{choice}\n{rubric}"
    )

    used_snowflake = True
    try:
        content = sf_complete(prompt)
        obj = json.loads(content) if content.strip().startswith("{") else {}
        score = int(obj.get("score", 0))
        tips  = (obj.get("tips") or [])[:2]
    except Exception:
        used_snowflake = False
        score, tips = _heuristic_score(qtype, text, choice)
        if not tips:
            tips = ["(Snowflake offline) Be specific about why you’re reaching out.",
                    "Make a 15-min time-boxed ask."]

    score = max(0, min(score, 10))
    add_points(user, score)
    save_all()

    rows = game.get_leaderboard(top_n=10)
    leaderboard_rows = [{"rank": i + 1, **r} for i, r in enumerate(rows)]

    return jsonify({
        "earned": score,
        "tips": tips,
        "leaderboard": leaderboard_rows,
        "points": user.points,
        "source": "snowflake" if used_snowflake else "local"
    })

@app.route("/coach/chat", methods=["POST"])
def coach_chat():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()

    prompt = (
        "System: You are a practical networking coach. Answer in 2–4 concise sentences with concrete examples. Avoid fluff.\n\n"
        f"User: {user_text}"
    )
    try:
        reply = sf_complete(prompt) or "Try again with one specific situation."
        source = "snowflake"
    except Exception:
        reply = "Snowflake is busy—try again shortly. Tip: include a concrete detail and a 15-min ask."
        source = "local"

    return jsonify({"reply": reply, "source": source})

@app.route("/quest/rewrite", methods=["POST"])
def quest_rewrite():
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()

    prompt = (
        "System: Rewrite the message into 2–4 tight, friendly sentences. "
        "Keep it specific and include a 15-minute time-boxed ask. "
        "Return JSON exactly as {\"text\":\"...\"}.\n\n"
        f"User: {text}"
    )
    try:
        content = sf_complete(prompt)
        if content.strip().startswith("{"):
            obj = json.loads(content)
            new_text = (obj.get("text") or "").strip()
        else:
            # If model returned plain text, accept it
            new_text = content.strip()
        if not new_text:
            new_text = text  # safety
        source = "snowflake"
    except Exception:
        new_text = text  # FIX 3: fallback returns original, not empty
        source = "local"

    return jsonify({"text": new_text, "source": source})

# --- Health endpoint to verify Snowflake connectivity (optional) ---
@app.get("/_snowflake_health")
def snowflake_health():
    try:
        out = sf_complete("Reply with the single word: OK.")
        return jsonify({"ok": True, "sample": out[:80]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# --- load saved progress on boot ---
load_all()

# --- main ---
if __name__ == "__main__":
    # Optional banner so you can see env vars are present
    print("=== Snowflake config ===")
    print("BASE  :", os.environ.get("SNOWFLAKE_BASE","(missing)"))
    print("MODEL :", os.environ.get("SNOWFLAKE_MODEL","(missing)"))
    tok = os.environ.get("SNOWFLAKE_API_TOKEN")
    print("TOKEN :", ("set, len="+str(len(tok)) if tok else "(missing)"))
    print("========================")
    app.run(debug=True)