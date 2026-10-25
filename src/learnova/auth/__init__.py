"""Authentication: phone + OTP sessions (primary) and Clerk verification (legacy)."""

from learnova.auth import phone
from learnova.auth.clerk import AuthError, user_id_from_header, verify_token

__all__ = ["AuthError", "verify_token", "user_id_from_header", "phone"]
