import pytest


@pytest.mark.django_db
def test_healthchecks(client):
    response = client.get("/")
    assert response.status_code == 200
