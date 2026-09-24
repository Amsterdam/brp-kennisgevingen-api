from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from brp_kennisgevingen.models import BSNMutation
from tests.utils import build_jwt_token

AUDIT_LOGGER_NAME = "brp_kennisgevingen.audit"


def get_audit_records(caplog):
    return [record for record in caplog.records if record.name == AUDIT_LOGGER_NAME]


def assert_latest_access_granted(
    caplog,
    *,
    service,
    scope,
    burgerservicenummers,
    response=None,
):
    audit_records = get_audit_records(caplog)
    assert audit_records

    audit_log_message = audit_records[-1]
    assert audit_log_message.message == (
        f"Access granted for '{service}' to 'test@example.com' "
        "(full request/response in detail)"
    )
    assert audit_log_message.service == service
    assert audit_log_message.upn == "test@example.com"
    assert audit_log_message.granted == [scope]
    assert audit_log_message.appid == "application_id"
    assert audit_log_message.environment == "brp-kennisgevingen-local"
    assert audit_log_message.needed == [scope]
    assert audit_log_message.burgerservicenummers == burgerservicenummers
    if response is not None:
        assert audit_log_message.response == response


def assert_latest_access_denied(caplog, *, path, granted_scopes, needed_scopes):
    audit_records = get_audit_records(caplog)
    assert audit_records

    audit_log_message = audit_records[-1]
    missing_scopes = sorted(set(needed_scopes) - set(granted_scopes))

    assert audit_log_message.message == (
        f"Denied overall access to '{path}', missing {','.join(missing_scopes)}"
    )
    assert audit_log_message.path == path
    assert audit_log_message.granted == sorted(granted_scopes)
    assert audit_log_message.needed == sorted(needed_scopes)
    assert audit_log_message.missing == missing_scopes
    assert audit_log_message.appid == "application_id"


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

    def test_insufficient_scopes(self, api_client, caplog):
        """Prove that insufficient scopes are handled."""
        url = reverse("subscriptions-list")
        granted_scopes = ["benk-brp-invalid"]
        token = build_jwt_token(granted_scopes)
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 403
        assert response.data == {
            "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.3",
            "title": "You do not have permission to perform this action.",
            "status": 403,
            "detail": "Required scopes not given in token.",
            "code": "permissionDenied",
            "instance": "/kennisgevingen/v1/volgindicaties",
        }
        assert_latest_access_denied(
            caplog,
            path="/kennisgevingen/v1/volgindicaties",
            granted_scopes=granted_scopes,
            needed_scopes=["benk-brp-volgindicaties-api"],
        )


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
    def test_subscriptions_for_application_id(self, api_client, subscriptions, caplog):
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
        assert len(response.data) == 3
        for record in response.data:
            assert record["burgerservicenummer"] in ["999990019", "999990093", "999990267"]

        assert_latest_access_granted(
            caplog,
            service="volgindicaties-list",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019", "999990093", "999990267"],
            response=response.data,
        )

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
    def test_subscriptions_detail_exists(self, api_client, subscriptions, caplog):
        url = reverse("subscriptions-detail", kwargs={"bsn": "999990019"})

        token = build_jwt_token(
            [
                "benk-brp-volgindicaties-api",
            ]
        )
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.data["burgerservicenummer"] == "999990019"

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_subscriptions_detail_inactive(self, api_client, subscriptions, caplog):
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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_subscriptions_detail_invalid_bsn(self, api_client, subscriptions, caplog):
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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

        # Expect subscription to exist
        caplog.clear()
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert response.data == {
            "begindatum": str(today),
            "burgerservicenummer": "999990019",
            "einddatum": str(today + timedelta(days=30)),
        }

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

        # Subscription should not exist
        caplog.clear()
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

        # End date should be set to the new date
        caplog.clear()
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.data["einddatum"] == str(new_date)

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990019"],
            response=response.data,
        )

        # The subscription should not be available anymore
        caplog.clear()
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 404

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

        # Set the end date to a future date to create a new subscription
        new_date = timezone.now().date() + timedelta(days=30)
        data = {"einddatum": new_date}

        caplog.clear()
        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990147"],
            response=response.data,
        )

        # The subscription should be available again
        caplog.clear()
        response = api_client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert response.data["einddatum"] == str(new_date)

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990147"],
            response=response.data,
        )

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

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=[],
            response=response.data,
        )

        # Set the end date to a future date to create a new subscription
        new_date = timezone.now().date() + timedelta(days=30)
        data = {"einddatum": new_date}

        caplog.clear()
        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 201

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990147"],
            response=response.data,
        )

        # Remove the subscription by setting a date in the past
        past_date = timezone.now().date() - timedelta(days=30)
        data = {"einddatum": past_date}

        caplog.clear()
        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990147"],
            response=response.data,
        )

        # Set the end date to a future date to re-activate the subscription
        data = {"einddatum": new_date}

        caplog.clear()
        response = api_client.put(url, data, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200

        assert_latest_access_granted(
            caplog,
            service="volgindicaties",
            scope="benk-brp-volgindicaties-api",
            burgerservicenummers=["999990147"],
            response=response.data,
        )


class TestUpdateViews:

    @pytest.mark.parametrize(
        "url,scope",
        [
            ("/kennisgevingen/v1/wijzigingen", "benk-brp-wijzigingen-api"),
            ("/kennisgevingen/v1/nieuwe-ingezetenen", "benk-brp-nieuwe-ingezetenen-api"),
        ],
    )
    @pytest.mark.django_db
    def test_hal_json_response(self, api_client, url, scope, subscriptions, new_residents):
        start_date = timezone.now().date() - timedelta(days=15)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                scope,
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/hal+json"

        assert "_links" in response.data
        assert all(field in response.data["_links"] for field in ["self", "ingeschrevenPersoon"])

    @pytest.mark.django_db
    def test_missing_query_parameter(self, api_client, caplog):
        url = reverse("updates-list")
        token = build_jwt_token(
            [
                "benk-brp-wijzigingen-api",
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

        assert_latest_access_granted(
            caplog,
            service="wijzigingen",
            scope="benk-brp-wijzigingen-api",
            burgerservicenummers=[],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_no_subscriptions_returns_empty_array(self, api_client):
        url = reverse("updates-list")
        today = timezone.now().date()
        query_params = {"vanaf": today}
        token = build_jwt_token(
            [
                "benk-brp-wijzigingen-api",
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
                "benk-brp-wijzigingen-api",
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
    def test_inserted_at_within_search_window(self, api_client, subscriptions, caplog):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Set the mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.create(bsn=subscriptions[0].bsn)
        timezone_aware_start_date = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
        bsn_mutation.inserted_at = timezone_aware_start_date + timedelta(days=3)
        bsn_mutation.save()

        caplog.clear()
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

        assert_latest_access_granted(
            caplog,
            service="wijzigingen",
            scope="benk-brp-wijzigingen-api",
            burgerservicenummers=[subscriptions[0].bsn],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_inserted_at_outside_search_window(self, api_client, subscriptions):
        url = reverse("updates-list")
        start_date = timezone.now().date() - timedelta(days=10)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Create a mutation with a date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.create(bsn=subscriptions[0].bsn)
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
                "benk-brp-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        # Create a mutation date of an active subscription and expect bsn to be returned
        bsn_mutation = BSNMutation.objects.create(bsn=subscriptions[0].bsn)
        timezone_aware_start_date = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
        bsn_mutation.inserted_at = timezone_aware_start_date + timedelta(days=15)
        bsn_mutation.save()

        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")
        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_new_resident_in_search_window(self, api_client, new_residents, caplog):
        url = reverse("new-residents-list")
        start_date = timezone.now().date() - timedelta(days=15)
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-nieuwe-ingezetenen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

        assert_latest_access_granted(
            caplog,
            service="nieuwe-ingezetenen",
            scope="benk-brp-nieuwe-ingezetenen-api",
            burgerservicenummers=response.data["burgerservicenummers"],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_new_resident_outside_search_window(self, api_client, new_residents):
        url = reverse("new-residents-list")
        start_date = timezone.now().date()
        query_params = {"vanaf": start_date}
        token = build_jwt_token(
            [
                "benk-brp-nieuwe-ingezetenen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

    @pytest.mark.django_db
    def test_new_resident_with_max_age(self, api_client, new_residents, caplog):
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
                "benk-brp-nieuwe-ingezetenen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 1

        assert_latest_access_granted(
            caplog,
            service="nieuwe-ingezetenen",
            scope="benk-brp-nieuwe-ingezetenen-api",
            burgerservicenummers=response.data["burgerservicenummers"],
            response=response.data,
        )

        query_params["maxLeeftijd"] = 9
        caplog.clear()
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["burgerservicenummers"]) == 0

        assert_latest_access_granted(
            caplog,
            service="nieuwe-ingezetenen",
            scope="benk-brp-nieuwe-ingezetenen-api",
            burgerservicenummers=[],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_bsn_changes_incorrect_scope(self, api_client, subscriptions, bsn_changes, caplog):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=30)
        query_params = {
            "vanaf": start_date,
        }
        granted_scopes = ["benk-brp-volgindicaties-api"]
        token = build_jwt_token(granted_scopes)
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 403

        assert_latest_access_denied(
            caplog,
            path="/kennisgevingen/v1/bsn-wijzigingen",
            granted_scopes=granted_scopes,
            needed_scopes=["benk-brp-bsn-wijzigingen-api"],
        )

    @pytest.mark.django_db
    def test_bsn_changes_list_view_in_search_window(
        self, api_client, subscriptions, bsn_changes, caplog
    ):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=30)
        query_params = {
            "vanaf": start_date,
        }
        token = build_jwt_token(
            [
                "benk-brp-bsn-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["bsnWijzigingen"]) == 3
        assert not {
            inst["burgerservicenummerOud"] for inst in response.data["bsnWijzigingen"]
        }.intersection({"999990155"})

        assert_latest_access_granted(
            caplog,
            service="bsn-wijzigingen",
            scope="benk-brp-bsn-wijzigingen-api",
            burgerservicenummers=[
                "999990019",
                "999990020",
                "999990093",
                "999990094",
                "999990267",
            ],
            response=response.data,
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
                "benk-brp-bsn-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["bsnWijzigingen"]) == 2
        assert not {
            inst["burgerservicenummerOud"] for inst in response.data["bsnWijzigingen"]
        }.intersection({"999990155", "999990093"})

    @pytest.mark.django_db
    def test_bsn_changes_list_view_empty_new_bsn(
        self, api_client, subscriptions, bsn_changes, caplog
    ):
        url = reverse("bsn-changes-list")
        start_date = timezone.now().date() - timedelta(days=5)
        query_params = {
            "vanaf": start_date,
        }
        token = build_jwt_token(
            [
                "benk-brp-bsn-wijzigingen-api",
            ]
        )
        response = api_client.get(url, data=query_params, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 200
        assert len(response.data["bsnWijzigingen"]) == 1
        assert response.data["bsnWijzigingen"][0]["burgerservicenummerOud"] == "999990267"
        assert response.data["bsnWijzigingen"][0]["burgerservicenummerNieuw"] == ""

        assert_latest_access_granted(
            caplog,
            service="bsn-wijzigingen",
            scope="benk-brp-bsn-wijzigingen-api",
            burgerservicenummers=["999990267"],
            response=response.data,
        )

    @pytest.mark.django_db
    def test_bsn_changes_list_missing_query_parameter(self, api_client, caplog):
        url = reverse("bsn-changes-list")
        token = build_jwt_token(
            [
                "benk-brp-bsn-wijzigingen-api",
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

        assert_latest_access_granted(
            caplog,
            service="bsn-wijzigingen",
            scope="benk-brp-bsn-wijzigingen-api",
            burgerservicenummers=[],
            response=response.data,
        )
