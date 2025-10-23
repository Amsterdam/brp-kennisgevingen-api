from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta
from django.core.handlers.wsgi import WSGIRequest
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from brp_kennisgevingen.models import BSNUpdate, NewResident, Subscription
from tests.utils import api_request_with_scopes, to_drf_request

HERE = Path(__file__).parent


@pytest.fixture()
def api_rf() -> APIRequestFactory:
    """Request factory for APIView classes"""
    return APIRequestFactory()


@pytest.fixture()
def api_request() -> WSGIRequest:
    """Return a very basic Request object. This can be used for the APIClient.
    The DRF views use a different request object internally, see `drf_request` for that.
    """
    return api_request_with_scopes([])


@pytest.fixture()
def drf_request(api_request) -> Request:
    """The wrapped WSGI Request as a Django-Rest-Framework request.
    This is the 'request' object that APIView.dispatch() creates.
    """
    return to_drf_request(api_request)


@pytest.fixture()
def api_client() -> APIClient:
    """Return a client that has unhindered access to the API views"""
    api_client = APIClient()
    api_client.default_format = "json"  # instead of multipart
    return api_client


@pytest.fixture()
def subscriptions() -> list[Subscription]:
    """
    Creates four subscriptions:
    - Two active subscription for the user making the requests
    - An inactive subscription for the user making the requests
    - An active subscription for another user
    """
    today = timezone.now().date()

    subscriptions = [
        {
            "application_id": "application_id",
            "bsn": "999990019",
            "start_date": today,
            "end_date": today + timedelta(days=30),
        },
        {
            "application_id": "application_id",
            "bsn": "999990093",
            "start_date": today,
            "end_date": today + timedelta(days=30),
        },
        {
            "application_id": "application_id",
            "bsn": "999990147",
            "start_date": today - timedelta(days=30),
            "end_date": today - timedelta(days=5),
        },
        {
            "application_id": "other_application_id",
            "bsn": "999990147",
            "start_date": today,
            "end_date": today + timedelta(days=30),
        },
    ]

    instances = []

    for subscription in subscriptions:
        instances.append(Subscription.objects.create_with_bsn(**subscription))

    return instances


@pytest.fixture()
def subscription_today() -> Subscription:
    """
    Create an inactive subscription because it expires 'today'
    """
    today = timezone.now().date()
    subscription = {
        "application_id": "application_id",
        "bsn": "999990093",
        "start_date": today - timedelta(days=30),
        "end_date": today,
    }
    return Subscription.objects.create_with_bsn(**subscription)


@pytest.fixture()
def subscription_past() -> Subscription:
    """
    Create an inactive subscription because it expired 10 days ago
    """
    today = timezone.now().date()
    subscription = {
        "application_id": "application_id",
        "bsn": "999990093",
        "start_date": today - timedelta(days=30),
        "end_date": today - timedelta(days=10),
    }
    return Subscription.objects.create_with_bsn(**subscription)


@pytest.fixture()
def new_residents() -> list[NewResident]:
    """
    Creates four new residents:
    - Two with an inserted_at set, one of them has a birthdate set
    - One without an inserted_at set
    - One with an inserted_at in the future
    """
    today = timezone.now()

    new_residents = [
        {
            "bsn": "999990019",
            "birthdate": None,
            "inserted_at": today - timedelta(days=30),
        },
        {
            "bsn": "999990093",
            "birthdate": today - relativedelta(years=10),
            "inserted_at": today - timedelta(days=10),
        },
        {
            "bsn": "999990147",
            "birthdate": None,
            "inserted_at": None,
        },
        {
            "bsn": "999990214",
            "birthdate": None,
            "inserted_at": today + timedelta(days=10),
        },
    ]

    instances = []

    for resident in new_residents:
        instances.append(NewResident.objects.create(**resident))

    return instances


@pytest.fixture()
def bsn_updates() -> list[BSNUpdate]:
    """ """
    today = timezone.now()

    bsn_updates = [
        {
            "application_id": "application_id",
            "old_bsn": "999990019",
            "new_bsn": "999990020",
            "inserted_at": today - timedelta(days=10),
        },
        {
            "application_id": "application_id",
            "old_bsn": "999990093",
            "new_bsn": "999990094",
            "inserted_at": today - timedelta(days=10),
        },
        {
            "application_id": "application_id",
            "old_bsn": "999990147",
            "new_bsn": "999990148",
            "inserted_at": today - timedelta(days=15),
        },
        {
            "application_id": "other_application_id",
            "old_bsn": "999990155",
            "new_bsn": "999990156",
            "inserted_at": today - timedelta(days=10),
        },
    ]

    instances = []

    for bsn_update in bsn_updates:
        instances.append(BSNUpdate.objects.create(**bsn_update))

    return instances
