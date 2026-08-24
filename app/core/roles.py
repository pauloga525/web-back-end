from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


ROLE_HIERARCHY = {
    Role.SUPER_ADMIN: 4,
    Role.ADMIN: 3,
    Role.EDITOR: 2,
    Role.VIEWER: 1,
}


def has_role(user_role: str, required_roles: list) -> bool:
    return user_role in required_roles
