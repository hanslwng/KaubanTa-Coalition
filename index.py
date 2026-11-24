"""KaubanTa Coalition site and API. Local run: py index.py"""

import hmac
import os
import re
import smtplib
import sys
from datetime import date, datetime
from email.message import EmailMessage

import certifi
import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "public")
load_dotenv(os.path.join(ROOT, ".env"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.json.ensure_ascii = False

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TABLES = {
    "members",
    "subscribers",
    "rsvps",
    "contact_messages",
    "activities",
    "newsletters",
}
NEEDED_TABLES = TABLES


class ConfigError(Exception):
    pass


def log(message):
    print(message, file=sys.stderr)


def bad(message, code=400):
    return jsonify(error=message), code


def fail(exc):
    log(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, ConfigError):
        return bad("The site database is not set up yet.", 500)
    return bad("Server error. Please try again.", 500)


def val(data, key, limit=255):
    return str(data.get(key, "")).strip()[:limit]


def one_line(value, limit=200):
    return " ".join(str(value).split())[:limit]


def email_ok(value):
    return bool(value) and "\n" not in value and "\r" not in value and bool(EMAIL.match(value))


def phone_ok(value):
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15


def missing_env():
    return [key for key in ("DB_HOST", "DB_USER", "DB_NAME") if not os.environ.get(key)]


def db():
    missing = missing_env()
    if missing:
        raise ConfigError("missing " + ", ".join(missing))
    settings = dict(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=8,
        cursorclass=pymysql.cursors.DictCursor,
    )
    if os.environ.get("DB_SSL", "0") == "1":
        settings["ssl"] = {"ca": certifi.where()}
    return pymysql.connect(**settings)


def rows_to_json(rows):
    converted = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, date):
                item[key] = value.isoformat()
            else:
                item[key] = value
        converted.append(item)
    return converted


def pretty_when(value):
    if isinstance(value, datetime):
        return value.strftime("%a, %b %d, %Y at %I:%M %p")
    return str(value)


def parse_date(value):
    text = str(value).strip()[:10]
    datetime.strptime(text, "%Y-%m-%d")
    return text


def parse_dt(value):
    text = str(value).strip().replace("T", " ")
    if len(text) == 16:
        text += ":00"
    text = text[:19]
    datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    return text


def blank_none(value, limit):
    text = str(value or "").strip()[:limit]
    return text or None


def save(sql, args, duplicate="You're already on the list."):
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute(sql, args)
    except pymysql.err.IntegrityError:
        return bad(duplicate, 409)
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()
    return None


def done(emailed, sent, silent):
    return jsonify(ok=True, message=sent if emailed else silent)


def mail_configured():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("MAIL_FROM"))


def org_to():
    addr = os.environ.get("NOTIFY_EMAIL", "").strip()
    return addr if email_ok(addr) else ""


def deliver(messages):
    pending = [item for item in messages if email_ok(item.get("to", ""))]
    if not mail_configured() or not pending:
        return False
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ["MAIL_FROM"]
    smtp = None
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            smtp = smtplib.SMTP(host, port, timeout=15)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        if user:
            smtp.login(user, password)
        for item in pending:
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = item["to"].strip()
            msg["Subject"] = one_line(item["subject"], 200) or "KaubanTa Coalition"
            reply_to = item.get("reply_to", "")
            if email_ok(reply_to):
                msg["Reply-To"] = reply_to
            msg.set_content(item["body"])
            smtp.send_message(msg)
        return True
    except Exception as exc:
        log(f"email failed: {type(exc).__name__}: {exc}")
        return False
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass


def authorized():
    token = os.environ.get("ADMIN_TOKEN", "")
    sent = request.headers.get("Authorization", "")
    if sent.lower().startswith("bearer "):
        sent = sent[7:].strip()
    if not token or len(sent) != len(token):
        return False
    return hmac.compare_digest(sent, token)


def require_admin():
    if not authorized():
        return bad("Unauthorized", 401)
    return None


def db_hint(exc):
    code = exc.args[0] if getattr(exc, "args", None) else None
    if code == 1045:
        return "The database rejected the username or password."
    if code == 1049:
        return "That database name does not exist. Create it, then run schema.sql."
    if code in (2003, 2005, 2006, 2013):
        return "The app could not reach the database. Check the host, port, and IP allowlist."
    return "The app could not connect to the database."


