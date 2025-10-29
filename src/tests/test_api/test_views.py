from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from brp_kennisgevingen.models import BSNMutation
from tests.utils import build_jwt_token


class TestBaseView:
    """Prove that the generic view offers the login check logic.
    This is tested through the concrete implementations though.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "/kennisgevingen/v1/volgindicaties",
            "/kennisgevingen/v1/volgindicaties/999990019",
            "/kennisgevingen/v1/wijzigingen",
        ],
    )
    def test_no_login(self, api_client, url):
        """Prove that accessing the view fails without a login token."""
        response = api_client.get(url)
        assert response.status_code == 401
        assert response.data == {
            "type": "https://datatracker.ietf.org/doc/html/rfc7235#section-3.1",
            "code": "notAuthenticated",
            "title": "Authentication credentials were not provided.",
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
            "code": "permissionDenied",
            "instance": "/kennisgevingen/v1/volgindicaties",
        }


class TestSubscriptionsView:

    @pytest.mark.django_db
    def test_no_subscriptions_returns_empty_array(self, api_client):
        url = reverse("subscriptions-list")

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
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
                "benk-brp-volgindicaties-api",
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
                "benk-brp-volgindicaties-api",
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
                "benk-brp-volgindicaties-api",
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
                "benk-brp-volgindicaties-api",
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
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 404
        assert response.data == {
            "detail": "The server has not found anything matching the Request-URI.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4",
            "title": "Opgevraagde resource bestaat niet.",
            "status": 404,
            "code": "notFound",
            "instance": "/kennisgevingen/v1/volgindicaties/999990147",
        }

    @pytest.mark.django_db
    def test_subscriptions_detail_invalid_bsn(self, api_client, subscriptions):
        url = reverse("subscriptions-detail", kwargs={"bsn": "invalid"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
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
            "code": "parseError",
            "instance": "/kennisgevingen/v1/volgindicaties/invalid",
            "invalidParams": [
                {
                    "code": "bsn",
                    "name": "burgerservicenummer",
                    "reason": "Waarde is geen geldig BSN.",
                }
            ],
        }

    @pytest.mark.django_db
    def test_create_new_subscription(self, api_client, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        today = timezone.now().date()

        data = {"einddatum": today + timedelta(days=30)}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201
        assert response.data == {
            "begindatum": str(today),
            "burgerservicenummer": "999990019",
            "einddatum": str(today + timedelta(days=30)),
        }

        # Expect subscription to exist
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert response.data == {
            "begindatum": str(today),
            "burgerservicenummer": "999990019",
            "einddatum": str(today + timedelta(days=30)),
        }

        log_messages = caplog.messages
        for log_message in [
            (
                "Access granted for 'new subscription' to 'test@example.com' on '999990019' "
                "(full request/response in detail)"
            ),
        ]:
            assert log_message in log_messages

    @pytest.mark.django_db
    def test_create_new_subscription_end_date_in_past(self, api_client, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        data = {"einddatum": timezone.now().date() - timedelta(days=30)}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 400
        assert response.data == {
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "title": "Geen correcte waarde opgegeven.",
            "status": 400,
            "code": "parseError",
            "instance": "/kennisgevingen/v1/volgindicaties/999990019",
            "invalidParams": [
                {
                    "name": "einddatum",
                    "code": "date",
                    "reason": "Voor een nieuwe volgindicatie kan de einddatum niet in "
                    "het verleden liggen.",
                }
            ],
        }

        # Subscription should not exist
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_create_new_subscription_empty_end_date(self, api_client, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        data = {}

        today = timezone.now().date()

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        # When no end_date is supplied, the end_date should be 182 days in the future
        assert response.data == {
            "begindatum": str(today),
            "burgerservicenummer": "999990019",
            "einddatum": None,
        }

    @pytest.mark.django_db
    def test_change_existing_active_subscription(self, api_client, subscriptions, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        new_date = timezone.now().date() + timedelta(days=50)
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        # End date should be set to the new date
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.data["einddatum"] == str(new_date)

        log_messages = caplog.messages
        for log_message in [
            (
                "Access granted for 'update subscription' to 'test@example.com' on '999990019' "
                "(full request/response in detail)"
            ),
        ]:
            assert log_message in log_messages

    @pytest.mark.django_db
    def test_remove_existing_active_subscription(self, api_client, subscriptions, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        # Set the end date to today - 1 to stop the subscription
        new_date = timezone.now().date() - timedelta(days=1)
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        # The subscription should not be available anymore
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

        log_messages = caplog.messages
        for log_message in [
            (
                "Access granted for 'update subscription' to 'test@example.com' on '999990019' "
                "(full request/response in detail)"
            ),
        ]:
            assert log_message in log_messages

    @pytest.mark.django_db
    def test_reactivate_expired_subscription(self, api_client, subscriptions, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990147"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        # The subscription should not be available
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

        # Set the end date to a future date to create a new subscription
        new_date = timezone.now().date() + timedelta(days=30)
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        # The subscription should be available again
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert response.data["einddatum"] == str(new_date)

    @pytest.mark.django_db
    def test_send_multiple_updates(self, api_client, subscriptions, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990147"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )

        # The subscription should not be available
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

        # Set the end date to a future date to create a new subscription
        new_date = timezone.now().date() + timedelta(days=30)
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        # Remove the subscription by setting a date in the past
        past_date = timezone.now().date() - timedelta(days=30)
        data = {"einddatum": past_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        # Set the end date to a future date to re-activate the subscription
        data = {"einddatum": new_date}

        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200


# Hier komt dan ook mijn bsn-wijzigingen (naam vind ik niet goed, wijzigingen laat al bsns zien)
class TestUpdateViews:

    @pytest.mark.parametrize(
        "url",
        ["/kennisgevingen/v1/wijzigingen", "/kennisgevingen/v1/nieuwe-ingezetenen"],
    )
    @pytest.mark.django_db
    def test_hal_json_response(self, api_client, url, subscriptions, new_residents):
        start_date = timezone.now().date() - timedelta(days=15)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/hal+json"

        assert "_links" in response.data
        assert all(field in response.data["_links"] for field in ["self", "ingeschrevenPersoon"])

    @pytest.mark.django_db
    def test_missing_query_parameter(self, api_client):
        url = reverse("updates-list")
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 400
        assert response.data == {
            "code": "parseError",
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "status": 400,
            "title": "Geen correcte waarde opgegeven.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "instance": "/kennisgevingen/v1/wijzigingen",
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
        query_params = {"vanaf": today}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data == {
            "burgerservicenummers": [],
            "_links": {
                "self": {"href": f"/kennisgevingen/v1/wijzigingen?vanaf={today}"},
                "ingeschrevenPersoon": {"href": "/bevragingen/v1/personen"},
            },
        }

    @pytest.mark.django_db
    def test_subscriptions_without_inserted_at_returns_empty_array(
        self, api_client, subscriptions
    ):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data == {
            "burgerservicenummers": [],
            "_links": {
                "self": {"href": f"/kennisgevingen/v1/wijzigingen?vanaf={start_date}"},
                "ingeschrevenPersoon": {"href": "/bevragingen/v1/personen"},
            },
        }

    @pytest.mark.django_db
    def test_inserted_at_within_search_window(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.get(bsn=subscriptions[0].bsn)
        timezone_aware_start_date = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
        bsn_mutation.inserted_at = timezone_aware_start_date + timedelta(days=3)
        bsn_mutation.save()

        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

    @pytest.mark.django_db
    def test_inserted_at_outside_search_window(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.get(bsn=subscriptions[0].bsn)
        timezone_aware_start_date = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
        bsn_mutation.inserted_at = timezone_aware_start_date - timedelta(days=3)
        bsn_mutation.save()

        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_inserted_at_in_future(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.get(bsn=subscriptions[0].bsn)
        timezone_aware_start_date = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
        bsn_mutation.inserted_at = timezone_aware_start_date + timedelta(days=15)
        bsn_mutation.save()

        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_new_resident_in_search_window(self, api_client, new_residents):
        url = reverse("new-residents-list")
        start_date = timezone.now().date() - timedelta(days=15)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        print(response.data)
        assert len(response.data["burgerservicenummers"]) == 1

    @pytest.mark.django_db
    def test_new_resident_outside_search_window(self, api_client, new_residents):
        url = reverse("new-residents-list")
        start_date = timezone.now().date()
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_new_resident_with_max_age(self, api_client, new_residents):
        """
        One new resident within the search window has an age of 10. We should
        be able to filter this record bases on the maxLeeftijd parameter
        """
        url = reverse("new-residents-list")
        start_date = timezone.now().date() - timedelta(days=15)
        query_params = {
            "vanaf": start_date,
            "maxLeeftijd": 15,
        }
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

        query_params["maxLeeftijd"] = 9
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_bsn_changes_list_view_in_search_window(self, api_client, subscriptions, bsn_changes):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=30)
        query_params = {
            "vanaf": start_date,
        }
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data) == 4
        assert not {inst["burgerservicenummerOud"] for inst in response.data}.intersection(
            {"999990155"}
        )

    @pytest.mark.django_db
    def test_bsn_changes_list_view_outside_search_window(
        self, api_client, subscriptions, bsn_changes
    ):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=14)
        query_params = {
            "vanaf": start_date,
        }
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        print(response.data)
        assert len(response.data) == 3
        assert not {inst["burgerservicenummerOud"] for inst in response.data}.intersection(
            {"999990155", "999990147"}
        )

    @pytest.mark.django_db
    def test_bsn_changes_list_view_empty_new_bsn(self, api_client, subscriptions, bsn_changes):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=5)
        query_params = {
            "vanaf": start_date,
        }
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        print(response.data)
        assert len(response.data) == 1
        assert response.data[0]["burgerservicenummerOud"] == "999990267"
        assert response.data[0]["burgerservicenummerNieuw"] == ""

    @pytest.mark.django_db
    def test_bsn_changes_list_missing_query_parameter(self, api_client):
        url = reverse("bsn-changes-list")
        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 400
        assert response.data == {
            "code": "parseError",
            "detail": "The request could not be understood by the server due to malformed "
            "syntax. The client SHOULD NOT repeat the request without modification.",
            "status": 400,
            "title": "Geen correcte waarde opgegeven.",
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
            "instance": "/kennisgevingen/v1/bsn-wijzigingen",
            "invalidParams": [
                {
                    "code": "date",
                    "name": "vanaf",
                    "reason": "This field is required.",
                }
            ],
        }
