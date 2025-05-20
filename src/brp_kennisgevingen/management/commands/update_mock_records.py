from typing import Any

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from brp_kennisgevingen.models import BSNMutation


class Command(BaseCommand):  # noqa: D101
    help = """Update mock records to reflect the changes in Haal Centraal Mock data.
    Uses an environment variable to get the list of BSN records which need to be updated.

    Runned by a daily cronjob to make sure the test records are returned when querying the
    API for changes.
    """  # noqa: A003
    requires_system_checks = []

    def handle(self, *args: list[Any], **options: dict[str, Any]) -> None:  # noqa: D102
        if settings.MOCK_RECORDS_BSN:
            # Make sure a BSNMutation record exists for all the changed mock data
            bsn_mutations = [
                BSNMutation(bsn=bsn, inserted_at=timezone.now())
                for bsn in settings.MOCK_RECORDS_BSN
            ]
            BSNMutation.objects.bulk_create(
                bsn_mutations,
                update_conflicts=True,
                update_fields=["inserted_at"],
                unique_fields=["bsn"],
            )
