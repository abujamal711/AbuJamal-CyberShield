from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List
import aiofiles

from app.core.security import get_current_user, check_permission, log_audit
from app.modules.evidence_engine.evidence_manager import EvidenceManager

router = APIRouter()
evidence_manager = EvidenceManager()

@router.post("/upload")
async def upload_evidence(
    case_id: int = Form(...),
    evidence_type: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """رفع دليل جديد"""
    if not check_permission(current_user.role, "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك برفع الأدلة"
        )
    
    # قراءة محتوى الملف
    file_content = await file.read()
    
    # حفظ الدليل
    result = evidence_manager.save_evidence(
        case_id=case_id,
        evidence_type=evidence_type,
        file_content=file_content,
        filename=file.filename,
        description=description,
        uploaded_by=current_user.id
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return result

@router.post("/archive-url")
async def archive_url(
    case_id: int = Form(...),
    url: str = Form(...),
    description: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """أرشفة رابط كدليل"""
    if not check_permission(current_user.role, "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك بأرشفة الروابط"
        )
    
    # أرشفة الرابط
    result = evidence_manager.archive_url(
        url=url,
        case_id=case_id,
        uploaded_by=current_user.id
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return result

@router.get("/{evidence_id}")
async def get_evidence(
    evidence_id: int,
    current_user: User = Depends(get_current_user)
):
    """الحصول على معلومات الدليل"""
    info = evidence_manager.get_evidence_info(evidence_id)
    
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الدليل غير موجود"
        )
    
    # التحقق من صلاحية الوصول للقضية
    conn = sqlite3.connect("cybershield.db")
    cursor = conn.cursor()
    cursor.execute("SELECT case_id FROM evidence WHERE id = ?", (evidence_id,))
    evidence_case = cursor.fetchone()
    conn.close()
    
    if evidence_case:
        # يمكن إضافة التحقق من صلاحية الوصول للقضية هنا
        pass
    
    return info

@router.get("/{evidence_id}/verify")
async def verify_evidence(
    evidence_id: int,
    current_user: User = Depends(get_current_user)
):
    """التحقق من سلامة الدليل"""
    is_valid = evidence_manager.verify_integrity(evidence_id)
    
    log_audit(
        current_user.id,
        "VERIFY",
        "EVIDENCE",
        evidence_id,
        f"التحقق من سلامة الدليل: {'ناجح' if is_valid else 'فشل'}"
    )
    
    return {
        "evidence_id": evidence_id,
        "integrity_verified": is_valid,
        "verified_at": datetime.now().isoformat()
    }