def public_url(name):
    value = os.environ.get(name, "").strip()
    if value.lower().startswith("https://"):
        return value
    return ""


@app.get("/")
def page_index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/api/health")
def health():
    email_on = mail_configured()
    missing = missing_env()
    if missing:
        return jsonify(
            ok=False,
            database=False,
            email=email_on,
            error="Set " + ", ".join(missing) + " in the environment.",
        ), 500
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            found = set()
            for row in cur.fetchall():
                found.add(next(iter(row.values())))
        missing_tables = sorted(NEEDED_TABLES - found)
        if missing_tables:
            return jsonify(
                ok=False,
                database=False,
                email=email_on,
                error="Connected, but schema.sql has not been fully run. Missing: " + ", ".join(missing_tables),
            ), 500
        return jsonify(ok=True, database=True, email=email_on)
    except ConfigError as exc:
        return jsonify(ok=False, database=False, email=email_on, error=str(exc)), 500
    except Exception as exc:
        log(f"{type(exc).__name__}: {exc}")
        return jsonify(ok=False, database=False, email=email_on, error=db_hint(exc)), 500
    finally:
        if conn:
            conn.close()


@app.get("/api/site")
def site():
    email = os.environ.get("PUBLIC_EMAIL", "").strip()
    phone = os.environ.get("PUBLIC_PHONE", "").strip()
    address = os.environ.get("PUBLIC_ADDRESS", "").strip()
    hours = os.environ.get("PUBLIC_HOURS", "").strip()
    if not hours and (email or phone or address):
        hours = "Mon to Fri, 9 AM to 5 PM"
    return jsonify(
        email=email,
        phone=phone,
        address=address,
        hours=hours,
        facebook=public_url("SOCIAL_FACEBOOK"),
        instagram=public_url("SOCIAL_INSTAGRAM"),
        tiktok=public_url("SOCIAL_TIKTOK"),
        x=public_url("SOCIAL_X"),
        map=public_url("MAP_URL"),
    )


@app.get("/api/activities")
def activities():
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, title, cause, venue, starts_at, slots, description
                   FROM activities ORDER BY starts_at"""
            )
            listing = rows_to_json(cur.fetchall())
            cur.execute(
                """SELECT
                     (SELECT COUNT(*) FROM members) AS volunteers,
                     (SELECT COUNT(*) FROM activities) AS events,
                     (SELECT COUNT(DISTINCT city_province) FROM members
                        WHERE city_province <> '') AS communities"""
            )
            stats = cur.fetchone()
        return jsonify(
            activities=listing,
            stats={
                "volunteers": int(stats["volunteers"]),
                "events": int(stats["events"]),
                "communities": int(stats["communities"]),
            },
        )
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()


@app.get("/api/newsletters")
def newsletters():
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, type, title, period, summary, featured, body, pdf_url, published_at
                   FROM newsletters ORDER BY published_at DESC, id DESC"""
            )
            return jsonify(newsletters=rows_to_json(cur.fetchall()))
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()


