import re
import sqlite3
from typing import List, Dict, Set, Tuple
from collections import defaultdict

class NetworkDetector:
    def __init__(self):
        self.conn = sqlite3.connect("cybershield.db")
        self.conn.row_factory = sqlite3.Row
    
    def extract_usernames(self, text: str) -> List[str]:
        """استخراج أسماء المستخدمين من النص"""
        # أنماط أسماء المستخدمين في المنصات المختلفة
        patterns = [
            r'@(\w+)',  # @username
            r't\.me/(\w+)',  # Telegram
            r'twitter\.com/(\w+)',  # Twitter
            r'instagram\.com/(\w+)',  # Instagram
            r'facebook\.com/(\w+)',  # Facebook
            r'tiktok\.com/@(\w+)',  # TikTok
        ]
        
        usernames = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            usernames.update(matches)
        
        return list(usernames)
    
    def find_network_connections(self, case_id: int) -> Dict:
        """إيجاد روابط الشبكة للقضية"""
        # الحصول على محتوى القضية
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT title, description 
        FROM cases WHERE id = ?
        """, (case_id,))
        
        case = cursor.fetchone()
        if not case:
            return {}
        
        # استخراج أسماء المستخدمين
        case_text = f"{case['title']} {case['description']}"
        usernames = self.extract_usernames(case_text)
        
        # البحث عن قضايا أخرى تحتوي على نفس أسماء المستخدمين
        related_cases = []
        for username in usernames:
            cursor.execute("""
            SELECT c.id, c.case_id, c.title, c.violation_type, c.created_at
            FROM cases c
            WHERE (c.title LIKE ? OR c.description LIKE ?) 
            AND c.id != ?
            ORDER BY c.created_at DESC
            LIMIT 3
            """, (f'%{username}%', f'%{username}%', case_id))
            
            related_cases.extend(cursor.fetchall())
        
        # البحث في الأدلة
        cursor.execute("""
        SELECT description, url 
        FROM evidence 
        WHERE case_id = ?
        """, (case_id,))
        
        evidence = cursor.fetchall()
        
        evidence_usernames = set()
        for item in evidence:
            if item['description']:
                evidence_usernames.update(self.extract_usernames(item['description']))
            if item['url']:
                evidence_usernames.update(self.extract_usernames(item['url']))
        
        # البحث عن قضايا مرتبطة عبر الأدلة
        for username in evidence_usernames:
            cursor.execute("""
            SELECT DISTINCT c.id, c.case_id, c.title, c.violation_type, c.created_at
            FROM cases c
            JOIN evidence e ON c.id = e.case_id
            WHERE (e.description LIKE ? OR e.url LIKE ?) 
            AND c.id != ?
            ORDER BY c.created_at DESC
            LIMIT 3
            """, (f'%{username}%', f'%{username}%', case_id))
            
            related_cases.extend(cursor.fetchall())
        
        # إزالة التكرارات وتنظيم النتائج
        unique_cases = []
        seen_ids = set()
        for case_row in related_cases:
            if case_row['id'] not in seen_ids:
                seen_ids.add(case_row['id'])
                unique_cases.append(dict(case_row))
        
        # إنشاء أو تحديث شبكة
        if unique_cases:
            network_id = self.create_or_update_network(case_id, unique_cases)
        else:
            network_id = None
        
        return {
            "current_case_id": case_id,
            "extracted_usernames": usernames + list(evidence_usernames),
            "related_cases_count": len(unique_cases),
            "related_cases": unique_cases[:10],  # إرجاع 10 كحد أقصى
            "network_id": network_id
        }
    
    def create_or_update_network(self, case_id: int, related_cases: List[Dict]) -> str:
        """إنشاء أو تحديث شبكة مرتبطة"""
        cursor = self.conn.cursor()
        
        # التحقق مما إذا كانت القضية مرتبطة بشبكة موجودة
        cursor.execute("""
        SELECT network_id 
        FROM case_network 
        WHERE case_id = ?
        """, (case_id,))
        
        existing_network = cursor.fetchone()
        
        if existing_network:
            network_id = existing_network['network_id']
            
            # إضافة القضايا المرتبطة إلى الشبكة
            for related_case in related_cases:
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO case_network (case_id, network_id)
                    VALUES (?, ?)
                    """, (related_case['id'], network_id))
                except:
                    pass
        else:
            # إنشاء شبكة جديدة
            import uuid
            network_id = f"NET-{str(uuid.uuid4())[:8].upper()}"
            
            cursor.execute("""
            INSERT INTO networks (network_id, name, description)
            VALUES (?, ?, ?)
            """, (
                network_id,
                f"شبكة مرتبطة بالقضية #{case_id}",
                f"شبكة تلقائية تم إنشاؤها بواسطة النظام للقضية #{case_id}"
            ))
            
            # ربط القضية الحالية بالشبكة
            cursor.execute("""
            INSERT INTO case_network (case_id, network_id)
            VALUES (?, ?)
            """, (case_id, cursor.lastrowid))
            
            # ربط القضايا المرتبطة
            for related_case in related_cases:
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO case_network (case_id, network_id)
                    VALUES (?, ?)
                    """, (related_case['id'], cursor.lastrowid))
                except:
                    pass
        
        self.conn.commit()
        return network_id
    
    def get_network_details(self, network_id: str) -> Dict:
        """الحصول على تفاصيل الشبكة"""
        cursor = self.conn.cursor()
        
        # معلومات الشبكة الأساسية
        cursor.execute("""
        SELECT * FROM networks WHERE network_id = ?
        """, (network_id,))
        
        network = cursor.fetchone()
        if not network:
            return {}
        
        # القضايا المرتبطة
        cursor.execute("""
        SELECT c.* 
        FROM cases c
        JOIN case_network cn ON c.id = cn.case_id
        JOIN networks n ON cn.network_id = n.id
        WHERE n.network_id = ?
        ORDER BY c.created_at DESC
        """, (network_id,))
        
        cases = [dict(row) for row in cursor.fetchall()]
        
        # إحصائيات الشبكة
        stats = {
            "total_cases": len(cases),
            "violation_types": defaultdict(int),
            "status_distribution": defaultdict(int)
        }
        
        for case in cases:
            stats["violation_types"][case['violation_type']] += 1
            stats["status_distribution"][case['status']] += 1
        
        return {
            "network_info": dict(network),
            "cases": cases,
            "statistics": stats
        }
    
    def find_common_patterns(self, network_id: str) -> List[Dict]:
        """إيجاد الأنماط المشتركة في الشبكة"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
        SELECT c.description, e.description as evidence_desc, e.url
        FROM cases c
        JOIN case_network cn ON c.id = cn.case_id
        JOIN networks n ON cn.network_id = n.id
        LEFT JOIN evidence e ON c.id = e.case_id
        WHERE n.network_id = ?
        """, (network_id,))
        
        data = cursor.fetchall()
        
        # تحليل النصوص للعثور على أنماط مشتركة
        texts = []
        for row in data:
            if row['description']:
                texts.append(row['description'].lower())
            if row['evidence_desc']:
                texts.append(row['evidence_desc'].lower())
        
        # استخراج الكلمات الشائعة
        from collections import Counter
        import re
        
        all_words = []
        for text in texts:
            words = re.findall(r'\b\w{3,}\b', text)
            all_words.extend(words)
        
        word_counts = Counter(all_words)
        common_words = word_counts.most_common(20)
        
        # استخراج أسماء المستخدمين المشتركة
        all_usernames = set()
        for row in data:
            text = f"{row['description'] or ''} {row['evidence_desc'] or ''} {row['url'] or ''}"
            usernames = self.extract_usernames(text)
            all_usernames.update(usernames)
        
        return {
            "common_words": common_words,
            "shared_usernames": list(all_usernames),
            "total_texts_analyzed": len(texts)
        }
    
    def __del__(self):
        """إغلاق اتصال قاعدة البيانات"""
        if hasattr(self, 'conn'):
            self.conn.close()
