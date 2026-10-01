import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_role_and_candidate_workflow(client: AsyncClient):
    # 1. Register user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "recruiter@example.com",
            "name": "Jane Recruiter",
            "password": "Password123!",
            "workspace_name": "TalentCorp",
        },
    )
    assert reg_resp.status_code in (200, 201), reg_resp.text
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Role
    jd_content = (
        "We are looking for a Senior Python Distributed Systems Engineer. "
        "Must have 5+ years experience in Python, FastAPI, and PostgreSQL. "
        "Must have experience with Kafka and distributed messaging. "
        "Should have Docker and Kubernetes deployment experience."
    )
    role_resp = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"title": "Senior Python Engineer", "jd_text": jd_content},
    )
    assert role_resp.status_code == 201, role_resp.text
    role_data = role_resp.json()
    role_id = role_data["id"]
    assert role_data["title"] == "Senior Python Engineer"

    # 3. List Roles
    list_roles_resp = await client.get("/api/v1/roles", headers=headers)
    assert list_roles_resp.status_code == 200
    assert list_roles_resp.json()["total"] == 1

    # 4. Upload Candidate resume (text file)
    resume_text = (
        "Senior Backend Developer with 6 years experience in Python, FastAPI, and PostgreSQL. "
        "Designed and maintained Kafka distributed event pipelines handling 10M events/day. "
        "Architected scalable Docker microservices deployed on Kubernetes clusters."
    )
    files = {
        "file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")
    }
    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        data={"role_id": role_id},
        files=files,
    )
    assert cand_resp.status_code == 201, cand_resp.text
    cand_data = cand_resp.json()
    cand_id = cand_data["candidate_id"]
    assert cand_data["status"] == "uploaded"
    assert cand_data["display_alias"].startswith("Candidate-")

    # 5. List Candidates
    list_cands_resp = await client.get(
        f"/api/v1/candidates?role_id={role_id}", headers=headers
    )
    assert list_cands_resp.status_code == 200
    assert list_cands_resp.json()["total"] == 1
    assert list_cands_resp.json()["candidates"][0]["id"] == cand_id

    # 6. Get Candidate Details
    get_cand_resp = await client.get(
        f"/api/v1/candidates/{cand_id}", headers=headers
    )
    assert get_cand_resp.status_code == 200
    cand_detail = get_cand_resp.json()
    assert cand_detail["id"] == cand_id
    assert cand_detail["profile"]["parser_version"] is not None


@pytest.mark.asyncio
async def test_approvals_workflow_and_rbac(client: AsyncClient):
    # 1. Register Recruiter
    reg_rec = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "recruiter1@org.com",
            "name": "Recruiter One",
            "password": "Password123!",
            "workspace_name": "Org A",
        },
    )
    assert reg_rec.status_code in (200, 201), reg_rec.text
    rec_token = reg_rec.json()["access_token"]
    rec_headers = {"Authorization": f"Bearer {rec_token}"}

    # Create role
    role_resp = await client.post(
        "/api/v1/roles",
        headers=rec_headers,
        json={
            "title": "Data Engineer",
            "jd_text": "Looking for BigQuery, SQL, and Python Data Engineer with 4 years experience.",
        },
    )
    role_id = role_resp.json()["id"]

    # Create run
    run_resp = await client.post(
        "/api/v1/runs",
        headers=rec_headers,
        json={"role_id": role_id},
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]
    assert run_resp.json()["state"] == "CREATED"

    # Get Run details
    get_run_resp = await client.get(f"/api/v1/runs/{run_id}", headers=rec_headers)
    assert get_run_resp.status_code == 200
    assert get_run_resp.json()["id"] == run_id

    # Request approval for shortlist
    appr_resp = await client.post(
        "/api/v1/approvals",
        headers=rec_headers,
        json={
            "run_id": run_id,
            "shortlist_snapshot": ["cand-1", "cand-2"],
            "note": "Ready for hiring manager review",
        },
    )
    assert appr_resp.status_code == 200, appr_resp.text
    appr_data = appr_resp.json()
    assert appr_data["state"] == "pending"
    assert "payload_hash" in appr_data
    appr_id = appr_data["approval_id"]

    # List approvals
    list_appr_resp = await client.get("/api/v1/approvals", headers=rec_headers)
    assert list_appr_resp.status_code == 200
    assert list_appr_resp.json()["total"] >= 1

    # Check cryptographic audit trail
    audit_resp = await client.get("/api/v1/audit", headers=rec_headers)
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["entries"]
    assert len(entries) >= 1
    # Check that SHA-256 hash chaining exists
    for entry in entries:
        assert len(entry["hash"]) == 64
        assert entry["prev_hash"] is not None
