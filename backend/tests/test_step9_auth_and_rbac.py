"""Foresight AI - Step 9 Authentication & RBAC Test Suite."""

import pytest
from httpx import AsyncClient
from app.core.security import get_password_hash, verify_password


@pytest.mark.asyncio
async def test_password_hashing_and_verification():
    """Verifies bcrypt password hashing, salting, and verification with 72-byte truncation."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert hashed.startswith("$2b$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

    # Test long password (>72 bytes)
    long_pass = "A" * 100
    hashed_long = get_password_hash(long_pass)
    assert verify_password(long_pass, hashed_long) is True
    assert verify_password("A" * 72, hashed_long) is True


@pytest.mark.asyncio
async def test_user_registration_and_duplicate_prevention(async_client: AsyncClient):
    """Verifies user registration, role defaults, and duplicate email/username rejection."""
    reg_payload = {
        "email": "analyst_soc1@foresight.ai",
        "username": "soc_analyst1",
        "password": "Password12345!",
        "full_name": "SOC Analyst One",
        "role": "analyst",
    }
    res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == reg_payload["email"]
    assert data["username"] == reg_payload["username"]
    assert data["role"] == "analyst"
    assert data["is_active"] is True
    assert "hashed_password" not in data

    # Attempt duplicate registration
    res_dup = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert res_dup.status_code == 400
    err_data = res_dup.json()
    assert "error" in err_data
    assert err_data["error"]["code"] == "HTTP_400"


@pytest.mark.asyncio
async def test_login_and_token_issuance(async_client: AsyncClient):
    """Verifies login returns access and refresh tokens, updates session, and rejects invalid credentials."""
    user_payload = {
        "email": "test_login_user@foresight.ai",
        "username": "login_test_user",
        "password": "ValidPassword123!",
        "full_name": "Login Test User",
        "role": "analyst",
    }
    reg = await async_client.post("/api/v1/auth/register", json=user_payload)
    assert reg.status_code == 201

    # Invalid password login
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "login_test_user", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "UNAUTHORIZED"

    # Valid login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "login_test_user", "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0

    # Read profile via /auth/me with access token
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "login_test_user"


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation(async_client: AsyncClient):
    """Verifies refresh token rotation, issuing new tokens, and revoking expired/logged-out sessions."""
    user_payload = {
        "email": "refresh_user@foresight.ai",
        "username": "refresh_user",
        "password": "ValidPassword123!",
        "role": "analyst",
    }
    await async_client.post("/api/v1/auth/register", json=user_payload)

    # Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "refresh_user", "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    access_token_1 = tokens["access_token"]
    refresh_token_1 = tokens["refresh_token"]

    # Refresh
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert refresh_res.status_code == 200
    rotated_tokens = refresh_res.json()
    assert "access_token" in rotated_tokens
    assert "refresh_token" in rotated_tokens
    refresh_token_2 = rotated_tokens["refresh_token"]
    assert refresh_token_2 != refresh_token_1

    # Attempt to reuse old refresh token 1 -> MUST FAIL (token rotation revocation)
    reuse_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert reuse_res.status_code == 401

    # Logout with rotated token
    headers = {"Authorization": f"Bearer {rotated_tokens['access_token']}"}
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": refresh_token_2},
    )
    assert logout_res.status_code == 200

    # Attempt to use refresh token 2 after logout -> MUST FAIL
    post_logout_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert post_logout_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_and_admin_authorization(async_client: AsyncClient):
    """Verifies RBAC access restrictions: admins can list users/models; regular users are forbidden."""
    # 1. Register normal user
    normal_payload = {
        "email": "normal_user@foresight.ai",
        "username": "normal_user",
        "password": "Password123!",
        "role": "user",
    }
    await async_client.post("/api/v1/auth/register", json=normal_payload)
    login_norm = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "normal_user", "password": "Password123!"},
    )
    norm_token = login_norm.json()["access_token"]
    norm_headers = {"Authorization": f"Bearer {norm_token}"}

    # 2. Register admin user
    admin_payload = {
        "email": "admin_user@foresight.ai",
        "username": "admin_user",
        "password": "AdminPassword123!",
        "role": "admin",
    }
    await async_client.post("/api/v1/auth/register", json=admin_payload)
    login_admin = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin_user", "password": "AdminPassword123!"},
    )
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Normal user attempts to list users -> 403 Forbidden
    res_forbidden = await async_client.get("/api/v1/auth/users", headers=norm_headers)
    assert res_forbidden.status_code == 403
    assert res_forbidden.json()["error"]["code"] == "FORBIDDEN"

    # 4. Admin user lists users -> 200 OK
    res_admin = await async_client.get("/api/v1/auth/users", headers=admin_headers)
    assert res_admin.status_code == 200
    users_list = res_admin.json()
    assert len(users_list) >= 2

    # 5. Normal user attempts to register model version -> 403 Forbidden
    model_payload = {
        "version_tag": "v1.1.0-candidate",
        "model_architecture": "TemporalGradientBoosting",
        "brier_score": 0.008,
        "expected_calibration_error": 0.005,
    }
    res_mod_forbid = await async_client.post("/api/v1/model/versions", headers=norm_headers, json=model_payload)
    assert res_mod_forbid.status_code == 403

    # 6. Admin user registers model version -> 201 Created
    res_mod_admin = await async_client.post("/api/v1/model/versions", headers=admin_headers, json=model_payload)
    assert res_mod_admin.status_code == 201
    assert res_mod_admin.json()["version_tag"] == "v1.1.0-candidate"

    # 7. Admin activates the model version -> 200 OK
    res_act = await async_client.post("/api/v1/model/versions/v1.1.0-candidate/activate", headers=admin_headers)
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIVE"
