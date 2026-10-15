"""Smoke suite for the RV Catalog API.

Covers the endpoints the dashboard and downstream dealer sites depend on:
health, manufacturers, models, floorplans, lookup, and auth config.
Run with:  python -m pytest tests/ -q
"""

API = "/api"


class TestHealth:
    def test_overview(self, client):
        r = client.get(f"{API}/health")
        assert r.status_code == 200
        body = r.json()
        assert body["total_manufacturers"] == 2
        assert body["active_manufacturers"] == 1
        assert body["defunct_manufacturers"] == 1
        assert body["total_models"] == 2
        assert body["total_floorplans"] == 1
        assert body["total_images"] == 2
        assert body["scrape_status"] == {"complete": 1, "defunct": 1}

    def test_manufacturer_health(self, client):
        r = client.get(f"{API}/health/manufacturer/jayco")
        assert r.status_code == 200
        body = r.json()
        assert body["manufacturer"]["slug"] == "jayco"
        assert body["totals"] == {"models": 2, "floorplans": 1, "images": 2}
        assert len(body["scrape_history"]) == 1

    def test_manufacturer_health_404(self, client):
        r = client.get(f"{API}/health/manufacturer/does-not-exist")
        assert r.status_code == 404


class TestManufacturers:
    def test_list_excludes_defunct_by_default(self, client):
        r = client.get(f"{API}/manufacturers")
        assert r.status_code == 200
        slugs = [m["slug"] for m in r.json()]
        assert slugs == ["jayco"]

    def test_list_includes_defunct(self, client):
        r = client.get(f"{API}/manufacturers", params={"include_defunct": "true"})
        assert {m["slug"] for m in r.json()} == {"jayco", "old-brand"}

    def test_detail_with_models(self, client):
        r = client.get(f"{API}/manufacturers/jayco")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Jayco"
        names = {m["model_name"] for m in body["models"]}
        assert names == {"Grey Wolf", "Redhawk"}

    def test_detail_404(self, client):
        assert client.get(f"{API}/manufacturers/does-not-exist").status_code == 404


class TestModels:
    def test_list_filtered(self, client):
        r = client.get(f"{API}/models", params={"make": "jayco", "year": 2024})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["model_name"] == "Grey Wolf"

    def test_detail_includes_floorplans_and_images(self, client):
        r = client.get(f"{API}/models/1")
        assert r.status_code == 200
        body = r.json()
        assert body["model_name"] == "Grey Wolf"
        assert [f["floorplan_code"] for f in body["floorplans"]] == ["37FRZ"]
        types = {i["image_type"] for i in body["images"]}
        assert types == {"floorplan", "exterior"}

    def test_detail_404(self, client):
        assert client.get(f"{API}/models/9999").status_code == 404

    def test_floorplan_list_by_model(self, client):
        r = client.get(f"{API}/floorplans", params={"model_id": 1})
        assert r.status_code == 200
        fps = r.json()
        assert len(fps) == 1
        assert fps[0]["floorplan_code"] == "37FRZ"

    def test_floorplan_detail_with_images(self, client):
        r = client.get(f"{API}/floorplans/1")
        assert r.status_code == 200
        body = r.json()
        assert body["floorplan_code"] == "37FRZ"
        assert len(body["images"]) == 1
        assert body["images"][0]["image_type"] == "floorplan"

    def test_floorplan_detail_404(self, client):
        assert client.get(f"{API}/floorplans/9999").status_code == 404


class TestLookup:
    def test_exact_match(self, client):
        r = client.get(
            f"{API}/lookup",
            params={"make": "jayco", "model": "grey wolf", "year": 2024},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["match"]["model_name"] == "Grey Wolf"
        assert body["match"]["manufacturer_display"] == "Jayco"
        assert [f["floorplan_code"] for f in body["floorplans"]] == ["37FRZ"]

    def test_no_match(self, client):
        r = client.get(f"{API}/lookup", params={"make": "jayco", "model": "nope"})
        assert r.status_code == 200
        assert r.json()["match"] is None


class TestAuth:
    def test_config_public(self, client):
        r = client.get(f"{API}/auth/config")
        assert r.status_code == 200
        assert r.json()["environment"] == "development"

    def test_me_stub_in_dev(self, client):
        r = client.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "dev@savvydealer.com"
