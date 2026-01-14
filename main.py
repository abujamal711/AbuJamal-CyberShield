from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import sqlite3
import os

from app.database import init_db, get_db
from app.api import auth, cases, evidence, reports
from app.core.security import create_admin_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    # تهيئة عند بدء التشغيل
    print("🚀 بدء تشغيل Abu Jamal CyberShield...")
    init_db()
    create_admin_user()  # إنشاء مستخدم المدير الافتراضي
    yield
    # تنظيف عند الإغلاق
    print("🛑 إغلاق النظام...")

app = FastAPI(
    title="Abu Jamal CyberShield",
    description="منصة العدالة الرقمية - Digital Justice Platform",
    version="1.0.0",
    lifespan=lifespan
)

# تحميل الملفات الثابتة والقوالب
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# تسجيل واجهات API
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard/main.html", {"request": request})

# إضافة الواجهات الأساسية الأخرى...
