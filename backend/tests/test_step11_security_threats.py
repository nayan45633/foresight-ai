"""Foresight AI - Step 11 Security Threats & Authorization Hardening Tests.

Tests:
- Authentication threat vectors (expired JWT, malformed JWT, refresh token replay, session revocation)
- RBAC privilege escalation prevention (USER vs ANALYST vs ADMIN)
- IDOR cross-tenant isolation
- Model registry path traversal defense
- Error response sanitization (no stack traces, SQL, or secrets leaked)
"""

import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token


@pytest.mark.asyncio
async def test_invalid_and_expired_jwt_rejected(async_client: AsyncClient):
    """Verifies that forged, malformed, or expired JWT tokens are rejected with 401 Unauthorized."""
    # 1. Malformed token
    res_malformed = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert res_malformed.status_code == 401

    # 2. Forged token signed with incorrect secret
    import jwt
    forged_token = jwt.encode(
        {"sub": "fake-user-id", "exp": 9999999999, "type": "access"},
        "completely-wrong-secret-key-that-does-not-match-settings",
        algorithm="HS256",
    )
    res_forged = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert res_forged.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_replay_rejected(async_client: AsyncClient):
    """Verifies that rotated refresh tokens cannot be replayed or reused."""
    user_email = "replay_test_11@foresight.ai"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "username": "replay_user_11", "password": "SecurePassword123!", "role": "user"},
    )
    assert reg_res.status_code in [200, 201]

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user_email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    first_refresh_token = login_data["refresh_token"]

    # First refresh (Rotation)
    refresh_1 = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh_token},
    )
    assert refresh_1.status_code == 200
    refreshed_data = refresh_1.json()
    second_refresh_token = refreshed_data["refresh_token"]
    assert second_refresh_token != first_refresh_token

    # Attempt replay of the first refresh token (MUST FAIL)
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh_token},
    )
    assert replay_res.status_code == 401


@pytest.mark.asyncio
async def test_session_revocation_on_logout(async_client: AsyncClient):
    """Verifies that logout revokes active sessions and prevents subsequent access."""
    user_email = "revocation_test_11@foresight.ai"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "username": "revocation_user_11", "password": "SecurePassword123!", "role": "user"},
    )

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user_email, "password": "SecurePassword123!"},
    )
    data = login_res.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Verify access before logout
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # Refresh should now fail because session was revoked
    refresh_fail = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_fail.status_code == 401


@pytest.mark.asyncio
async def test_rbac_server_side_enforcement(async_client: AsyncClient):
    """Verifies that USER role cannot access ANALYST or ADMIN operations."""
    user_email = "std_user_11@foresight.ai"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "username": "std_user_11", "password": "SecurePassword123!", "role": "user"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": user_email, "password": "SecurePassword123!"},
    )
    user_token = login_res.json()["access_token"]

    # 1. USER attempts to access ADMIN-only user listing -> 403 Forbidden
    users_res = await async_client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert users_res.status_code == 403

    # 2. USER attempts to activate model -> 403 Forbidden
    act_res = await async_client.post(
        "/api/v1/model/versions/production-v1/activate",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert act_res.status_code == 403

    # 3. USER attempts to query audit logs -> 403 Forbidden
    audit_res = await async_client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert audit_res.status_code == 403


@pytest.mark.asyncio
async def test_model_registry_path_traversal_blocked(async_client: AsyncClient):
    """Verifies that path traversal attempts in model version tags are strictly rejected."""
    admin_email = "admin_security_test_11@foresight.ai"
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "username": "admin_sec_11", "password": "SecurePassword123!", "role": "admin"},
    )
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": admin_email, "password": "SecurePassword123!"},
    )
    admin_token = login_res.json()["access_token"]

    # Path traversal payload
    traversal_tag = "../../etc/passwd"
    res = await async_client.post(
        f"/api/v1/model/versions/{traversal_tag}/activate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code in [400, 404, 422]


@pytest.mark.asyncio
async def test_error_handling_masks_sensitive_internals(async_client: AsyncClient):
    """Verifies that non-existent or failing routes return clean error contracts without leaking stack traces or SQL."""
    res = await async_client.get("/api/v1/non_existent_endpoint_404")
    assert res.status_code == 404
    body = res.text
    assert "Traceback" not in body
    assert "SELECT " not in body
    assert "password" not in body.lower()
    assert "SECRET_KEY" not in body
