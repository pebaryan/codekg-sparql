"""Main application module."""

from config import parse_config, validate_config
from models import User, AdminUser


def create_app(config_path: str):
    """Create and configure the application."""
    config = parse_config(config_path)
    if not validate_config(config):
        raise ValueError("Invalid config")
    return {"config": config}


def handle_request(user: User, action: str):
    """Handle a user request."""
    user.validate()
    greeting = user.greet()
    print(greeting)
    return process_action(action)


def process_action(action: str):
    """Process a single action."""
    return {"action": action, "status": "ok"}


def main():
    app = create_app("config.yaml")
    admin = AdminUser("Admin", "admin@example.com")
    handle_request(admin, "dashboard")
