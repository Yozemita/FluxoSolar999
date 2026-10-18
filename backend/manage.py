"""Owner password reset; reads credentials only from the injected environment."""
import argparse
import os
import sys
from pathlib import Path

if not __package__:
    directory = Path(__file__).resolve().parent
    sys.path.insert(0, str(directory.parent))
    __package__ = directory.name

from sqlalchemy import delete, select

from .database import Audit, Owner, Session, make_database
from .security import hash_password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["reset-password"])
    parser.parse_args()
    password = os.getenv("ADMIN_PASSWORD", "")
    if len(password) < 16 or password == "CHANGE_ME_WITH_16_OR_MORE_CHARACTERS":
        raise SystemExit("Configure ADMIN_PASSWORD securely before resetting.")
    engine, sessions = make_database()
    try:
        with sessions() as db:
            user = db.scalar(select(Owner).where(Owner.username == os.getenv("ADMIN_USERNAME", "rapha")))
            if not user:
                raise SystemExit("Owner not found; initialize the application first.")
            user.password_hash = hash_password(password)
            db.execute(delete(Session).where(Session.owner_id == user.id))
            db.add(Audit(action="owner.password_reset"))
            db.commit()
        print("Password updated and all owner sessions revoked.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
