import os
from datetime import timedelta

class Settings:
    # إعدادات التطبيق
    APP_NAME = "Abu Jamal CyberShield"
    APP_VERSION = "1.0.0"
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = "sqlite:///./cybershield.db"
    
    # إعدادات الأمان
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # إعدادات التخزين
    UPLOAD_DIR = "app/static/uploads"
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    
    # الأدوار
    ROLES = {
        "admin": "المسؤول العام",
        "intake": "موظف الاستقبال",
        "analyst": "محلل",
        "reporter": "مراسل",
        "viewer": "مشاهد"
    }
    
    # حالات القضية
    CASE_STATUS = {
        "new": "جديدة",
        "under_analysis": "قيد التحليل",
        "evidence_collected": "تم جمع الأدلة",
        "network_linked": "مرتبطة بشبكة",
        "report_submitted": "تم إرسال التقرير",
        "closed": "مغلقة",
        "escalated": "مرفوعة"
    }
    
    # أنواع المخالفات
    VIOLATION_TYPES = {
        "privacy": "انتهاك الخصوصية",
        "extortion": "ابتزاز إلكتروني",
        "hate_speech": "خطاب كراهية",
        "terrorism": "إرهاب أو تنظيمات محظورة",
        "impersonation": "انتحال شخصية",
        "harassment": "تحرش إلكتروني"
    }

settings = Settings()
