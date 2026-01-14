import hashlib
import os
from datetime import datetime
from typing import Optional
import sqlite3
from pathlib import Path

class EvidenceManager:
    def __init__(self, upload_dir: str = "app/static/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def calculate_hash(self, file_path: str) -> str:
        """حساب بصمة SHA256 للملف"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def save_evidence(
        self,
        case_id: int,
        evidence_type: str,
        file_content: bytes,
        filename: str,
        description: Optional[str] = None,
        uploaded_by: int = None,
        url: Optional[str] = None
    ) -> dict:
        """حفظ دليل جديد"""
        # إنشاء اسم فريد للملف
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{Path(filename).name}"
        file_path = self.upload_dir / safe_filename
        
        # حفظ الملف
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # حساب بصمة الملف
        file_hash = self.calculate_hash(str(file_path))
        
        # حفظ في قاعدة البيانات
        conn = sqlite3.connect("cybershield.db")
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO evidence 
            (case_id, evidence_type, filename, file_hash, file_path, url, description, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                case_id,
                evidence_type,
                filename,
                file_hash,
                str(file_path),
                url,
                description,
                uploaded_by
            ))
            
            evidence_id = cursor.lastrowid
            conn.commit()
            
            # تسجيل في سجل التدقيق
            if uploaded_by:
                from app.core.security import log_audit
                log_audit(
                    uploaded_by,
                    "UPLOAD",
                    "EVIDENCE",
                    evidence_id,
                    f"رفع دليل: {filename} للقضية #{case_id}"
                )
            
            return {
                "id": evidence_id,
                "filename": filename,
                "file_hash": file_hash,
                "file_path": str(file_path),
                "message": "تم حفظ الدليل بنجاح"
            }
            
        except sqlite3.IntegrityError:
            conn.rollback()
            # الملف موجود مسبقًا (نفس البصمة)
            return {
                "error": "هذا الدليل موجود مسبقًا في النظام",
                "file_hash": file_hash
            }
        except Exception as e:
            conn.rollback()
            return {"error": f"خطأ في حفظ الدليل: {str(e)}"}
        finally:
            conn.close()
    
    def verify_integrity(self, evidence_id: int) -> bool:
        """التحقق من سلامة الدليل (عدم التعديل)"""
        conn = sqlite3.connect("cybershield.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT file_path, file_hash FROM evidence WHERE id = ?", (evidence_id,))
        evidence = cursor.fetchone()
        conn.close()
        
        if not evidence or not os.path.exists(evidence["file_path"]):
            return False
        
        # حساب البصمة الحالية ومقارنتها بالمخزنة
        current_hash = self.calculate_hash(evidence["file_path"])
        return current_hash == evidence["file_hash"]
    
    def get_evidence_info(self, evidence_id: int) -> dict:
        """الحصول على معلومات الدليل"""
        conn = sqlite3.connect("cybershield.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT e.*, u.username as uploaded_by_name 
        FROM evidence e
        LEFT JOIN users u ON e.uploaded_by = u.id
        WHERE e.id = ?
        ''', (evidence_id,))
        
        evidence = cursor.fetchone()
        conn.close()
        
        if not evidence:
            return {}
        
        # التحقق من السلامة
        is_integrity_ok = self.verify_integrity(evidence_id)
        
        return {
            "id": evidence["id"],
            "case_id": evidence["case_id"],
            "evidence_type": evidence["evidence_type"],
            "filename": evidence["filename"],
            "file_hash": evidence["file_hash"],
            "file_path": evidence["file_path"],
            "url": evidence["url"],
            "description": evidence["description"],
            "uploaded_by": evidence["uploaded_by_name"],
            "uploaded_at": evidence["uploaded_at"],
            "integrity_verified": is_integrity_ok,
            "file_exists": os.path.exists(evidence["file_path"])
        }
    
    def archive_url(self, url: str, case_id: int, uploaded_by: int) -> dict:
        """أرشفة رابط كدليل"""
        import requests
        from urllib.parse import urlparse
        
        try:
            # استخراج معلومات الرابط
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            filename = f"url_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            # محتوى الأرشيف
            archive_content = f"""
            === معلومات الأرشفة ===
            الرابط: {url}
            النطاق: {domain}
            وقت الأرشفة: {datetime.now().isoformat()}
            حالة القضية: #{case_id}
            
            === محتوى الصفحة (لاحقاً يمكن إضافة حفظ الصفحة) ===
            [سيتم حفظ محتوى الصفحة في إصدارات لاحقة]
            """
            
            # حفظ كملف نصي
            file_path = self.upload_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(archive_content)
            
            # قراءة المحتوى للبصمة
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # حفظ في قاعدة البيانات
            return self.save_evidence(
                case_id=case_id,
                evidence_type="url_archive",
                file_content=file_content,
                filename=filename,
                description=f"أرشيف للرابط: {url}",
                uploaded_by=uploaded_by,
                url=url
            )
            
        except Exception as e:
            return {"error": f"خطأ في أرشفة الرابط: {str(e)}"}
