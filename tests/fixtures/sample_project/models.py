"""Data models for the sample project."""

from dataclasses import dataclass


class BaseModel:
    """Base class for all models."""

    def validate(self):
        return True


class User(BaseModel):
    """Represents a user."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def greet(self) -> str:
        return f"Hello, {self.name}!"


class AdminUser(User):
    """An admin user with extra privileges."""

    def __init__(self, name: str, email: str, role: str = "admin"):
        super().__init__(name, email)
        self.role = role

    def has_permission(self, perm: str) -> bool:
        return True
