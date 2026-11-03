"""Dependencias de autenticacao OAuth2 Bearer (R9)."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import decode_access_token

# tokenUrl aponta para o endpoint de login (gera o botao "Authorize" no Swagger).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais invalidas ou token expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    email = decode_access_token(token)
    if not email:
        raise _credentials_exc
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise _credentials_exc
    return user
