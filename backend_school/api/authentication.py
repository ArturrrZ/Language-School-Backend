from rest_framework.authentication import SessionAuthentication


class CookieSessionAuthentication(SessionAuthentication):
    """Session-based authentication for browser clients using Django session cookies."""
