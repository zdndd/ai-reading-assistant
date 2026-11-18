import json

from fastapi.testclient import TestClient

from app.services.rag import RagService


def upload_sample(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/books",
        files={
            "file": (
                "sample.md",
                "# 时间旅行\n大雄和哆啦A梦启动时光机。\n\n他们前往未来对抗黑暗赛亚人。",
                "text/markdown",
            )
        },
        data={"title": "时空之战"},
    )
    assert response.status_code == 201
    return response.json()["book"]


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.strip().split("\n\n"):
        lines = frame.splitlines()
        event = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_health_reports_extractive_mode(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["llm_provider"] == "extractive"
    assert response.json()["generated_answers_enabled"] is False


def test_book_lifecycle_and_question(client: TestClient) -> None:
    book = upload_sample(client)

    listing = client.get("/api/v1/books")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["title"] == "时空之战"

    detail = client.get(f"/api/v1/books/{book['id']}")
    assert detail.status_code == 200
    assert detail.json()["chunk_count"] >= 1

    answer = client.post(
        "/api/v1/questions",
        json={
            "book_id": book["id"],
            "question": "大雄为什么启动时光机？",
            "top_k": 1,
        },
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["mode"] == "fake"
    assert body["model"] == "fake-model"
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["book_id"] == book["id"]
    assert "时光机" in body["evidence"][0]["text"]

    deleted = client.delete(f"/api/v1/books/{book['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/books/{book['id']}").status_code == 404


def test_rejects_unsupported_document(client: TestClient) -> None:
    response = client.post(
        "/api/v1/books",
        files={"file": ("book.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_document"


def test_missing_book_returns_domain_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/questions",
        json={"book_id": "missing", "question": "讲了什么？", "top_k": 3},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "book_not_found"


def test_whitespace_question_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/questions",
        json={"question": "   ", "top_k": 3},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_question"


def test_book_survives_service_recreation(
    client: TestClient,
    settings,
    service: RagService,
) -> None:
    book = upload_sample(client)
    recreated = RagService(
        settings,
        embedder=service.embedder,
        reranker=service.reranker,
        answerer=service.answerer,
    )

    assert recreated.get_book(book["id"]).title == "时空之战"


def test_question_stream_returns_meta_deltas_and_done(client: TestClient) -> None:
    book = upload_sample(client)

    with client.stream(
        "POST",
        "/api/v1/questions/stream",
        json={
            "book_id": book["id"],
            "question": "大雄为什么启动时光机？",
            "top_k": 1,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = parse_sse("".join(response.iter_text()))

    assert events[0][0] == "meta"
    assert events[0][1]["evidence"][0]["book_id"] == book["id"]
    delta_events = [data for event, data in events if event == "delta"]
    assert len(delta_events) > 1
    assert all(data["mode"] == "fake" for data in delta_events)
    assert events[-1] == (
        "done",
        {"mode": "fake", "model": "fake-model"},
    )
