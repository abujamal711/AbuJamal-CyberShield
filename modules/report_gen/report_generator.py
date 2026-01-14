from datetime import datetime
import sqlite3
from typing import Dict, Optional
import json

class ReportGenerator:
    def __init__(self):
        self.conn = sqlite3.connect("cybershield.db")
        self.conn.row_factory = sqlite3.Row
    
    def generate_case_report(self, case_id: int, report_type: str = "detailed") -> Dict:
        """توليد تقرير مفصل للقضية"""
        cursor = self.conn.cursor()
        
        # معلومات القضية الأساسية
        cursor.execute("""
        SELECT c.*, u1.username as created_by_name, u2.username as assigned_to_name
        FROM cases c
        LEFT JOIN users u1 ON c.created_by = u1.id
        LEFT JOIN users u2 ON c.assigned_to = u2.id
        WHERE c.id = ?
        """, (case_id,))
        
        case = cursor.fetchone()
        if not case:
            return {"error": "القضية غير موجودة"}
        
        # الأدلة المرتبطة
        cursor.execute("""
        SELECT * FROM evidence 
        WHERE case_id = ?
        ORDER BY uploaded_at
        """, (case_id,))
        
        evidence_list = [dict(row) for row in cursor.fetchall()]
        
        # الشبكات المرتبطة
        cursor.execute("""
        SELECT n.* 
        FROM networks n
        JOIN case_network cn ON n.id = cn.network_id
        WHERE cn.case_id = ?
        """, (case_id,))
        
        networks = [dict(row) for row in cursor.fetchall()]
        
        # سجل الأنشطة
        cursor.execute("""
        SELECT al.*, u.username 
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.entity_type = 'CASE' AND al.entity_id = ?
        ORDER BY al.created_at DESC
        LIMIT 20
        """, (case_id,))
        
        activity_log = [dict(row) for row in cursor.fetchall()]
        
        # توليد معرف التقرير
        import uuid
        report_id = f"REP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        
        # محتوى التقرير
        report_content = self._format_report_content(
            case=dict(case),
            evidence=evidence_list,
            networks=networks,
            activity_log=activity_log,
            report_type=report_type
        )
        
        # حفظ التقرير في قاعدة البيانات
        cursor.execute("""
        INSERT INTO reports (report_id, case_id, report_type, content, generated_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report_id,
            case_id,
            report_type,
            report_content,
            datetime.now().isoformat(),
            "generated"
        ))
        
        report_db_id = cursor.lastrowid
        self.conn.commit()
        
        return {
            "report_id": report_id,
            "case_id": case_id,
            "report_type": report_type,
            "generated_at": datetime.now().isoformat(),
            "content_preview": report_content[:500] + "..." if len(report_content) > 500 else report_content,
            "download_url": f"/api/reports/{report_id}/download"
        }
    
    def _format_report_content(self, case: Dict, evidence: List, networks: List, 
                               activity_log: List, report_type: str) -> str:
        """تنسيق محتوى التقرير"""
        from app.config import settings
        
        violation_type_ar = settings.VIOLATION_TYPES.get(case['violation_type'], case['violation_type'])
        status_ar = settings.CASE_STATUS.get(case['status'], case['status'])
        
        # رأس التقرير
        content = f"""
        ========================================
        تقرير قضية - Abu Jamal CyberShield
        ========================================
        
        معلومات أساسية:
        ---------------
        معرف القضية: {case['case_id']}
        العنوان: {case['title']}
        نوع المخالفة: {violation_type_ar}
        الحالة: {status_ar}
        الأولوية: {case['priority']}
        تاريخ الإنشاء: {case['created_at']}
        منشئ القضية: {case.get('created_by_name', 'غير معروف')}
        المسند إلى: {case.get('assigned_to_name', 'غير معين')}
        
        وصف القضية:
        -----------
        {case['description'] or 'لا يوجد وصف'}
        
        معلومات المُبلغ:
        ---------------
        الاسم: {case['reporter_name'] or 'غير محدد'}
        جهة الاتصال: {case['reporter_contact'] or 'غير محددة'}
        """
        
        # قسم الأدلة
        if evidence:
            content += f"""
            
            الأدلة الجنائية ({len(evidence)}):
            --------------------------
            """
            
            for idx, ev in enumerate(evidence, 1):
                content += f"""
            {idx}. نوع الدليل: {ev['evidence_type']}
                الوصف: {ev['description'] or 'لا يوجد وصف'}
                اسم الملف: {ev['filename']}
                بصمة الملف (SHA256): {ev['file_hash']}
                تاريخ الرفع: {ev['uploaded_at']}
                رابط: {ev['url'] or 'لا يوجد رابط'}
                """
        
        # قسم الشبكات
        if networks:
            content += f"""
            
            الشبكات المرتبطة ({len(networks)}):
            ----------------------------
            """
            
            for idx, net in enumerate(networks, 1):
                content += f"""
            {idx}. معرف الشبكة: {net['network_id']}
                الاسم: {net['name'] or 'لا يوجد اسم'}
                الوصف: {net['description'] or 'لا يوجد وصف'}
                """
        
        # قسم سجل الأنشطة
        if activity_log:
            content += f"""
            
            سجل الأنشطة (آخر {len(activity_log)} نشاط):
            -----------------------------------
            """
            
            for log in activity_log:
                content += f"""
            [{log['created_at']}] {log['username'] or 'النظام'} - {log['action']}
                التفاصيل: {log['details'] or 'لا توجد تفاصيل'}
                """
        
        # تذييل التقرير
        content += f"""
        
        ========================================
        معلومات النظام:
        --------------
        النظام: {settings.APP_NAME}
        الإصدار: {settings.APP_VERSION}
        وقت توليد التقرير: {datetime.now().isoformat()}
        نوع التقرير: {report_type}
        
        ملاحظة:
        ------
        هذا التقرير تم توليده تلقائيًا بواسطة نظام Abu Jamal CyberShield.
        جميع المعلومات الموجودة في هذا التقرير موثقة رقميًا وغير قابلة للتعديل.
        
        ========================================
        """
        
        return content
    
    def generate_network_report(self, network_id: str) -> Dict:
        """توليد تقرير للشبكة"""
        from app.modules.network_analysis.network_detector import NetworkDetector
        
        network_detector = NetworkDetector()
        network_details = network_detector.get_network_details(network_id)
        
        if not network_details:
            return {"error": "الشبكة غير موجودة"}
        
        # توليد معرف التقرير
        import uuid
        report_id = f"NET-REP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        
        # تنسيق محتوى التقرير
        content = f"""
        ========================================
        تقرير شبكة - Abu Jamal CyberShield
        ========================================
        
        معلومات الشبكة:
        ---------------
        معرف الشبكة: {network_details['network_info']['network_id']}
        الاسم: {network_details['network_info']['name']}
        الوصف: {network_details['network_info']['description']}
        تاريخ الإنشاء: {network_details['network_info']['created_at']}
        
        إحصائيات الشبكة:
        ---------------
        عدد القضايا: {network_details['statistics']['total_cases']}
        
        توزيع أنواع المخالفات:
        """
        
        for violation_type, count in network_details['statistics']['violation_types'].items():
            violation_ar = settings.VIOLATION_TYPES.get(violation_type, violation_type)
            content += f"        - {violation_ar}: {count} قضايا\n"
        
        content += f"""
        توزيع حالات القضايا:
        """
        
        for status, count in network_details['statistics']['status_distribution'].items():
            status_ar = settings.CASE_STATUS.get(status, status)
            content += f"        - {status_ar}: {count} قضايا\n"
        
        # القضايا في الشبكة
        content += f"""
        
        القضايا في الشبكة ({len(network_details['cases'])}):
        ---------------------------
        """
        
        for idx, case in enumerate(network_details['cases'][:20], 1):  # أول 20 قضية
            violation_ar = settings.VIOLATION_TYPES.get(case['violation_type'], case['violation_type'])
            status_ar = settings.CASE_STATUS.get(case['status'], case['status'])
            
            content += f"""
        {idx}. {case['case_id']} - {case['title']}
            النوع: {violation_ar}
            الحالة: {status_ar}
            التاريخ: {case['created_at']}
            """
        
        if len(network_details['cases']) > 20:
            content += f"""
        ... و {len(network_details['cases']) - 20} قضايا إضافية
            """
        
        # الأنماط المشتركة
        patterns = network_detector.find_common_patterns(network_id)
        if patterns['common_words'] or patterns['shared_usernames']:
            content += f"""
            
            الأنماط المشتركة:
            ----------------
            تم تحليل {patterns['total_texts_analyzed']} نص
            
            الكلمات الأكثر شيوعًا:
            """
            
            for word, count in patterns['common_words'][:10]:
                content += f"            - {word}: {count} مرة\n"
            
            if patterns['shared_usernames']:
                content += f"""
            أسماء المستخدمين المشتركة ({len(patterns['shared_usernames'])}):
                """
                
                for username in patterns['shared_usernames'][:15]:
                    content += f"            - {username}\n"
        
        # تذييل التقرير
        content += f"""
        
        ========================================
        معلومات النظام:
        --------------
        النظام: {settings.APP_NAME}
        الإصدار: {settings.APP_VERSION}
        وقت توليد التقرير: {datetime.now().isoformat()}
        نوع التقرير: تقرير شبكة
        
        ملاحظة:
        ------
        هذا التقرير يوضح الروابط بين القضايا المختلفة في الشبكة.
        يمكن استخدامه لتقديم بلاغ جماعي للجهات المختصة.
        
        ========================================
        """
        
        # حفظ التقرير
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO reports (report_id, report_type, content, generated_at, status)
        VALUES (?, ?, ?, ?, ?)
        """, (
            report_id,
            "network_report",
            content,
            datetime.now().isoformat(),
            "generated"
        ))
        
        self.conn.commit()
        
        return {
            "report_id": report_id,
            "network_id": network_id,
            "report_type": "network_report",
            "generated_at": datetime.now().isoformat(),
            "cases_in_network": len(network_details['cases']),
            "download_url": f"/api/reports/{report_id}/download"
        }
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """الحصول على التقرير"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,))
        
        report = cursor.fetchone()
        if not report:
            return None
        
        return dict(report)
    
    def __del__(self):
        """إغلاق اتصال قاعدة البيانات"""
        if hasattr(self, 'conn'):
            self.conn.close()
