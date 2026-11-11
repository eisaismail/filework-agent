from fastapi.testclient import TestClient

from filework.server import create_app

TEXT = "Invoice ID: INV-1\nSupplier: Alder\nDate: 2026-03-12\nCurrency: EUR\nTotal: 10.25\n"
HEADERS = {"X-Filework": "1"}


def app_at(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "a.txt").write_text(TEXT)
    return create_app(docs, tmp_path / "state")


def test_preview_approve_download_and_restart(tmp_path):
    with TestClient(app_at(tmp_path)) as client:
        task = client.post("/api/tasks", json={"request": "March 2026 invoices"}, headers=HEADERS).json()
        assert task["status"] == "awaiting_approval"
        path = "/api/tasks/" + task["id"]
        assert client.get(path + "/report").status_code == 404
        approved = client.post(path + "/approve", json={}, headers=HEADERS)
        assert approved.status_code == 200
        assert "10.25" in client.get(path + "/report").text
        assert client.post(path + "/approve", json={}, headers=HEADERS).status_code == 409
    with TestClient(app_at(tmp_path)) as client:
        assert client.get(path).json()["status"] == "completed"


def test_cross_origin_and_missing_header_rejected(tmp_path):
    with TestClient(app_at(tmp_path)) as client:
        assert client.post("/api/tasks", json={"request": "all invoices"}).status_code == 403
        response = client.post("/api/tasks", json={"request": "all invoices"}, headers={**HEADERS, "Origin": "https://elsewhere.invalid"})
        assert response.status_code == 403


def test_source_change_rejects_save(tmp_path):
    with TestClient(app_at(tmp_path)) as client:
        task = client.post("/api/tasks", json={"request": "all invoices"}, headers=HEADERS).json()
        (tmp_path / "docs/a.txt").write_text(TEXT.replace("10.25", "25.00"))
        assert client.post(f"/api/tasks/{task['id']}/approve", json={}, headers=HEADERS).status_code == 409


def test_static_interface_and_host_guard(tmp_path):
    with TestClient(app_at(tmp_path)) as client:
        response = client.get("/")
        assert response.status_code == 200 and "Filework" in response.text
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert client.get("/api/workspace", headers={"host": "evil.invalid"}).status_code == 400
