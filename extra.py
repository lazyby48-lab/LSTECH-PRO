from app import app, connect
from flask import request, redirect, session
from markupsafe import escape

def init_credits():
    db = connect()
    db.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    db.commit()
    db.close()

@app.route("/admin/credits", methods=["GET", "POST"])
def manage_credits():
    if "user_id" not in session or session.get("role") != "admin":
        return "Acesso não autorizado", 403

    message = ""

    if request.method == "POST":
        try:
            user_id = int(request.form["user_id"])
            amount = int(request.form["amount"])

            if amount <= 0 or amount > 1000000:
                raise ValueError()

            db = connect()
            db.execute("BEGIN IMMEDIATE")

            user = db.execute(
                "SELECT id FROM users WHERE id=? AND role='client'",
                (user_id,)
            ).fetchone()

            if not user:
                db.rollback()
                db.close()
                return "Cliente não encontrado."

            db.execute(
                "UPDATE users SET balance=balance+? WHERE id=?",
                (amount, user_id)
            )

            db.execute("""
                INSERT INTO transactions
                (user_id, amount, description)
                VALUES (?, ?, ?)
            """, (user_id, amount, "Crédito adicionado pelo administrador"))

            db.commit()
            db.close()

            return redirect("/admin/credits")

        except (ValueError, KeyError):
            message = "Valor inválido."

    db = connect()
    users = db.execute(
        "SELECT id, username, balance FROM users WHERE role='client'"
    ).fetchall()

    history = db.execute("""
        SELECT transactions.*, users.username
        FROM transactions
        JOIN users ON users.id=transactions.user_id
        ORDER BY transactions.id DESC LIMIT 30
    """).fetchall()
    db.close()

    html = """
    <div style="background:#14213d;padding:20px;border-radius:12px">
    <h2>GESTÃO DE CRÉDITOS</h2>
    <p style="color:#ffcc00">""" + message + """</p>
    <form method="POST">
    <label>Selecionar cliente</label><br>
    <select name="user_id" required style="padding:12px;margin:10px;width:90%">
    """

    for u in users:
        html += (
            f'<option value="{u["id"]}">'
            f'{escape(u["username"])} - {u["balance"]} MT'
            '</option>'
        )

    html += """
    </select><br>
    <label>Quantidade de créditos (MT)</label><br>
    <input type="number" name="amount" min="1"
    max="1000000" required style="padding:12px;margin:10px">
    <br>
    <button style="padding:13px;background:#00bfff;color:white">
    ADICIONAR CRÉDITOS
    </button>
    </form>
    <hr>
    <h3>HISTÓRICO DE CRÉDITOS</h3>
    """

    for t in history:
        html += (
            f'<p>{escape(t["username"])}: '
            f'+{t["amount"]} MT<br>'
            f'{escape(t["created_at"])}</p><hr>'
        )

    html += '<a href="/admin" style="color:#00bfff">Voltar ao painel</a></div>'

    return f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="background:#080d1b;color:white;font-family:Arial;text-align:center;padding:15px">
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {html}
    </body></html>
    """

init_credits()

import gsm_tools

import rental

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
