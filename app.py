



from flask import Flask, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import escape
import sqlite3
import secrets
import os
from functools import wraps

app = Flask(__name__)
from payments import payments
app.register_blueprint(payments)

if not os.path.exists("secret.key"):
    with open("secret.key", "w") as f:
        f.write(secrets.token_hex(32))

app.secret_key = open("secret.key").read()

DB = "lstech.db"

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = connect()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'client',
        status TEXT DEFAULT 'pending',
        balance INTEGER DEFAULT 0)
    """)
    db.commit()
    db.close()

def page(title, content):
    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport"
    content="width=device-width, initial-scale=1">
    <title>{title} - LSTECH PRO</title>
    <style>
    body {{
      background:#080d1b;color:white;
      font-family:Arial;text-align:center;
      padding:20px;
    }}
    .box {{
      background:#14213d;padding:22px;
      margin:18px auto;border-radius:12px;
      max-width:420px;
    }}
    input {{
      width:90%;padding:13px;
      margin:8px;border-radius:7px;
      border:0;
    }}
    button {{
      background:#00bfff;color:white;
      padding:13px 25px;border:0;
      border-radius:7px;margin:8px;
    }}
    a {{color:#00bfff;}}
    </style>
    </head>
    <body>
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {content}
    </body>
    </html>
    """

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return page("Início", """
    <div class="box">
    <h2>GSM RENTAL PLATFORM</h2>
    <p>Servidor GSM LSTECH PRO</p>
    <p><a href="/register">Criar conta</a></p>
    <p><a href="/login">Entrar na plataforma</a></p>
    </div>
    """)

@app.route("/setup", methods=["GET", "POST"])
def setup():
    db = connect()
    admins = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='admin'"
    ).fetchone()[0]

    if admins:
        db.close()
        return "Administrador já configurado."

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3 or len(password) < 10:
            db.close()
            return "Utilizador: mínimo 3 caracteres. Senha: mínimo 10."

        try:
            db.execute(
                "INSERT INTO users (username,password,role,status) VALUES (?,?,?,?)",
                (username, generate_password_hash(password),
                 "admin", "approved")
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.close()
            return "Este utilizador já existe."

        db.close()
        return redirect("/login")

    db.close()
    return page("Configurar administrador", """
    <div class="box">
    <h2>Criar primeiro administrador</h2>
    <form method="POST">
    <input name="username" placeholder="Nome de administrador" required>
    <input name="password" type="password"
    placeholder="Senha (mínimo 10 caracteres)" required>
    <button>Criar administrador</button>
    </form>
    </div>
    """)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3 or len(password) < 10:
            return "Utilizador mínimo 3 caracteres e senha mínima 10."

        db = connect()
        try:
            db.execute(
                "INSERT INTO users (username,password) VALUES (?,?)",
                (username, generate_password_hash(password))
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.close()
            return "Este nome de utilizador já existe."

        db.close()
        return "Conta criada! Aguarde aprovação do administrador."

    return page("Registo", """
    <div class="box">
    <h2>Criar conta</h2>
    <form method="POST">
    <input name="username" placeholder="Nome de utilizador" required>
    <input name="password" type="password"
    placeholder="Criar senha" required>
    <button>Registar</button>
    </form>
    <a href="/login">Já tenho conta</a>
    </div>
    """)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = connect()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            if user["status"] != "approved":
                return "Conta pendente ou bloqueada. Contacte o administrador."

            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect("/admin" if user["role"] == "admin"
                            else "/dashboard")

        return "Utilizador ou senha incorretos."

    return page("Login", """
    <div class="box">
    <h2>Entrar</h2>
    <form method="POST">
    <input name="username" placeholder="Utilizador" required>
    <input name="password" type="password"
    placeholder="Senha" required>
    <button>Login</button>
    </form>
    </div>
    """)

@app.route("/dashboard")
@login_required
def dashboard():
    db = connect()
    user = db.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    db.close()

    if user["status"] != "approved":
        session.clear()
        return redirect("/login")

    return page("Painel do cliente", f"""
    <div class="box">
    <h2>Bem-vindo, {escape(user['username'])}</h2>
    <h3>Carteira: {user['balance']} MT</h3>
    <p>GSM RENTAL</p>
    <p>Serviços disponíveis em preparação.</p>
    <a href="/logout">Sair</a>
    </div>
    """)

@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()

    users = db.execute(
        "SELECT * FROM users ORDER BY id DESC"
    ).fetchall()

    total = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='client'"
    ).fetchone()[0]

    approved = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='client' AND status='approved'"
    ).fetchone()[0]

    pending = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='client' AND status='pending'"
    ).fetchone()[0]

    blocked = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='client' AND status='blocked'"
    ).fetchone()[0]

    db.close()

    content = f"""
    <div class='box'>
    <h2>LSTECH PRO SERVER</h2>
    <h3>Painel Administrativo</h3>

    <p>Total de clientes: {total}</p>
    <p>Clientes aprovados: {approved}</p>
    <p>Clientes pendentes: {pending}</p>
    <p>Clientes bloqueados: {blocked}</p>
    """

    for u in users:
        if u["role"] != "client":
            continue

        content += f"""
        <hr>
        <h3>Cliente: {escape(u['username'])}</h3>
        <p>Estado: {escape(u['status'])}</p>
        <p>Saldo: {u['balance']} MT</p>

        <form method="POST" action="/approve/{u['id']}">
            <button name="status" value="approved">Aprovar</button>
            <button name="status" value="blocked">Bloquear</button>
            <button name="status" value="pending">Suspender</button>
        </form>

        <h4>Gestão de saldo</h4>

        <form method="POST" action="/admin/balance/{u['id']}">
            <input type="number" name="amount"
            placeholder="Valor em MT" min="1" required>

            <button name="action" value="add">
            Adicionar saldo
            </button>

            <button name="action" value="remove">
            Retirar saldo
            </button>
        </form>
        """

    content += "<hr><a href='/admin/orders'>Gerir pedidos GSM</a><br>"
    content += "<a href='/logout'>Terminar sessão</a></div>"

    return page("Administração LSTECH PRO", content)


