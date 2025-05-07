import pytest


@pytest.mark.django_db
def test_healthchecks(client):
    response = client.get("/kennisgevingen/v1")
    assert response.status_code == 200