@app.post("/api/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = val(data, "n", 150)
    email = val(data, "e", 150).lower()
    mobile = val(data, "m", 30)
    birthday = val(data, "b", 10)
    city = val(data, "c", 150)
    if not (name and city and email_ok(email) and phone_ok(mobile)):
        return bad("Please fill in all required fields.")
    try:
        born = datetime.strptime(birthday, "%Y-%m-%d").date()
    except ValueError:
        return bad("Please check the birthday.")
    if born > date.today() or born.year < 1900:
        return bad("Please check the birthday.")
    if data.get("p") != "1":
        return bad("Please accept the privacy notice.")
    error = save(
        """INSERT INTO members
           (full_name, email, mobile, birthday, school_or_work, city_province,
            interests, availability, heard_from, privacy_consent)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
        (
            name,
            email,
            mobile,
            birthday,
            val(data, "s", 150),
            city,
            val(data, "i"),
            val(data, "a", 50),
            val(data, "h", 50),
        ),
        "This email is already signed up.",
    )
    if error:
        return error
    emailed = deliver(
        [
            {
                "to": email,
                "subject": "You're signed up with KaubanTa Coalition",
                "body": (
                    f"Hi {name},\n\n"
                    "We received your volunteer sign-up. The team will contact you within three days.\n\n"
                    "If you did not sign up, you can ignore this message.\n"
                ),
            },
            {
                "to": org_to(),
                "subject": f"New volunteer sign-up: {name}",
                "reply_to": email,
                "body": (
                    f"Name: {name}\nEmail: {email}\nMobile: {mobile}\nBirthday: {birthday}\n"
                    f"School or work: {val(data, 's', 150)}\nCity: {city}\n"
                    f"Interests: {val(data, 'i')}\nAvailability: {val(data, 'a', 50)}\n"
                    f"Heard from: {val(data, 'h', 50)}\n"
                ),
            },
        ]
    )
    return done(
        emailed,
        "Salamat! We got your sign-up. Check your email for a confirmation.",
        "Salamat! We got your sign-up. We will contact you at this email address.",
    )


@app.post("/api/subscribe")
def subscribe():
    email = val(request.get_json(silent=True) or {}, "e", 150).lower()
    if not email_ok(email):
        return bad("Please enter a valid email.")
    error = save(
        "INSERT INTO subscribers (email) VALUES (%s)",
        (email,),
        "You're already subscribed.",
    )
    if error:
        return error
    emailed = deliver(
        [
            {
                "to": email,
                "subject": "You're subscribed to KaubanTa Coalition",
                "body": "Salamat! You'll get KaubanTa Coalition newsletter updates at this address.\n",
            },
            {
                "to": org_to(),
                "subject": "New newsletter subscriber",
                "reply_to": email,
                "body": f"Email: {email}\n",
            },
        ]
    )
    return done(
        emailed,
        "Salamat! You're subscribed. Watch your inbox.",
        "Salamat! You're subscribed.",
    )


@app.post("/api/rsvp")
def rsvp():
    data = request.get_json(silent=True) or {}
    name = val(data, "n", 150)
    email = val(data, "e", 150).lower()
    mobile = val(data, "m", 30)
    try:
        activity_id = int(data.get("activity_id"))
    except (TypeError, ValueError):
        return bad("Invalid activity.")
    if not name or not email_ok(email):
        return bad("Please enter your name and a valid email.")
    if mobile and not phone_ok(mobile):
        return bad("Please enter a valid contact number.")
    conn = None
    activity = None
    try:
        conn = db()
        conn.autocommit(False)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE activities SET slots = slots - 1 WHERE id=%s AND slots > 0",
                (activity_id,),
            )
            if cur.rowcount != 1:
                cur.execute("SELECT id FROM activities WHERE id=%s", (activity_id,))
                found = cur.fetchone()
                conn.rollback()
                if not found:
                    return bad("This activity is no longer available.")
                return bad("This activity is full.")
            cur.execute(
                "INSERT INTO rsvps (activity_id, name, email, mobile) VALUES (%s,%s,%s,%s)",
                (activity_id, name, email, mobile),
            )
            cur.execute(
                "SELECT title, venue, starts_at, description FROM activities WHERE id=%s",
                (activity_id,),
            )
            activity = cur.fetchone()
        conn.commit()
    except pymysql.err.IntegrityError:
        if conn:
            conn.rollback()
        return bad("You already RSVPed to this activity.", 409)
    except Exception as exc:
        if conn:
            conn.rollback()
        return fail(exc)
    finally:
        if conn:
            conn.close()

    title = activity["title"] if activity else "the activity"
    when = pretty_when(activity["starts_at"]) if activity else ""
    venue = activity["venue"] if activity else ""
    description = (activity["description"] or "") if activity else ""
    emailed = deliver(
        [
            {
                "to": email,
                "subject": f"You're in for {title}",
                "body": (
                    f"Hi {name},\n\nYou're confirmed for {title}.\n"
                    f"When: {when}\nWhere: {venue}\n{description}\n\n"
                    "Save this email and bring it when you arrive.\n"
                ),
            },
            {
                "to": org_to(),
                "subject": f"New RSVP: {title}",
                "reply_to": email,
                "body": f"Activity: {title}\nName: {name}\nEmail: {email}\nMobile: {mobile}\n",
            },
        ]
    )
    return done(
        emailed,
        f"You're in for {title}. We sent the details to your email.",
        f"You're in for {title}. Save the details shown on this page.",
    )


@app.post("/api/contact")
def contact():
    data = request.get_json(silent=True) or {}
    if val(data, "hp"):
        return jsonify(ok=True, message="Message sent. Salamat! We'll reply soon.")
    name = val(data, "n", 150)
    email = val(data, "e", 150).lower()
    subject = val(data, "s", 50)
    message = val(data, "msg", 5000)
    if not (name and subject and message and email_ok(email)):
        return bad("Please fill in all fields.")
    error = save(
        "INSERT INTO contact_messages (name, email, subject, message) VALUES (%s,%s,%s,%s)",
        (name, email, subject, message),
    )
    if error:
        return error
    emailed = deliver(
        [
            {
                "to": email,
                "subject": "We got your message",
                "body": (
                    f"Hi {name},\n\nWe received your message about \"{one_line(subject, 80)}\". "
                    "We'll reply within two working days.\n"
                ),
            },
            {
                "to": org_to(),
                "subject": f"Contact form: {subject}",
                "reply_to": email,
                "body": f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\n{message}\n",
            },
        ]
    )
    return done(
        emailed,
        "Message sent. Salamat! We'll reply soon.",
        "Message sent. Salamat! We'll reply soon.",
    )


@app.get("/api/admin/<table>")
def admin_table(table):
    denied = require_admin()
    if denied:
        return denied
    if table not in TABLES:
        return bad("Not found", 404)
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 500")
            return jsonify(rows_to_json(cur.fetchall()))
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()


@app.post("/api/admin/activities")
def admin_add_activity():
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    title = val(data, "title", 200)
    cause = val(data, "cause", 50)
    venue = val(data, "venue", 200)
    if not (title and cause and venue):
        return bad("Please fill in the title, cause, and venue.")
    try:
        starts = parse_dt(data.get("starts_at", ""))
    except ValueError:
        return bad("Enter a valid date and time.")
    try:
        slots = int(data.get("slots"))
    except (TypeError, ValueError):
        return bad("Enter the number of slots.")
    if slots < 0 or slots > 10000:
        return bad("Slots must be between 0 and 10000.")
    error = save(
        """INSERT INTO activities (title, cause, venue, starts_at, slots, description)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (title, cause, venue, starts, slots, val(data, "description", 5000)),
    )
    if error:
        return error
    return jsonify(ok=True)


@app.delete("/api/admin/activities/<int:activity_id>")
def admin_delete_activity(activity_id):
    denied = require_admin()
    if denied:
        return denied
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM activities WHERE id=%s", (activity_id,))
            if cur.rowcount != 1:
                return bad("Activity not found.", 404)
        return jsonify(ok=True)
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()


@app.post("/api/admin/newsletters")
def admin_add_newsletter():
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    kind = val(data, "type", 20)
    title = val(data, "title", 200)
    body = val(data, "body", 20000)
    if kind not in {"weekly", "monthly"}:
        return bad("Choose weekly or monthly.")
    if not title or not body:
        return bad("Please fill in the title and the body.")
    try:
        published = parse_date(data.get("published_at", ""))
    except ValueError:
        return bad("Enter a valid publish date.")
    pdf = val(data, "pdf_url", 255)
    if pdf and not pdf.lower().startswith("https://"):
        return bad("The PDF link must start with https://")
    error = save(
        """INSERT INTO newsletters
           (type, title, period, summary, featured, body, pdf_url, published_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            kind,
            title,
            blank_none(data.get("period"), 80),
            blank_none(data.get("summary"), 300),
            blank_none(data.get("featured"), 300),
            body,
            pdf or None,
            published,
        ),
    )
    if error:
        return error
    return jsonify(ok=True)


@app.delete("/api/admin/newsletters/<int:newsletter_id>")
def admin_delete_newsletter(newsletter_id):
    denied = require_admin()
    if denied:
        return denied
    conn = None
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM newsletters WHERE id=%s", (newsletter_id,))
            if cur.rowcount != 1:
                return bad("Newsletter not found.", 404)
        return jsonify(ok=True)
    except Exception as exc:
        return fail(exc)
    finally:
        if conn:
            conn.close()


@app.errorhandler(404)
def missing(_err):
    if request.path.startswith("/api/"):
        return bad("Not found", 404)
    return "Not found", 404


@app.errorhandler(413)
def too_large(_err):
    return bad("That submission is too long.", 413)


if __name__ == "__main__":
    missing = missing_env()
    if missing:
        log("Database is not configured. Set " + ", ".join(missing) + " in .env")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
