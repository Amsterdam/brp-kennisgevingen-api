from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.utils import build_jwt_token


class TestBaseView:
    """Prove that the generic view offers the login check logic.
    This is tested through the concrete implementations though.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "/volgindicaties",
            "/volgindicaties/999990019",
            "/wijzigingen",
        ],
    )
    def test_no_login(self, api_client, url):
        """Prove that accessing the view fails without a login token."""
        response = api_client.get(url)
        assert response.status_code == 401
        assert response.data == {
            "type": "https://datatracker.ietf.org/doc/html/rfc7235#section-3.1",
            "code": "not_authenticated",
            "title": "Not authenticated.",
            "detail": "The request requires user authentication. The response MUST include a "
            "WWW-Authenticate header field (section 14.47) containing a challenge "
            "applicable to the requested resource.",
            "status": 401,
            "instance": url,
        }

    def test_insufficient_scopes(self, api_client):
        """Prove that insufficient scopes are handled."""
        url = reverse("subscriptions-list")
        token = build_jwt_token(
            [
                "benk-brp-invalid",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 403
        assert response.data == {
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.3",
            "title": "You do not have permission to perform this action.",
            "status": 403,
            "detail": "",
            "code": "permission_denied",
            "instance": "/volgindicaties",
        }


class TestSubscriptionsView:

    @pytest.mark.django_db
    def test_no_subscriptions_returns_empty_array(self, api_client):
        url = reverse("subscriptions-list")

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data == []

    @pytest.mark.django_db
    def test_subscriptions_for_application_id(self, api_client, subscriptions):
        url = reverse("subscriptions-list")

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200

        # We expect two records, since the other subscriptions are either inactive
        # or linked to another application_id
        assert len(response.data) == 2
        for record in response.data:
            assert record["burgerservicenummer"] in ["999990019", "999990093"]

    @pytest.mark.django_db
    def test_subscriptions_ending_today_are_not_returned(self, api_client, subscription_today):
        url = reverse("subscriptions-list")

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200

        # We expect no records, since the end_date is today
        assert len(response.data) == 0

    @pytest.mark.django_db
    def test_subscriptions_ended_are_not_returned(self, api_client, subscription_past):
        url = reverse("subscriptions-list")

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200

        # We expect no records, since the end_date is today
        assert len(response.data) == 0

    @pytest.mark.django_db
    def test_subscriptions_detail_exists(self, api_client, subscriptions):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data["burgerservicenummer"] == "999990019"

    @pytest.mark.django_db
    def test_subscriptions_detail_inactive(self, api_client, subscriptions):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990147"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 404
        assert response.data == {
            "detail": "The server has not found anything matching the Request-URI.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4",
            "title": "Opgevraagde resource bestaat niet.",
            "status": 404,
            "code": "not_found",
            "instance": "/volgindicaties/999990147",
        }

    @pytest.mark.django_db
    def test_subscriptions_detail_invalid_bsn(self, api_client, subscriptions):
        url = reverse("subscriptions-detail", kwargs={"bsn": "invalid"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 400
        assert response.data == {
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "title": "Waarde is geen geldig BSN.",
            "status": 400,
            "code": "parse_error",
            "instance": "/volgindicaties/invalid",
            "invalidParams": [
                {
                    "code": "bsn",
                    "name": "burgerservicenummer",
                    "reason": "Waarde is geen geldig BSN.",
                }
            ],
        }

    @pytest.mark.django_db
    def test_create_new_subscription(self, api_client):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        today = timezone.now().date()

        data = {"einddatum": today + timedelta(days=30)}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        # Expect subscription to exist
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert response.data == {
            "begindatum": str(today),
            "burgerservicenummer": "999990019",
            "einddatum": str(today + timedelta(days=30)),
        }

    @pytest.mark.django_db
    def test_create_new_subscription_end_date_in_past(self, api_client):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )

        today = timezone.now().date()

        data = {"einddatum": today - timedelta(days=30)}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 400
        assert response.data == {
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "title": "Geen correcte waarde opgegeven.",
            "status": 400,
            "code": "parse_error",
            "instance": "/volgindicaties/999990019",
            "invalidParams": [
                {
                    "name": "einddatum",
                    "code": "date",
                    "reason": "Einddatum moet in de toekomst liggen.",
                }
            ],
        }

        # Subscription should not exist
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_create_new_subscription_end_date_too_far(self, api_client):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )

        today = timezone.now().date()

        data = {"einddatum": today + timedelta(days=184)}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 400
        assert response.data == {
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "title": "Geen correcte waarde opgegeven.",
            "status": 400,
            "code": "parse_error",
            "instance": "/volgindicaties/999990019",
            "invalidParams": [
                {
                    "code": "date",
                    "name": "einddatum",
                    "reason": "Einddatum mag maximaal 6 maanden in de toekomst liggen.",
                }
            ],
        }

        # Subscription should not exist
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_change_existing_active_subscription(self, api_client, subscriptions):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )

        new_date = timezone.now().date() + timedelta(days=50)
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        # End date should be set to the new date
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.data["einddatum"] == str(new_date)


class TestUpdateViews:

    @pytest.mark.parametrize(
        "url",
        ["/wijzigingen", "/nieuwe-ingezetenen"],
    )
    @pytest.mark.django_db
    def test_hal_json_response(self, api_client, url, subscriptions, new_residents):
        start_date = timezone.now().date() - timedelta(days=15)
        url += f"?vanaf={start_date}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/hal+json"

        assert "_links" in response.data
        assert all(field in response.data["_links"] for field in ["self", "ingeschrevenPersoon"])

    @pytest.mark.django_db
    def test_missing_query_parameter(self, api_client):
        url = reverse("updates-list")
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 400
        assert response.data == {
            "code": "parse_error",
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "status": 400,
            "title": "Geen correcte waarde opgegeven.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "instance": "/wijzigingen",
            "invalidParams": [
                {
                    "code": "date",
                    "name": "vanaf",
                    "reason": "This field is required.",
                }
            ],
        }

    @pytest.mark.django_db
    def test_no_subscriptions_returns_empty_array(self, api_client):
        url = reverse("updates-list")
        today = timezone.now().date()
        url += f"?vanaf={today}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data == {
            "burgerservicenummers": [],
            "_links": {
                "self": {"href": f"/wijzigingen?vanaf={today}"},
                "ingeschrevenPersoon": {
                    "href": "/ingeschrevenpersonen/{burgerservicenummer}",
                    "templated": True,
                },
            },
        }

    @pytest.mark.django_db
    def test_subscriptions_without_mutation_date_returns_empty_array(
        self, api_client, subscriptions
    ):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        url += f"?vanaf={start_date}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data == {
            "burgerservicenummers": [],
            "_links": {
                "self": {"href": f"/wijzigingen?vanaf={start_date}"},
                "ingeschrevenPersoon": {
                    "href": "/ingeschrevenpersonen/{burgerservicenummer}",
                    "templated": True,
                },
            },
        }

    @pytest.mark.django_db
    def test_mutation_date_within_search_window(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now() - timedelta(days=10)
        url += f"?vanaf={start_date.date()}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = subscriptions[0].bsn
        bsn_mutation.mutation_date = start_date + timedelta(days=3)
        bsn_mutation.save()

        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

    @pytest.mark.django_db
    def test_mutation_date_outside_search_window(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now() - timedelta(days=10)
        url += f"?vanaf={start_date.date()}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = subscriptions[0].bsn
        bsn_mutation.mutation_date = start_date - timedelta(days=3)
        bsn_mutation.save()

        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_mutation_date_in_future(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now() - timedelta(days=10)
        url += f"?vanaf={start_date.date()}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = subscriptions[0].bsn
        bsn_mutation.mutation_date = start_date + timedelta(days=15)
        bsn_mutation.save()

        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_new_resident_in_search_window(self, api_client, new_residents):
        url = reverse("new-residents-list")
        start_date = timezone.now() - timedelta(days=15)
        url += f"?vanaf={start_date.date()}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

    @pytest.mark.django_db
    def test_new_resident_outside_search_window(self, api_client, new_residents):
        url = reverse("new-residents-list")
        start_date = timezone.now().date()
        url += f"?vanaf={start_date}"
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0
