from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel

from app.core.security import (
    authenticate_user,
    create_access_token,
    check_permission,
    log_audit
)
from app.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """تسجيل الدخول والحصول على توكن"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "id": user["id"]},
        expires_delta=access_token_expires
    )
    
    # تسجيل الدخول في سجل التدقيق
    log_audit(user["id"], "LOGIN", "USER", user["id"], "تسجيل دخول ناجح")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """الحصول على بيانات المستخدم الحالي"""
    # هنا يجب فك تشفير التوكن والتحقق منه
    # هذا مثال مبسط
    return User(
        id=1,
        username="abujamal",
        full_name="أبو جمال",
        email="admin@cybershield.dj",
        role="admin"
    )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """تسجيل الخروج"""
    log_audit(current_user.id, "LOGOUT", "USER", current_user.id, "تسجيل خروج")
    return {"message": "تم تسجيل الخروج بنجاح"}
