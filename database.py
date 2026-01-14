import sqlite3
from contextlib import contextmanager
from datetime import datetime

DATABASE_PATH = "cybershield.db"

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    ''')
    
    # جدول القضايا
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        violation_type TEXT NOT NULL,
        status TEXT DEFAULT 'new',
        priority INTEGER DEFAULT 1,
        reporter_name TEXT,
        reporter_contact TEXT,
        assigned_to INTEGER,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        closed_at TIMESTAMP,
        FOREIGN KEY (assigned_to) REFERENCES users (id),
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')
    
    # جدول الأدلة
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        evidence_type TEXT NOT NULL,
        filename TEXT,
        file_hash TEXT UNIQUE,
        file_path TEXT,
        url TEXT,
        description TEXT,
        uploaded_by INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT,
        FOREIGN KEY (case_id) REFERENCES cases (id),
        FOREIGN KEY (uploaded_by) REFERENCES users (id)
    )
    ''')
    
    # جدول الشبكات (للربط بين الحسابات)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS networks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        network_id TEXT UNIQUE NOT NULL,
        name TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول ربط القضايا بالشبكات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS case_network (
        case_id INTEGER NOT NULL,
        network_id INTEGER NOT NULL,
        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (case_id, network_id),
        FOREIGN KEY (case_id) REFERENCES cases (id),
        FOREIGN KEY (network_id) REFERENCES networks (id)
    )
    ''')
    
    # جدول سجل الأنشطة (Audit Trail)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        details TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # جدول التقارير
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id TEXT UNIQUE NOT NULL,
        case_id INTEGER NOT NULL,
        report_type TEXT NOT NULL,
        content TEXT NOT NULL,
        generated_by INTEGER,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sent_to TEXT,
        sent_at TIMESTAMP,
        status TEXT DEFAULT 'draft',
        FOREIGN KEY (case_id) REFERENCES cases (id),
        FOREIGN KEY (generated_by) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ تم تهيئة قاعدة البيانات بنجاح")

@contextmanager
def get_db():
    """الحصول على اتصال قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
