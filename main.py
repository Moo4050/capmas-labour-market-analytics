from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from urllib.parse import unquote
import pyodbc
import hashlib
import httpx
import secrets
import json
import os
from datetime import datetime

app = FastAPI(title="CAPMAS Labour Market Portal")
templates = Jinja2Templates(directory="templates")


# ── DB connection ──────────────────────────────────────────────
def get_conn():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=Labour_ForceDB;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )


# ── Simple file-based users ────────────────────────────────────
USERS_FILE = "users.json"


def load_users():
    if not os.path.exists(USERS_FILE):
        save_users({"admin": hash_password("admin123")})
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


load_users()
print("✅ Users file ready")

# ── Sessions ───────────────────────────────────────────────────
sessions = {}


def create_session(user_id, user_type):
    token = secrets.token_hex(32)
    sessions[token] = {"user_id": user_id, "user_type": user_type}
    return token


def get_session(request: Request):
    token = request.cookies.get("session_token")
    if token and token in sessions:
        return sessions[token]
    return None


# ══════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    session = get_session(request)
    if session:
        if session["user_type"] == "admin":
            return RedirectResponse("/admin")
        return RedirectResponse("/individual")
    return templates.TemplateResponse(request, "login.html")


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "كلمتا المرور غير متطابقتين", "tab": "register"},
        )
    if len(username.strip()) < 3:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "اسم المستخدم لازم يكون 3 حروف على الأقل", "tab": "register"},
        )
    users = load_users()
    if username in users:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "اسم المستخدم موجود بالفعل، اختر اسماً آخر", "tab": "register"},
        )
    users[username] = hash_password(password)
    save_users(users)
    token = create_session(username, "individual")
    resp = RedirectResponse("/individual", status_code=302)
    resp.set_cookie("session_token", token)
    return resp


@app.post("/login")
async def login(
    request: Request,
    user_type: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
):
    users = load_users()
    if user_type == "admin":
        if username == "admin" and users.get("admin") == hash_password(password):
            token = create_session("admin", "admin")
            resp = RedirectResponse("/admin", status_code=302)
            resp.set_cookie("session_token", token)
            return resp
        return templates.TemplateResponse(
            request, "login.html", {"error": "بيانات المدير غير صحيحة"}
        )
    elif user_type == "individual":
        if username == "admin":
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "هذا الحساب للمدير فقط، اختر نوع المدير"},
            )
        if username not in users or users[username] != hash_password(password):
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "error": "اسم المستخدم أو كلمة المرور غير صحيحة — سجّل حساباً جديداً إذا لم يكن عندك حساب"
                },
            )
        token = create_session(username, "individual")
        resp = RedirectResponse("/individual", status_code=302)
        resp.set_cookie("session_token", token)
        return resp
    return RedirectResponse("/", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token in sessions:
        del sessions[token]
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session_token")
    return resp


@app.get("/individual", response_class=HTMLResponse)
async def individual_home(request: Request):
    session = get_session(request)
    if not session or session["user_type"] != "individual":
        return RedirectResponse("/")
    return templates.TemplateResponse(
        request, "individual.html", {"display_name": session["user_id"]}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    session = get_session(request)
    if not session or session["user_type"] != "admin":
        return RedirectResponse("/")
    return templates.TemplateResponse(
        request, "admin.html", {"username": session["user_id"]}
    )


@app.post("/admin/add_individual")
async def add_individual(request: Request, individual_id: str = Form(...)):
    session = get_session(request)
    if not session or session["user_type"] != "admin":
        raise HTTPException(status_code=403)
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Individual_ID FROM Individual WHERE Individual_ID=?", individual_id
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return templates.TemplateResponse(
                request,
                "admin.html",
                {
                    "username": session["user_id"],
                    "error": f"الـ ID '{individual_id}' غير موجود في قاعدة البيانات",
                },
            )
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "username": session["user_id"],
                "success": "تم العثور على الفرد",
                "found_id": individual_id,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request, "admin.html", {"username": session["user_id"], "error": str(e)}
        )


@app.get("/admin/individual/{individual_id}", response_class=HTMLResponse)
async def admin_view_individual(individual_id: str, request: Request):
    session = get_session(request)
    if not session or session["user_type"] != "admin":
        return RedirectResponse("/")
    return templates.TemplateResponse(
        request,
        "individual_data.html",
        {"individual_id": individual_id, "username": session["user_id"]},
    )


@app.get("/api/individual/{section}")
async def get_individual_data(section: str, request: Request, iid: str = None):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401)
    individual_id = (
        iid if (session["user_type"] == "admin" and iid) else session["user_id"]
    )
    section_map = {
        "personal": "Individual",
        "employment": "Employment",
        "education": "Education",
        "income": "Income",
        "unemployment": "Unemployment",
        "disability": "Disability",
        "social": "Social_Benefits",
        "covid": "COVID_IMPACT",
        "secondary_job": "Secondary_Job",
    }
    if section not in section_map:
        raise HTTPException(status_code=404)
    table = section_map[section]
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table} WHERE Individual_ID = ?", individual_id)
        row = cursor.fetchone()
        if not row:
            conn.close()
            return JSONResponse({"data": None, "message": "لا توجد بيانات لهذا القسم"})
        cols = [desc[0] for desc in cursor.description]
        conn.close()
        return JSONResponse(
            {"data": dict(zip(cols, [str(v) if v is not None else None for v in row]))}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    session = get_session(request)
    if not session:
        return RedirectResponse("/")
    return templates.TemplateResponse(request, "reports.html")


@app.get("/view-pdf", response_class=HTMLResponse)
async def view_pdf(request: Request, file: str):
    session = get_session(request)
    if not session:
        return RedirectResponse("/")
    return templates.TemplateResponse(request, "view_pdf.html", {"file": file})


@app.get("/pdf/{filename:path}")
async def serve_pdf(filename: str, request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=403)
    from urllib.parse import unquote

    filename = unquote(filename)
    file_path = (
        r"E:\ITI Labs\Final Project\capmas_portal\static\reports" + "\\" + filename
    )
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Not found: {file_path}")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.post("/api/chat")
async def chat_proxy(request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://127.0.0.1:5000/chat", json=body, timeout=30)
        return JSONResponse(resp.json())


@app.get("/n8n")
async def n8n_page():
    content = open(r"E:\ITI Labs\Final Project\n8n\chat.html", encoding="utf-8").read()
    content = content.replace('src="logo.png.jpeg"', 'src="/static/logo.png.jpeg"')
    content = content.replace('src="logo.png"', 'src="/static/logo.png.jpeg"')
    return HTMLResponse(content)


@app.get("/logo.png.jpeg")
async def logo():
    return FileResponse(r"E:\ITI Labs\Final Project\n8n\logo.png")


app.mount("/static", StaticFiles(directory="static"), name="static")
