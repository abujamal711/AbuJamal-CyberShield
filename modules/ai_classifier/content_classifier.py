import re
from typing import Dict, List, Tuple
import sqlite3

class ContentClassifier:
    def __init__(self):
        # قوائم الكلمات المفتاحية للتصنيف
        self.keywords = {
            "privacy": [
                "خاص", "خصوصية", "صور خاصة", "مقاطع خاصة", "بدون إذن",
                "مسرب", "تسريب", "فضيحة", "كاميرا خفية"
            ],
            "extortion": [
                "ابتزاز", "تهديد", "فديو", "فلوس", "مبلغ",
                "تحويل", "حوالة", "تهديد بالنشر", "فضيحة"
            ],
            "hate_speech": [
                "كراهية", "عنصرية", "طائفي", "تحريض", "عنف",
                "قتل", "تهديد", "إرهاب", "تكفير"
            ],
            "terrorism": [
                "داعش", "قاعدة", "تنظيم", "إرهابي", "تفجير",
                "سلاح", "تدريب", "تجنيد", "تكفيري"
            ],
            "impersonation": [
                "انتحال", "حساب مزيف", "تزوير", "شخصية", "مقلد",
                "نشر باسم", "سرقة حساب"
            ],
            "harassment": [
                "تحرش", "مضايقة", "إزعاج", "تهديد جنسي", "محتوى جنسي",
                "رسائل غير مرغوبة", "ملاحقة"
            ]
        }
        
        # أنماط Regex للكشف
        self.patterns = {
            "phone_number": r'\b\d{10,15}\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "bank_account": r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
            "social_media": r'(instagram|facebook|twitter|tiktok|snapchat|telegram)\.(com|org|net)/[^\s]+'
        }
    
    def classify_content(self, text: str, title: str = "") -> Dict:
        """تصنيف المحتوى بناءً على النص والعنوان"""
        combined_text = f"{title} {text}".lower()
        
        scores = {}
        
        # حساب النقاط لكل فئة
        for category, words in self.keywords.items():
            score = 0
            for word in words:
                if word in combined_text:
                    score += 1
            scores[category] = score
        
        # تحديد الفئة الرئيسية
        main_category = max(scores, key=scores.get) if scores else "unknown"
        confidence = scores[main_category] / max(len(self.keywords.get(main_category, [1])), 1)
        
        # البحث عن معلومات حساسة
        sensitive_info = self.extract_sensitive_info(combined_text)
        
        # حساب درجة الخطورة
        severity = self.calculate_severity(scores, sensitive_info)
        
        return {
            "main_category": main_category,
            "confidence": round(confidence, 2),
            "category_scores": scores,
            "sensitive_info_found": len(sensitive_info) > 0,
            "sensitive_info": sensitive_info,
            "severity_level": severity
        }
    
    def extract_sensitive_info(self, text: str) -> List[Dict]:
        """استخراج المعلومات الحساسة من النص"""
        sensitive_info = []
        
        for info_type, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                sensitive_info.append({
                    "type": info_type,
                    "value": match,
                    "context": self.get_context(text, match)
                })
        
        return sensitive_info
    
    def get_context(self, text: str, match: str, window: int = 50) -> str:
        """الحصول على السياق المحيط بالمطابقة"""
        try:
            index = text.index(match)
            start = max(0, index - window)
            end = min(len(text), index + len(match) + window)
            return text[start:end]
        except:
            return ""
    
    def calculate_severity(self, scores: Dict, sensitive_info: List) -> str:
        """حساب درجة الخطورة"""
        total_score = sum(scores.values())
        info_penalty = len(sensitive_info) * 2
        
        severity_score = total_score + info_penalty
        
        if severity_score >= 10:
            return "critical"
        elif severity_score >= 6:
            return "high"
        elif severity_score >= 3:
            return "medium"
        else:
            return "low"
    
    def suggest_related_cases(self, case_id: int) -> List[Dict]:
        """اقتراح قضايا مرتبطة"""
        conn = sqlite3.connect("cybershield.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # الحصول على معلومات القضية الحالية
        cursor.execute("""
        SELECT title, description, violation_type, reporter_contact 
        FROM cases WHERE id = ?
        """, (case_id,))
        
        current_case = cursor.fetchone()
        if not current_case:
            conn.close()
            return []
        
        # البحث عن قضايا متشابهة
        similar_cases = []
        
        # البحث بناءً على نوع المخالفة
        cursor.execute("""
        SELECT id, case_id, title, violation_type, created_at
        FROM cases 
        WHERE violation_type = ? AND id != ?
        ORDER BY created_at DESC
        LIMIT 5
        """, (current_case["violation_type"], case_id))
        
        similar_cases.extend(cursor.fetchall())
        
        # البحث بناءً على جهة الاتصال (إذا كانت متاحة)
        if current_case["reporter_contact"]:
            cursor.execute("""
            SELECT id, case_id, title, violation_type, created_at
            FROM cases 
            WHERE reporter_contact = ? AND id != ?
            ORDER BY created_at DESC
            LIMIT 3
            """, (current_case["reporter_contact"], case_id))
            
            similar_cases.extend(cursor.fetchall())
        
        # إزالة التكرارات
        unique_cases = []
        seen_ids = set()
        for case in similar_cases:
            if case["id"] not in seen_ids:
                seen_ids.add(case["id"])
                unique_cases.append(dict(case))
        
        conn.close()
        
        return unique_cases[:5]  # إرجاع 5 قضايا كحد أقصى
