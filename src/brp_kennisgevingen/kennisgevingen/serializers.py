from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from .utils import to_snake_case_data


class SubscriptionSerializer(serializers.Serializer):
    burgerservicenummer = serializers.CharField(source="bsn")
    begindatum = serializers.DateField(source="start_date")
    einddatum = serializers.DateField(source="end_date")


class UpdateSubscriptionSerializer(serializers.Serializer):
    einddatum = serializers.DateField(required=False, allow_null=True)


class HalLinkSerializer(serializers.Serializer):
    description = serializers.CharField(required=False)
    href = serializers.CharField()
    templated = serializers.BooleanField(required=False)
    title = serializers.CharField(required=False)


class UpdatesLinksSerializer(serializers.Serializer):
    self = HalLinkSerializer()
    ingeschrevenPersoon = HalLinkSerializer()


class UpdatesSerializer(serializers.Serializer):
    burgerservicenummers = serializers.ListField(child=serializers.CharField())
    _links = UpdatesLinksSerializer()


class BSNChangesSerializer(serializers.Serializer):
    oud_bsn = serializers.CharField(source="old_bsn")
    nieuw_bsn = serializers.CharField(source="new_bsn")
    wijzigingsdatum = serializers.DateTimeField(
        required=False, allow_null=True, source="inserted_at"
    )
    ingangsdatum = serializers.DateTimeField(required=False, allow_null=True, source="valid_from")


class UpdatesInputSerializer(serializers.Serializer):
    vanaf = serializers.DateField()

    def validate_vanaf(self, value):
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError("Vanaf moet in het verleden liggen.")
        # Return a timezone aware datetime
        return datetime.combine(value, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )


class NewResidentsInputSerializer(UpdatesInputSerializer):
    max_leeftijd = serializers.IntegerField(required=False)

    def validate_max_leeftijd(self, value):
        if value < 0:
            raise serializers.ValidationError("Max leeftijd moet een positief getal zijn.")
        return value

    def to_internal_value(self, data):
        return super().to_internal_value(to_snake_case_data(data))
