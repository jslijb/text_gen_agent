import pytest
from tests.conftest import client, db_session


class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestProjectAPI:
    def test_create_project(self, client):
        response = client.post("/api/v1/projects", json={
            "name": "测试小说",
            "synopsis": "一个都市情感故事，讲述两个年轻人在大城市相遇相知的经历",
            "gender": "男性向",
            "genre": "都市情感",
            "target_word_count": 20000,
            "initial_chapters": 10,
            "daily_chapters": 2,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "测试小说"
        assert data["genre"] == "都市情感"
        assert data["status"] == "draft"

    def test_list_projects(self, client):
        client.post("/api/v1/projects", json={
            "name": "测试小说1",
            "synopsis": "测试梗概内容超过十个字的故事描述",
            "gender": "男性向",
            "genre": "都市情感",
            "target_word_count": 20000,
        })
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_get_project(self, client):
        create_resp = client.post("/api/v1/projects", json={
            "name": "测试小说2",
            "synopsis": "另一个测试梗概内容超过十个字的故事描述",
            "gender": "无性向",
            "genre": "恐怖推理",
            "target_word_count": 15000,
        })
        project_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "测试小说2"

    def test_update_project(self, client):
        create_resp = client.post("/api/v1/projects", json={
            "name": "测试小说3",
            "synopsis": "更新测试梗概内容超过十个字的故事描述",
            "gender": "无性向",
            "genre": "恐怖推理",
            "target_word_count": 25000,
        })
        project_id = create_resp.json()["id"]
        response = client.put(f"/api/v1/projects/{project_id}", json={
            "name": "更新后的名字",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "更新后的名字"

    def test_delete_project(self, client):
        create_resp = client.post("/api/v1/projects", json={
            "name": "待删除小说",
            "synopsis": "删除测试梗概内容超过十个字的故事描述",
            "gender": "无性向",
            "genre": "见闻杂谈",
            "target_word_count": 12000,
        })
        project_id = create_resp.json()["id"]
        response = client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

    def test_invalid_genre(self, client):
        response = client.post("/api/v1/projects", json={
            "name": "测试",
            "synopsis": "测试梗概内容超过十个字的故事描述",
            "gender": "无性向",
            "genre": "无效题材",
            "target_word_count": 20000,
        })
        assert response.status_code == 400

    def test_project_not_found(self, client):
        response = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404