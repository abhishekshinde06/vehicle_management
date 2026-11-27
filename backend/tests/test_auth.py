"""
Authentication Tests
--------------------
Tests for the authentication layer:

  1. test_login_owner_returns_valid_jwt        — owner can log in, JWT is valid
  2. test_login_operator_returns_valid_jwt     — operator can log in, JWT is valid
  3. test_login_wrong_password                 — wrong password → 401
  4. test_login_unknown_user                   — unknown user → 401
  5. test_me_endpoint                          — /me returns correct profile
  6. test_me_requires_auth                     — /me without token → 401
  7. test_public_signup_is_disabled            — /signup removed → 404
  8. test_owner_can_create_operator            — owner creates operator → 201
  9. test_operator_cannot_create_operator      — operator cannot create accounts → 403
  10. test_create_operator_duplicate_username  — duplicate username → 400
  11. test_list_operators_owner_only           — owner sees operator list
  12. test_list_operators_operator_forbidden   — operator cannot list operators → 403
  13. test_jwt_token_structure                 — JWT has correct claims (sub, role, exp)
  14. test_inactive_user_cannot_login          — deactivated account → 403

Fixtures use an in-memory SQLite database — no PostgreSQL required.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jose import jwt

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User

# ---------------------------------------------------------------------------
# In-memory SQLite test database (isolated per test session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///./test_auth.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Create all tables before tests, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def db():
    """Module-scoped DB session for direct record insertion."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(db):
    """TestClient wired to the in-memory DB, with seeded owner + operator."""
    # Seed users directly — bypasses the disabled public signup
    owner = User(
        username="test_owner",
        password_hash=get_password_hash("ownerpass"),
        role="owner",
        full_name="Test Owner",
        is_active=True,
    )
    operator = User(
        username="test_operator",
        password_hash=get_password_hash("operatorpass"),
        role="operator",
        full_name="Test Operator",
        is_active=True,
    )
    inactive = User(
        username="inactive_user",
        password_hash=get_password_hash("pass123"),
        role="operator",
        full_name="Inactive User",
        is_active=False,
    )
    db.add_all([owner, operator, inactive])
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login(client, username, password):
    """POST /api/auth/login and return response JSON."""
    return client.post("/api/auth/login", data={"username": username, "password": password})


def owner_headers(client):
    res = login(client, "test_owner", "ownerpass")
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def operator_headers(client):
    res = login(client, "test_operator", "operatorpass")
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLogin:

    def test_login_owner_returns_valid_jwt(self, client):
        """Owner credentials produce a 200 with a token payload."""
        res = login(client, "test_owner", "ownerpass")
        assert res.status_code == 200
        body = res.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "owner"
        assert body["username"] == "test_owner"
        assert "access_token" in body
        assert "user_id" in body
        assert len(body["access_token"]) > 20

    def test_login_operator_returns_valid_jwt(self, client):
        """Operator credentials produce a 200 with a token payload."""
        res = login(client, "test_operator", "operatorpass")
        assert res.status_code == 200
        body = res.json()
        assert body["role"] == "operator"
        assert body["username"] == "test_operator"

    def test_login_wrong_password(self, client):
        """Wrong password → 401 Unauthorized."""
        res = login(client, "test_owner", "wrongpassword")
        assert res.status_code == 401
        assert "Incorrect" in res.json()["detail"]

    def test_login_unknown_user(self, client):
        """Non-existent username → 401 Unauthorized."""
        res = login(client, "nobody", "somepass")
        assert res.status_code == 401

    def test_inactive_user_cannot_login(self, client):
        """Deactivated account → 403 Forbidden."""
        res = login(client, "inactive_user", "pass123")
        assert res.status_code == 403
        assert "deactivated" in res.json()["detail"].lower()


class TestJWTStructure:

    def test_jwt_token_structure(self, client):
        """
        Decoded JWT must contain:
          - sub  (user UUID string)
          - role ('owner' or 'operator')
          - exp  (expiry timestamp)
        """
        res = login(client, "test_owner", "ownerpass")
        token = res.json()["access_token"]
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert "sub" in payload, "JWT missing 'sub' claim"
        assert "role" in payload, "JWT missing 'role' claim"
        assert "exp" in payload, "JWT missing 'exp' claim"
        assert payload["role"] == "owner"
        assert isinstance(payload["sub"], str)
        assert len(payload["sub"]) > 0


class TestMeEndpoint:

    def test_me_returns_correct_profile(self, client):
        """Authenticated user gets back their own profile."""
        res = client.get("/api/auth/me", headers=owner_headers(client))
        assert res.status_code == 200
        body = res.json()
        assert body["username"] == "test_owner"
        assert body["role"] == "owner"
        assert body["is_active"] is True
        assert "password" not in body
        assert "password_hash" not in body

    def test_me_requires_auth(self, client):
        """No token → 401."""
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_me_with_invalid_token(self, client):
        """Garbage token → 401."""
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer notavalidtoken"})
        assert res.status_code == 401


class TestPublicSignupDisabled:

    def test_public_signup_endpoint_does_not_exist(self, client):
        """
        POST /api/auth/signup must return 404 — the endpoint has been removed.
        Owner accounts are created only via seed.py.
        """
        res = client.post(
            "/api/auth/signup",
            json={"username": "hacker", "password": "hacker123"},
        )
        assert res.status_code == 404, (
            f"Expected 404 (endpoint removed) but got {res.status_code}. "
            "Public owner signup must be disabled for the single-transporter MVP."
        )


