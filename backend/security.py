import hashlib
import os
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from .database import Audit, LoginAttempt, Owner, Session, now

COOKIE = "fluxosolar_session"
SESSION_SECONDS = 8 * 3600


def hash_password(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)
    return f"scrypt${salt}${value.hex()}"


def verify_password(password, encoded):
    _, salt, expected = encoded.split("$")
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return secrets.compare_digest(actual, expected)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def bootstrap(db):
    if db.scalar(select(Owner.id).limit(1)):
        return
    password = os.getenv("ADMIN_PASSWORD", "")
    if len(password) < 16 or password == "CHANGE_ME_WITH_16_OR_MORE_CHARACTERS":
        raise RuntimeError("Configure a unique ADMIN_PASSWORD with at least 16 characters.")
    db.add(Owner(username=os.getenv("ADMIN_USERNAME", "rapha"), password_hash=hash_password(password)))
    db.commit()


def authenticate(db, username, password, peer):
    cutoff = now() - timedelta(minutes=15)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created < cutoff))
    attempts = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.peer == peer))
    if attempts >= 10:
        db.commit()
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
    db.add(LoginAttempt(peer=peer))
    db.commit()  # Failed attempts must survive an HTTPException.
    owner = db.scalar(select(Owner).where(Owner.username == username))
    encoded = owner.password_hash if owner else "scrypt$dummy$" + "0" * 128
    valid = verify_password(password, encoded)
    if not owner or not valid:
        raise HTTPException(401, "Usuário ou senha inválidos.")
    token = secrets.token_urlsafe(48)
    db.execute(delete(Session).where(Session.expires < now()))
    db.add(Session(digest=digest(token), owner_id=owner.id, expires=now() + timedelta(seconds=SESSION_SECONDS)))
    db.add(Audit(action="login"))
    db.commit()
    return token