@app.route("/approve/<int:user_id>", methods=["POST"])
@login_required
def approve(user_id):
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    status = request.form.get("status")
    if status not in ["approved", "blocked", "pending"]:
        return "Estado inválido.", 400

    db = connect()
    db.execute(
        "UPDATE users SET status=? WHERE id=? AND role='client'",
        (status, user_id)
    )
    db.commit()
    db.close()
    return redirect("/admin")
@app.route("/admin/balance/<int:user_id>", methods=["POST"])
def admin_balance(user_id):
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        return "Valor inválido.", 400

    action = request.form.get("action")

    if amount <= 0:
        return "Valor inválido.", 400

    if action not in ["add", "remove"]:
        return "Operação inválida.", 400

    db = connect()

    user = db.execute(
        "SELECT id, balance FROM users WHERE id=? AND role='client'",
        (user_id,)
    ).fetchone()

    if user is None:
        db.close()
        return "Cliente não encontrado.", 404

    if action == "remove" and user["balance"] < amount:
        db.close()
        return "Saldo insuficiente.", 400

    new_balance = (
        user["balance"] + amount
        if action == "add"
        else user["balance"] - amount
    )

    transaction_type = "credit" if action == "add" else "debit"

    db.execute(
        "UPDATE users SET balance=? WHERE id=?",
        (new_balance, user_id)
    )

    db.execute(
        """INSERT INTO transactions
        (user_id, amount, type, description)
        VALUES (?, ?, ?, ?)""",
        (user_id, amount, transaction_type,
         "Operação administrativa")
    )

    db.commit()
    db.close()

    return redirect("/admin")
    db.commit()
    db.close()
    return redirect("/admin")

@app.route("/api/v1/status")
def api_status():
    return {
        "server": "LSTECH PRO",
        "status": "online",
        "version": "2.0"
    }


@app.route("/admin/history")
@login_required
def transaction_history():
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()

    transactions = db.execute("""
        SELECT transactions.*, users.username
        FROM transactions
        LEFT JOIN users ON users.id = transactions.user_id
        ORDER BY transactions.id DESC
    """).fetchall()

    db.close()

    content = "<div class='box'><h2>LSTECH PRO - Histórico Financeiro</h2>"

    if not transactions:
        content += "<p>Nenhuma transação registada.</p>"

    for t in transactions:
        tipo = "Saldo adicionado" if t["type"] == "credit" else "Saldo retirado"

        content += f"""
7        <hr>
        <p>Cliente: {escape(str(t['username'] or 'Cliente removido'))}</p>
        <p>Operação: {tipo}</p>
        <p>Valor: {t['amount']} MT</p>
        <p>Descrição: {escape(str(t['description'] or ''))}</p>
        <p>Data: {escape(str(t['created_at']))}</p>
        """

    content += "<hr><a href='/admin'>Voltar ao painel</a></div>"

    return page("Histórico Financeiro", content)


