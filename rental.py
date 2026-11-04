from flask import request, redirect, session
from markupsafe import escape
from app import app, connect
from datetime import datetime, timedelta

def init_rental():
    db = connect()

    db.execute("""
    CREATE TABLE IF NOT EXISTS rental_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        hours INTEGER,
        price INTEGER
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS rentals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tool_id INTEGER,
        plan_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending_activation',
        created_at TEXT,
        started_at TEXT,
        expires_at TEXT
    )
    """)

    plans = [
        ("1 Hora", 1, 50),
        ("6 Horas", 6, 150),
        ("12 Horas", 12, 250),
        ("24 Horas", 24, 400)
    ]

    for plan in plans:
        db.execute("""
        INSERT OR IGNORE INTO rental_plans
        (name, hours, price) VALUES (?, ?, ?)
        """, plan)

    db.commit()
    db.close()


def approved_client():
    if "user_id" not in session:
        return False

    db = connect()
    user = db.execute(
        "SELECT status, role FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    db.close()

    return bool(
        user and user["status"] == "approved"
        and user["role"] == "client"
    )


@app.route("/rental")
def rental_page():
    if not approved_client():
        return redirect("/login")

    db = connect()

    tools = db.execute("""
        SELECT * FROM gsm_tools
        WHERE active=1
    """).fetchall()

    plans = db.execute("""
        SELECT * FROM rental_plans
        ORDER BY hours
    """).fetchall()

    user = db.execute(
        "SELECT balance FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    db.close()

    html = f"""
    <h2>ALUGUER GSM</h2>
    <h3>Carteira: {user['balance']} MT</h3>
    """

    for tool in tools:
        html += f"""
        <div class="box">
        <h3>{escape(tool['name'])}</h3>
        <form method="POST" action="/rental/request">
        <input type="hidden" name="tool_id"
        value="{tool['id']}">
        <select name="plan_id" required>
        """

        for plan in plans:
            html += f"""
            <option value="{plan['id']}">
            {escape(plan['name'])} - {plan['price']} MT
            </option>
            """

        html += """
        </select>
        <br><button>ALUGAR AGORA</button>
        </form>
        </div>
        """

    html += '<a href="/dashboard">Voltar ao painel</a>'

    return f"""
    <html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body {{background:#080d1b;color:white;font-family:Arial;
    text-align:center;padding:15px}}
    .box {{background:#14213d;padding:20px;margin:15px auto;
    border-radius:12px;max-width:400px}}
    select,button {{padding:13px;margin:10px;width:90%}}
    button {{background:#00bfff;color:white;border:0}}
    </style></head>
    <body>
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {html}
    </body></html>
    """


@app.route("/rental/request", methods=["POST"])
def rental_request():
    if not approved_client():
        return redirect("/login")

    try:
        tool_id = int(request.form["tool_id"])
        plan_id = int(request.form["plan_id"])
    except (ValueError, KeyError):
        return "Dados inválidos.", 400

    db = connect()

    try:
        db.execute("BEGIN IMMEDIATE")

        tool = db.execute("""
            SELECT * FROM gsm_tools
            WHERE id=? AND active=1
        """, (tool_id,)).fetchone()

        plan = db.execute("""
            SELECT * FROM rental_plans WHERE id=?
        """, (plan_id,)).fetchone()

        user = db.execute("""
            SELECT balance FROM users WHERE id=?
        """, (session["user_id"],)).fetchone()

        if not tool or not plan or not user:
            db.rollback()
            return "Ferramenta ou plano não encontrado.", 404

        if user["balance"] < plan["price"]:
            db.rollback()
            return "Saldo insuficiente. Adicione créditos."

        db.execute("""
            UPDATE users SET balance=balance-?
            WHERE id=?
        """, (plan["price"], session["user_id"]))

        db.execute("""
            INSERT INTO transactions
            (user_id, amount, description)
            VALUES (?, ?, ?)
        """, (
            session["user_id"],
            -plan["price"],
            "Pedido de aluguer: " + tool["name"]
        ))

        db.execute("""
            INSERT INTO rentals
            (user_id, tool_id, plan_id, amount, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            tool_id,
            plan_id,
            plan["price"],
            datetime.utcnow().isoformat()
        ))

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return redirect("/my-rentals")


@app.route("/my-rentals")
def my_rentals():
    if not approved_client():
        return redirect("/login")

    db = connect()

    rentals = db.execute("""
        SELECT rentals.*, gsm_tools.name, rental_plans.hours
        FROM rentals
        JOIN gsm_tools ON gsm_tools.id=rentals.tool_id
        JOIN rental_plans ON rental_plans.id=rentals.plan_id
        WHERE rentals.user_id=?
        ORDER BY rentals.id DESC
    """, (session["user_id"],)).fetchall()

    db.close()

    html = "<h2>OS MEUS ALUGUERES</h2>"

    for r in rentals:
        status = r["status"]

        if status == "active" and r["expires_at"]:
            expires = datetime.fromisoformat(r["expires_at"])
            if datetime.utcnow() >= expires:
                status = "expired"

        html += f"""
        <div class="box">
        <h3>{escape(r['name'])}</h3>
        <p>Duração: {r['hours']} horas</p>
        <p>Valor: {r['amount']} MT</p>
        <p>Estado: {escape(status)}</p>
        <p>Expira: {escape(r['expires_at'] or 'A aguardar ativação')}</p>
        </div>
        """

    html += '<a href="/rental">Novo aluguer</a>'

    return f"""
    <html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body {{background:#080d1b;color:white;font-family:Arial;
    text-align:center;padding:15px}}
    .box {{background:#14213d;padding:18px;margin:15px auto;
    border-radius:12px;max-width:400px}}
    a {{color:#00bfff}}
    </style></head>
    <body>
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {html}
    </body></html>
    """


@app.route("/admin/rentals")
def admin_rentals():
    if "user_id" not in session or session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()

    rentals = db.execute("""
        SELECT rentals.*, users.username,
        gsm_tools.name, rental_plans.hours
        FROM rentals
        JOIN users ON users.id=rentals.user_id
        JOIN gsm_tools ON gsm_tools.id=rentals.tool_id
        JOIN rental_plans ON rental_plans.id=rentals.plan_id
        ORDER BY rentals.id DESC
    """).fetchall()

    db.close()

    html = "<h2>GESTÃO DE ALUGUERES</h2>"

    for r in rentals:
        html += f"""
        <div class="box">
        <h3>{escape(r['name'])}</h3>
        <p>Cliente: {escape(r['username'])}</p>
        <p>Duração: {r['hours']} horas</p>
        <p>Valor: {r['amount']} MT</p>
        <p>Estado: {escape(r['status'])}</p>
        """

        if r["status"] == "pending_activation":
            html += f"""
            <form method="POST" action="/admin/rental/activate/{r['id']}">
            <button>ATIVAR ALUGUER</button>
            </form>
            <form method="POST" action="/admin/rental/refund/{r['id']}">
            <button>RECUSAR E DEVOLVER CRÉDITOS</button>
            </form>
            """

        html += "</div>"

    return f"""
    <html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body {{background:#080d1b;color:white;font-family:Arial;
    text-align:center;padding:15px}}
    .box {{background:#14213d;padding:18px;margin:15px auto;
    border-radius:12px;max-width:400px}}
    button {{padding:12px;background:#00bfff;color:white;
    border:0;margin:8px}}
    </style></head>
    <body>
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {html}
    <a href="/admin">Voltar</a>
    </body></html>
    """


@app.route("/admin/rental/activate/<int:rid>", methods=["POST"])
def activate_rental(rid):
    if "user_id" not in session or session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()
    db.execute("BEGIN IMMEDIATE")

    rental = db.execute("""
        SELECT rentals.*, rental_plans.hours
        FROM rentals
        JOIN rental_plans ON rental_plans.id=rentals.plan_id
        WHERE rentals.id=? AND rentals.status='pending_activation'
    """, (rid,)).fetchone()

    if rental:
        now = datetime.utcnow()
        expires = now + timedelta(hours=rental["hours"])

        db.execute("""
            UPDATE rentals
            SET status='active', started_at=?, expires_at=?
            WHERE id=?
        """, (now.isoformat(), expires.isoformat(), rid))

    db.commit()
    db.close()

    return redirect("/admin/rentals")


@app.route("/admin/rental/refund/<int:rid>", methods=["POST"])
def refund_rental(rid):
    if "user_id" not in session or session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()
    db.execute("BEGIN IMMEDIATE")

    rental = db.execute("""
        SELECT * FROM rentals
        WHERE id=? AND status='pending_activation'
    """, (rid,)).fetchone()

    if rental:
        db.execute("""
            UPDATE users SET balance=balance+?
            WHERE id=?
        """, (rental["amount"], rental["user_id"]))

        db.execute("""
            INSERT INTO transactions
            (user_id, amount, description)
            VALUES (?, ?, ?)
        """, (
            rental["user_id"],
            rental["amount"],
            "Devolução de aluguer recusado"
        ))

        db.execute("""
            UPDATE rentals SET status='refunded'
            WHERE id=?
        """, (rid,))

    db.commit()
    db.close()

    return redirect("/admin/rentals")


init_rental()
