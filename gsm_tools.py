from flask import request, redirect, session
from markupsafe import escape
from app import app, connect

def init_tools():
    db = connect()
    db.execute("""
    CREATE TABLE IF NOT EXISTS gsm_tools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        price INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    )
    """)

    names = [
        "UnlockTool",
        "DFT Pro",
        "TSM Tool",
        "EFT Dongle",
        "3uTools",
        "AMT Tool"
    ]

    for name in names:
        db.execute(
            "INSERT OR IGNORE INTO gsm_tools (name) VALUES (?)",
            (name,)
        )

    db.commit()
    db.close()


@app.route("/admin/tools", methods=["GET", "POST"])
def admin_tools():
    if "user_id" not in session or session.get("role") != "admin":
        return "Acesso não autorizado", 403

    db = connect()

    if request.method == "POST":
        try:
            tool_id = int(request.form["tool_id"])
            price = int(request.form["price"])
            active = int(request.form["active"])

            if price < 0 or active not in (0, 1):
                return "Dados inválidos.", 400

            db.execute("""
                UPDATE gsm_tools
                SET price=?, active=?
                WHERE id=?
            """, (price, active, tool_id))

            db.commit()
        except (ValueError, KeyError):
            db.close()
            return "Dados inválidos.", 400

        db.close()
        return redirect("/admin/tools")

    tools = db.execute(
        "SELECT * FROM gsm_tools ORDER BY id"
    ).fetchall()
    db.close()

    content = """
    <h2>GESTÃO DE FERRAMENTAS GSM</h2>
    """

    for tool in tools:
        content += f"""
        <div class="box">
        <h3>{escape(tool['name'])}</h3>
        <form method="POST">
        <input type="hidden" name="tool_id"
        value="{tool['id']}">

        <p>Preço de aluguer (MT)</p>
        <input type="number" name="price"
        value="{tool['price']}" min="0" required>

        <p>Estado</p>
        <select name="active">
        <option value="1" {"selected" if tool['active'] else ""}>
        Ativa</option>
        <option value="0" {"selected" if not tool['active'] else ""}>
        Desativada</option>
        </select>
        <br>
        <button>GUARDAR</button>
        </form>
        </div>
        """

    return f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body {{background:#080d1b;color:white;font-family:Arial;
    text-align:center;padding:15px}}
    .box {{background:#14213d;padding:18px;margin:15px auto;
    border-radius:12px;max-width:400px}}
    input,select {{padding:12px;margin:8px;width:85%}}
    button {{background:#00bfff;color:white;padding:12px;
    border:0;border-radius:6px}}
    </style>
    </head>
    <body>
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {content}
    <a href="/admin" style="color:#00bfff">Voltar ao painel</a>
    </body>
    </html>
    """


@app.route("/tools")
def client_tools():
    if "user_id" not in session:
        return redirect("/login")

    db = connect()
    tools = db.execute("""
        SELECT * FROM gsm_tools
        WHERE active=1
        ORDER BY id
    """).fetchall()
    db.close()

    content = "<h2>FERRAMENTAS GSM DISPONÍVEIS</h2>"

    for tool in tools:
        content += f"""
        <div class="box">
        <h3>{escape(tool['name'])}</h3>
        <p>Preço configurado: {tool['price']} MT</p>
        <p>Estado: DISPONÍVEL</p>
        </div>
        """

    return f"""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="background:#080d1b;color:white;
    font-family:Arial;text-align:center;padding:15px">
    <h1 style="color:#00bfff">LSTECH PRO SERVER</h1>
    {content}
    <a href="/dashboard" style="color:#00bfff">Voltar</a>
    </body>
    </html>
    """


init_tools()