@app.route("/create-order", methods=["GET", "POST"])
@login_required
def create_order():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        service = request.form.get("service", "").strip()
        imei = request.form.get("imei", "").strip()
        notes = request.form.get("notes", "").strip()

        if not brand or not model or not service:
            return "Preencha os campos obrigatórios.", 400

        db = connect()
        db.execute("""
            INSERT INTO orders
            (user_id, brand, model, service, imei, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user_id"], brand, model, service, imei, notes))
        db.commit()
        db.close()

        return redirect("/my-orders")

    content = """
    <div class='box'>
    <h2>Nova encomenda GSM</h2>
    <form method='POST'>
    <input name='brand' placeholder='Marca' required>
    <input name='model' placeholder='Modelo' required>
    <input name='service' placeholder='Serviço' required>
    <input name='imei' placeholder='IMEI'>
    <textarea name='notes' placeholder='Observações'></textarea>
    <button type='submit'>Enviar encomenda</button>
    </form>
    </div>
    """
    return page("Nova encomenda", content)


@app.route("/my-orders")
@login_required
def my_orders():
    db = connect()
    orders = db.execute("""
        SELECT * FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    db.close()

    content = "<div class='box'><h2>Minhas encomendas</h2>"

    for order in orders:
        content += f"""
        <hr>
        <p>Marca: {escape(str(order['brand']))}</p>
        <p>Modelo: {escape(str(order['model']))}</p>
        <p>Serviço: {escape(str(order['service']))}</p>
        <p>Estado: {escape(str(order['status']))}</p>
        """

    content += "<a href='/dashboard'>Voltar</a></div>"
    return page("Minhas encomendas", content)


@app.route("/admin/orders")
@login_required
def admin_orders():
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    db = connect()
    orders = db.execute("""
        SELECT orders.*, users.username
        FROM orders
        LEFT JOIN users ON users.id = orders.user_id
        ORDER BY orders.id DESC
    """).fetchall()
    db.close()

    content = "<div class='box'><h2>Gestão de encomendas GSM</h2>"

    for order in orders:
        content += f"""
        <hr>
        <p>Cliente: {escape(str(order['username'] or 'Desconhecido'))}</p>
        <p>Marca: {escape(str(order['brand']))}</p>
        <p>Modelo: {escape(str(order['model']))}</p>
        <p>Serviço: {escape(str(order['service']))}</p>
        <p>IMEI: {escape(str(order['imei'] or 'Não informado'))}</p>
        <p>Estado: {escape(str(order['status']))}</p>
        <form method='POST' action='/admin/orders/{order['id']}/status'>
        <select name='status'>
            <option value='pending'>Pendente</option>
            <option value='processing'>Em processamento</option>
            <option value='completed'>Concluída</option>
            <option value='rejected'>Rejeitada</option>
        </select>
        <button type='submit'>Atualizar</button>
        </form>
        """

    content += "<a href='/admin'>Voltar ao painel</a></div>"
    return page("Gestão de encomendas", content)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    if session.get("role") != "admin":
        return "Acesso não autorizado.", 403

    status = request.form.get("status")
    allowed = ["pending", "processing", "completed", "rejected"]

    if status not in allowed:
        return "Estado inválido.", 400

    db = connect()
    db.execute("""
        UPDATE orders
        SET status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (status, order_id))
    db.commit()
    db.close()

    return redirect("/admin/orders")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin-recovery", methods=["GET", "POST"])
def admin_recovery():
    token = os.environ.get("ADMIN_RECOVERY_TOKEN", "")

    if not token:
        return "Recuperação desativada.", 404

    if request.method == "POST":
        supplied = request.form.get("token", "")
        password = request.form.get("password", "")

        if not secrets.compare_digest(supplied, token):
            return "Código inválido.", 403

        if len(password) < 10:
            return "Password deve ter pelo menos 10 caracteres.", 400

        db = connect()
        result = db.execute(
            """UPDATE users SET password=?
               WHERE id=1 AND role='admin'""",
            (generate_password_hash(password),)
        )
        db.commit()
        changed = result.rowcount
        db.close()

        if changed == 1:
            return "Password ADMIN atualizada com sucesso!"

        return "Administrador não encontrado.", 404

    return """
    <h2>Recuperação LSTECH PRO</h2>
    <form method="POST">
        <input name="token" type="password"
        placeholder="Código secreto" required>
        <br><br>
        <input name="password" type="password"
        placeholder="Nova password" required>
        <br><br>
        <button type="submit">Atualizar password</button>
    </form>
    
    """

init_db()

import extra

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
