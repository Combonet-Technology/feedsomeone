from functools import wraps


class RegisterUser:

    def __init__(self):
        self.password = 'A-secure-test-password-2026'
        self.email = 'testuser@example.com'

    @property
    def spawn(self):
        return {
            'password': self.password,
            'email': self.email,
        }


class MockUser:

    def __init__(self):
        self.username = 'testuser'
        self.email = 'testuser@example.com'
        self.first_name = 'Ben'
        self.last_name = 'Buffer'

    @property
    def spawn(self):
        return {
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
        }


def mock_decorator(*args, **kwargs):
    """Decorate by doing nothing."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_function

    return decorator
