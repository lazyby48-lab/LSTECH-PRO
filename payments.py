from flask import Blueprint, jsonify, request, session, redirect
from flask import render_template_string
import sqlite3

payments = Blueprint("payments", __name__)

DB = "lstech.db"


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def user_session():
    return session.get("user_id")


def admin_session():
    return session.get("role") == "admin"


@payments.route("/payment/status")
def payment_status():
    return jsonify({
        "service": "LSTECH PRO SERVER",
        "provider": "ClicPay",
        "configured": False,
        "mode": "test"
    })


@payments.route("/deposit", methods=["GET", "POST"])
def deposit():
    if not user_session():
        return redirect("/login")

    if request.method == "POST":
        try:
            amount = int(request.form["amount"])
        except (ValueError, TypeError):
            return "Valor inválido."

        method = request.form.get("method")
        code = request.form.get("transaction_code", "").strip()

        if amount < 10:
            return "Depósito mínimo: 10 MT."

        if method not in ["MPESA", "EMOLA"]:
            return "Método inválido."

        if len(code) < 4:
            return "Código de transação inválido."

        db = connect()

        try:
            db.execute("""
                INSERT INTO deposit_requests
                (user_id, amount, method, transaction_code)
                VALUES (?, ?, ?, ?)
            """, (user_session(), amount, method, code))

            db.commit()

        except sqlite3.IntegrityError:
            db.close()
            return "Código de transação já utilizado."

        db.close()
        return "Pedido enviado! Aguarde confirmação do administrador."

    return render_template_string("""
    <h2>LSTECH PRO - Depósito</h2>

    <form method="POST">
        <input type="number" name="amount"
        placeholder="Valor em MT" min="10" required>

        <select name="method" required>
            <option value="MPESA">M-Pesa</option>
            <option value="EMOLA">e-Mola</option>
        </select>

        <input name="transaction_code"
        placeholder="Código da transação" required>

        <button>Enviar pedido</button>
    </form>

    <a href="/dashboard">Voltar</a>
    """)


@payments.route("/my-deposits")
def my_deposits():
    if not user_session():
        return redirect("/login")

    db = connect()

    deposits = db.execute("""
        SELECT * FROM deposit_requests
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_session(),)).fetchall()

    db.close()

    html = "<h2>Meus depósitos</h2>"

    for d in deposits:
        html += f"""
        <p>Valor: {d['amount']} MT</p>
        <p>Método: {d['method']}</p>
        <p>Estado: {d['status']}</p>
        <hr>
        """

    return html + '<a href="/dashboard">Voltar</a>'


@payments.route("/admin/deposits")
def admin_deposits():
    if not user_session() or not admin_session():
        return "Acesso não autorizado.", 403

    db = connect()

    deposits = db.execute("""
        SELECT deposit_requests.*, users.username
        FROM deposit_requests
        JOIN users ON users.id=deposit_requests.user_id
        ORDER BY deposit_requests.id DESC
    """).fetchall()

    db.close()

    html = "<h2>Gestão de depósitos</h2>"

    for d in deposits:
        html += f"""
        <hr>
        <p>Cliente: {d['username']}</p>
        <p>Valor: {d['amount']} MT</p>
        <p>Método: {d['method']}</p>
        <p>Código: {d['transaction_code']}</p>
        <p>Estado: {d['status']}</p>
        """

        if d["status"] == "pending":
            html += f"""
            <form method="POST"
            action="/admin/deposits/{d['id']}/approve">
                <button>Confirmar pagamento</button>
            </form>

            <form method="POST"
            action="/admin/deposits/{d['id']}/reject">
                <button>Rejeitar</button>
            </form>
            """

    return html + '<a href="/admin">Voltar</a>'


@payments.route("/admin/deposits/<int:deposit_id>/approve",
                methods=["POST"])
def approve_deposit(deposit_id):
    if not user_session() or not admin_session():
        return "Acesso não autorizado.", 403

    db = connect()

    try:
        db.execute("BEGIN IMMEDIATE")

        deposit = db.execute("""
            SELECT * FROM deposit_requests
            WHERE id=? AND status='pending'
        """, (deposit_id,)).fetchone()

        if not deposit:
            db.rollback()
            return "Pedido inexistente ou já processado."

        db.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE id=?
        """, (deposit["amount"], deposit["user_id"]))

        db.execute("""
            INSERT INTO transactions
            (user_id, amount, description, type)
            VALUES (?, ?, ?, 'credit')
        """, (
            deposit["user_id"],
            deposit["amount"],
            "Depósito aprovado: " + deposit["method"]
        ))

        db.execute("""
            UPDATE deposit_requests
            SET status='approved', reviewed_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'
        """, (deposit_id,))

        db.commit()
        return "Depósito aprovado e saldo atualizado!"

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@payments.route("/admin/deposits/<int:deposit_id>/reject",
                methods=["POST"])
def reject_deposit(deposit_id):
    if not user_session() or not admin_session():
        return "Acesso não autorizado.", 403

    db = connect()

    db.execute("""
        UPDATE deposit_requests
        SET status='rejected', reviewed_at=CURRENT_TIMESTAMP
        WHERE id=? AND status='pending'
    """, (deposit_id,))

    db.commit()
    db.close()

    return "Pedido rejeitado."
