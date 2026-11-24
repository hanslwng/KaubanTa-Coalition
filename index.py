import os, re, hmac
import pymysql, certifi
from flask import Flask, request, jsonify

app = Flask(__name__)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def db():
    return pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 4000)),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], ssl={"ca": certifi.where()},
        charset="utf8mb4", autocommit=True, connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor)

def bad(msg, code=400):
    return jsonify(error=msg), code

def val(d, k, n=255):
    return str(d.get(k, "")).strip()[:n]

def save(sql, args, dup="You’re already on the list."):
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute(sql, args)
    except pymysql.err.IntegrityError:
        return bad(dup, 409)
    except Exception:
        return bad("Server error. Please try again.", 500)
    finally:
        if conn: conn.close()
    return jsonify(ok=True)

@app.post("/api/signup")
def signup():
    d = request.get_json(silent=True) or {}
    n, e, m, b, c = val(d,"n",150), val(d,"e",150).lower(), val(d,"m",30), val(d,"b",10), val(d,"c",150)
    if not (n and m and b and c and EMAIL.match(e)): return bad("Please fill in all required fields.")
    if d.get("p") != "1": return bad("Please accept the privacy notice.")
    return save("""INSERT INTO members (full_name,email,mobile,birthday,school_or_work,city_province,
        interests,availability,heard_from,privacy_consent) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
        (n,e,m,b,val(d,"s",150),c,val(d,"i"),val(d,"a",50),val(d,"h",50)),
        "This email is already signed up.")

@app.post("/api/subscribe")
def subscribe():
    e = val(request.get_json(silent=True) or {}, "e", 150).lower()
    if not EMAIL.match(e): return bad("Please enter a valid email.")
    return save("INSERT INTO subscribers (email) VALUES (%s)", (e,), "You’re already subscribed.")

@app.post("/api/rsvp")
def rsvp():
    d = request.get_json(silent=True) or {}
    n, e = val(d,"n",150), val(d,"e",150).lower()
    try: aid = int(d.get("activity_id"))
    except (TypeError, ValueError): return bad("Invalid activity.")
    if not (n and EMAIL.match(e)): return bad("Please enter your name and a valid email.")
    return save("INSERT INTO rsvps (activity_id,name,email,mobile) SELECT id,%s,%s,%s FROM activities WHERE id=%s",
        (n,e,val(d,"m",30),aid), "You already RSVPed to this activity.")

@app.post("/api/contact")
def contact():
    d = request.get_json(silent=True) or {}
    if val(d, "hp"): return jsonify(ok=True)  # honeypot: bots fill this
    n, e, s, msg = val(d,"n",150), val(d,"e",150).lower(), val(d,"s",50), val(d,"msg",5000)
    if not (n and s and msg and EMAIL.match(e)): return bad("Please fill in all fields.")
    return save("INSERT INTO contact_messages (name,email,subject,message) VALUES (%s,%s,%s,%s)", (n,e,s,msg))

@app.get("/api/admin/<table>")
def admin(table):
    token = os.environ.get("ADMIN_TOKEN", "")
    sent = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token or not hmac.compare_digest(sent, token): return bad("Unauthorized", 401)
    if table not in {"members","subscribers","rsvps","contact_messages"}: return bad("Not found", 404)
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 500")
            return jsonify(cur.fetchall())
    finally:
        conn.close()
