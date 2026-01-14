from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
import uuid
import sqlite3

from app.core.security import get_current_user, check_permission, log_audit
from app.config import settings

router = APIRouter()

class CaseCreate(BaseModel):
    title: str
    description: str
    violation_type: str
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    assigned_to: Optional[int] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_case(
    case_data: CaseCreate,
    current_user: User = Depends(get_current_user)
):
    """إنشاء قضية جديدة"""
    # التحقق من الصلاحيات
    if not check_permission(current_user.role, "intake"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك بإنشاء قضايا"
        )
    
    # إنشاء معرف فريد للقضية
    case_id = f"CASE-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    conn = sqlite3.connect("cybershield.db")
    cursor = conn.cursor()
    
    try:
        # إدراج القضية في قاعدة البيانات
        cursor.execute('''
        INSERT INTO cases (case_id, title, description, violation_type, 
                          reporter_name, reporter_contact, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            case_id,
            case_data.title,
            case_data.description,
            case_data.violation_type,
            case_data.reporter_name,
            case_data.reporter_contact,
            current_user.id,
            "new"
        ))
        
        case_db_id = cursor.lastrowid
        
        conn.commit()
        
        # تسجيل النشاط
        log_audit(
            current_user.id, 
            "CREATE", 
            "CASE", 
            case_db_id, 
            f"إنشاء قضية جديدة: {case_data.title}"
        )
        
        return {
            "message": "تم إنشاء القضية بنجاح",
            "case_id": case_id,
            "db_id": case_db_id
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ في إنشاء القضية: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/")
async def get_cases(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """الحصول على قائمة القضايا"""
    offset = (page - 1) * limit
    
    conn = sqlite3.connect("cybershield.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM cases WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    cases = cursor.fetchall()
    
    # الحصول على العدد الإجمالي
    count_query = "SELECT COUNT(*) as total FROM cases"
    if status:
        count_query += " WHERE status = ?"
        cursor.execute(count_query, (status,))
    else:
        cursor.execute(count_query)
    
    total = cursor.fetchone()["total"]
    
    conn.close()
    
    return {
        "cases": cases,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user)
):
    """الحصول على تفاصيل قضية محددة"""
    conn = sqlite3.connect("cybershield.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # الحصول على القضية
    cursor.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
    case = cursor.fetchone()
    
    if not case:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="القضية غير موجودة"
        )
    
    # الحصول على الأدلة المرتبطة
    cursor.execute("SELECT * FROM evidence WHERE case_id = ?", (case["id"],))
    evidence_list = cursor.fetchall()
    
    # الحصول على الشبكات المرتبطة
    cursor.execute('''
    SELECT n.* FROM networks n
    JOIN case_network cn ON n.id = cn.network_id
    WHERE cn.case_id = ?
    ''', (case["id"],))
    networks = cursor.fetchall()
    
    # الحصول على سجل النشاطات
    cursor.execute('''
    SELECT al.*, u.username FROM audit_log al
    LEFT JOIN users u ON al.user_id = u.id
    WHERE al.entity_type = 'CASE' AND al.entity_id = ?
    ORDER BY al.created_at DESC
    LIMIT 50
    ''', (case["id"],))
    activity_log = cursor.fetchall()
    
    conn.close()
    
    return {
        "case": case,
        "evidence": evidence_list,
        "networks": networks,
        "activity_log": activity_log
    }

@router.put("/{case_id}")
async def update_case(
    case_id: str,
    update_data: CaseUpdate,
    current_user: User = Depends(get_current_user)
):
    """تحديث القضية"""
    if not check_permission(current_user.role, "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك بتحديث القضايا"
        )
    
    conn = sqlite3.connect("cybershield.db")
    cursor = conn.cursor()
    
    try:
        # الحصول على القضية الحالية
        cursor.execute("SELECT id, status FROM cases WHERE case_id = ?", (case_id,))
        case = cursor.fetchone()
        
        if not case:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="القضية غير موجودة"
            )
        
        # بناء استعلام التحديث
        update_fields = []
        update_values = []
        
        if update_data.title is not None:
            update_fields.append("title = ?")
            update_values.append(update_data.title)
        
        if update_data.description is not None:
            update_fields.append("description = ?")
            update_values.append(update_data.description)
        
        if update_data.status is not None:
            update_fields.append("status = ?")
            update_values.append(update_data.status)
            
            # إذا تم إغلاق القضية
            if update_data.status == "closed":
                update_fields.append("closed_at = ?")
                update_values.append(datetime.now().isoformat())
        
        if update_data.priority is not None:
            update_fields.append("priority = ?")
            update_values.append(update_data.priority)
        
        if update_data.assigned_to is not None:
            update_fields.append("assigned_to = ?")
            update_values.append(update_data.assigned_to)
        
        # إضافة تاريخ التحديث
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())
        
        # إضافة معرف القضية
        update_values.append(case_id)
        
        # تنفيذ التحديث
        update_query = f"UPDATE cases SET {', '.join(update_fields)} WHERE case_id = ?"
        cursor.execute(update_query, update_values)
        
        conn.commit()
        
        # تسجيل النشاط
        changes = []
        if update_data.status:
            changes.append(f"تغيير الحالة إلى: {update_data.status}")
        
        log_audit(
            current_user.id,
            "UPDATE",
            "CASE",
            case[0],
            f"تحديث القضية: {', '.join(changes) if changes else 'تحديث عام'}"
        )
        
        return {"message": "تم تحديث القضية بنجاح"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ في تحديث القضية: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/{case_id}/timeline")
async def get_case_timeline(
    case_id: str,
    current_user: User = Depends(get_current_user)
):
    """الحصول على الخط الزمني للقضية"""
    conn = sqlite3.connect("cybershield.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # الحصول على القضية
    cursor.execute("SELECT id, created_at FROM cases WHERE case_id = ?", (case_id,))
    case = cursor.fetchone()
    
    if not case:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="القضية غير موجودة"
        )
    
    # جمع جميع الأحداث
    timeline = []
    
    # 1. إنشاء القضية
    timeline.append({
        "type": "case_created",
        "timestamp": case["created_at"],
        "title": "إنشاء القضية",
        "description": "تم إنشاء القضية في النظام"
    })
    
    # 2. الأدلة المرفوعة
    cursor.execute(
        "SELECT uploaded_at, description FROM evidence WHERE case_id = ? ORDER BY uploaded_at",
        (case["id"],)
    )
    for evidence in cursor.fetchall():
        timeline.append({
            "type": "evidence_uploaded",
            "timestamp": evidence["uploaded_at"],
            "title": "رفع دليل",
            "description": evidence["description"] or "تم رفع دليل جديد"
        })
    
    # 3. تغييرات الحالة
    cursor.execute('''
    SELECT created_at, details FROM audit_log 
    WHERE entity_type = 'CASE' AND entity_id = ? 
    AND action = 'UPDATE'
    ORDER BY created_at
    ''', (case["id"],))
    
    for log in cursor.fetchall():
        timeline.append({
            "type": "status_change",
            "timestamp": log["created_at"],
            "title": "تغيير حالة",
            "description": log["details"]
        })
    
    # 4. التقارير المولدة
    cursor.execute(
        "SELECT generated_at, report_type FROM reports WHERE case_id = ? ORDER BY generated_at",
        (case["id"],)
    )
    for report in cursor.fetchall():
        timeline.append({
            "type": "report_generated",
            "timestamp": report["generated_at"],
            "title": "توليد تقرير",
            "description": f"تقرير {report['report_type']}"
        })
    
    # ترتيب الخط الزمني حسب التاريخ
    timeline.sort(key=lambda x: x["timestamp"])
    
    conn.close()
    
    return {"timeline": timeline}