class TestCreateOperator:

    def test_owner_can_create_operator(self, client):
        """Authenticated owner creates a new operator → 201 with correct role."""
        payload = {
            "username": "new_driver",
            "password": "driverpass",
            "full_name": "New Driver",
        }
        res = client.post("/api/auth/create-operator", json=payload, headers=owner_headers(client))
        assert res.status_code == 201
        body = res.json()
        assert body["username"] == "new_driver"
        assert body["role"] == "operator"
        assert body["is_active"] is True
        assert "password_hash" not in body

    def test_operator_cannot_create_operator(self, client):
        """Operator calling create-operator → 403 Forbidden."""
        payload = {"username": "another_driver", "password": "password123", "full_name": "Another Driver"}
        res = client.post("/api/auth/create-operator", json=payload, headers=operator_headers(client))
        assert res.status_code == 403

    def test_unauthenticated_cannot_create_operator(self, client):
        """No token → 401."""
        res = client.post("/api/auth/create-operator", json={"username": "valid_user", "password": "password123", "full_name": "Valid User"})
        assert res.status_code == 401

    def test_create_operator_duplicate_username(self, client):
        """Duplicate username → 400 Bad Request."""
        payload = {"username": "test_operator", "password": "somepassword", "full_name": "Test Operator"}
        res = client.post("/api/auth/create-operator", json=payload, headers=owner_headers(client))
        assert res.status_code == 400
        assert "already taken" in res.json()["detail"]

    def test_create_operator_short_password(self, client):
        """Password shorter than 8 chars → 422 Unprocessable Entity."""
        payload = {"username": "shortpass_driver", "password": "abc", "full_name": "Short Pass"}
        res = client.post("/api/auth/create-operator", json=payload, headers=owner_headers(client))
        assert res.status_code == 422

    def test_create_operator_requires_full_name(self, client):
        """Missing or blank full_name → 422 Unprocessable Entity."""
        res_missing = client.post(
            "/api/auth/create-operator",
            json={"username": "noname_driver", "password": "driverpass99"},
            headers=owner_headers(client),
        )
        assert res_missing.status_code == 422

        res_blank = client.post(
            "/api/auth/create-operator",
            json={"username": "blankname_driver", "password": "driverpass99", "full_name": "   "},
            headers=owner_headers(client),
        )
        assert res_blank.status_code == 422

    def test_create_operator_rejects_whitespace_password_and_username(self, client):
        """Whitespace-only or space-containing password/username → 422."""
        res_ws_pass = client.post(
            "/api/auth/create-operator",
            json={"username": "ws_pass_driver", "password": "        ", "full_name": "WS Pass"},
            headers=owner_headers(client),
        )
        assert res_ws_pass.status_code == 422

        res_space_pass = client.post(
            "/api/auth/create-operator",
            json={"username": "sp_pass_driver", "password": "pass word1", "full_name": "Space Pass"},
            headers=owner_headers(client),
        )
        assert res_space_pass.status_code == 422

        res_ws_user = client.post(
            "/api/auth/create-operator",
            json={"username": "   ", "password": "driverpass99", "full_name": "WS User"},
            headers=owner_headers(client),
        )
        assert res_ws_user.status_code == 422

        res_space_user = client.post(
            "/api/auth/create-operator",
            json={"username": "bad user", "password": "driverpass99", "full_name": "Space User"},
            headers=owner_headers(client),
        )
        assert res_space_user.status_code == 422

    def test_new_operator_can_login(self, client):
        """
        Operator created by owner can immediately log in and receive a valid JWT.
        End-to-end: create → login → verify token role.
        """
        # Create
        create_res = client.post(
            "/api/auth/create-operator",
            json={"username": "loginable_driver", "password": "driverpass99", "full_name": "Loginable Driver"},
            headers=owner_headers(client),
        )
        assert create_res.status_code == 201

        # Login
        login_res = login(client, "loginable_driver", "driverpass99")
        assert login_res.status_code == 200
        body = login_res.json()
        assert body["role"] == "operator"

        # Verify JWT claims
        payload = jwt.decode(
            body["access_token"],
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert payload["role"] == "operator"


class TestListOperators:

    def test_owner_can_list_operators(self, client):
        """Owner sees a list of active operators."""
        res = client.get("/api/auth/operators", headers=owner_headers(client))
        assert res.status_code == 200
        operators = res.json()
        assert isinstance(operators, list)
        assert len(operators) >= 1
        usernames = [o["username"] for o in operators]
        assert "test_operator" in usernames
        # Inactive users must NOT appear
        assert "inactive_user" not in usernames
        # Every entry must be an operator
        for op in operators:
            assert op["role"] == "operator"
            assert op["is_active"] is True

    def test_operator_cannot_list_operators(self, client):
        """Operator calling /operators → 403 Forbidden."""
        res = client.get("/api/auth/operators", headers=operator_headers(client))
        assert res.status_code == 403

    def test_unauthenticated_cannot_list_operators(self, client):
        """No token → 401."""
        res = client.get("/api/auth/operators")
        assert res.status_code == 401
