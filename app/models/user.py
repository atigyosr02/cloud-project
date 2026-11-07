from flask_login import UserMixin

from app.models.db import fetch_one


class User(UserMixin):
    def __init__(self, row: dict):
        self.id = str(row["id"])
        self.email = row["email"]
        self.name = row["name"]
        self.role = row["role"]
        self._is_active = row["is_active"]

    @property
    def is_active(self) -> bool:
        return self._is_active


def get_user_by_id(user_id: str) -> User | None:
    row = fetch_one(
        "SELECT id, email, name, role, is_active FROM users WHERE id = %s AND is_active = TRUE",
        (user_id,),
    )
    return User(row) if row else None