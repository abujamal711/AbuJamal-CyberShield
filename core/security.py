from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import sqlite3

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """التحقق من كلمة المرور"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """تشفير كلمة المرور"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """إنشاء توكن وصول"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_admin_user():
    """إنشاء مستخدم المدير الافتراضي"""
    try:
        conn = sqlite3.connect("cybershield.db")
        cursor = conn.cursor()
        
        # التحقق مما إذا كان المستخدم موجودًا
        cursor.execute("SELECT id FROM users WHERE username = ?", ("abujamal",))
        if cursor.fetchone():
            print("👤 مستخدم المدير موجود بالفعل")
            return
        
        # إنشاء كلمة مرور مشفرة
        hashed_password = get_password_hash("Admin@2024")
        
        # إدراج مستخدم المدير
        cursor.execute('''
        INSERT INTO users (username, full_name, email, hashed_password, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("abujamal", "أبو جمال", "admin@cybershield.dj", hashed_password, "admin", 1))
        
        conn.commit()
        print("✅ تم إنشاء مستخدم المدير الافتراضي بنجاح")
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء مستخدم المدير: {e}")
    finally:
        conn.close()

def authenticate_user(username: str, password: str):
    """مصادقة المستخدم"""
    conn = sqlite3.connect("cybershield.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    
    return user

def check_permission(user_role: str, required_role: str) -> bool:
    """التحقق من صلاحية المستخدم"""
    role_hierarchy = {
        "admin": 4,
        "analyst": 3,
        "reporter": 2,
        "intake": 1,
        "viewer": 0
    }
    
    user_level = role_hierarchy.get(user_role, -1)
    required_level = role_hierarchy.get(required_role, 0)
    
    return user_level >= required_level

def log_audit(user_id: int, action: str, entity_type: str, entity_id: int = None, details: str = None):
    """تسجيل نشاط في سجل التدقيق"""
    try:
        conn = sqlite3.connect("cybershield.db")
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, action, entity_type, entity_id, details))
        
        conn.commit()
    except Exception as e:
        print(f"❌ خطأ في تسجيل النشاط: {e}")
    finally:
        conn.close()
