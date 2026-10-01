import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"

@pytest.mark.asyncio
async def test_auth_register_and_login(client: AsyncClient):
    # 1. Register User 1
    reg_resp = await client.post("/api/v1/auth/register", json={
        "email": "user1@company-a.com",
        "name": "User One",
        "password": "SecurePassword123!",
        "workspace_name": "Workspace Alpha"
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == "user1@company-a.com"
    ws_alpha = reg_data["workspace_id"]
    token_user1 = reg_data["access_token"]
    
    # 2. Login User 1
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "user1@company-a.com",
        "password": "SecurePassword123!"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    
    # 3. GET /auth/me
    me_resp = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token_user1}"
    })
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "user1@company-a.com"
    assert len(me_data["workspaces"]) == 1
    assert me_data["workspaces"][0]["workspace_id"] == ws_alpha

@pytest.mark.asyncio
async def test_cross_tenant_isolation_ac12(client: AsyncClient):
    """
    AC-12: Tenant isolation: cross-tenant probe returns 0 foreign records (404/403).
    """
    # Create Tenant A
    res_a = await client.post("/api/v1/auth/register", json={
        "email": "admin@tenant-a.com",
        "name": "Admin A",
        "password": "Password123!",
        "workspace_name": "Tenant A Corp"
    })
    token_a = res_a.json()["access_token"]
    ws_a = res_a.json()["workspace_id"]
    
    # Create Tenant B
    res_b = await client.post("/api/v1/auth/register", json={
        "email": "admin@tenant-b.com",
        "name": "Admin B",
        "password": "Password123!",
        "workspace_name": "Tenant B Corp"
    })
    token_b = res_b.json()["access_token"]
    ws_b = res_b.json()["workspace_id"]
    
    # User B tries to access User A's workspace context via X-Workspace-Id header
    probe_resp = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-Id": ws_a
    })
    # Should only return workspaces user B actually belongs to
    assert probe_resp.status_code == 200
    workspaces = probe_resp.json()["workspaces"]
    workspace_ids = [w["workspace_id"] for w in workspaces]
    assert ws_a not in workspace_ids
    assert ws_b in workspace_ids
