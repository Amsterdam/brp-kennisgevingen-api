from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers


class SubscriptionSerializer(serializers.Serializer):
    burgerservicenummer = serializers.CharField(source="bsn.bsn")
    begindatum = serializers.DateField(source="start_date")
    einddatum = serializers.DateField(source="end_date")


class UpdateSubscriptionSerializer(serializers.Serializer):
    einddatum = serializers.DateField()

    def validate_einddatum(self, value):
        today = timezone.now().date()
        if value < today:
            raise serializers.ValidationError("Einddatum moet in de toekomst liggen.")
        if value > today + timedelta(days=183):
            raise serializers.ValidationError(
                "Einddatum mag maximaal 6 maanden in de toekomst liggen."
            )
        return value


class UpdatesSerializer(serializers.Serializer):
    burgerservicenummers = serializers.ListField(child=serializers.CharField())
    _links = serializers.SerializerMethodField()

    def get__links(self, obj):
        return {
            "self": {"href": obj["self"]},
            "ingeschrevenPersoon": {
                "href": "/ingeschrevenpersonen/{burgerservicenummer}",
                "templated": True,
            },
        }


class DateInputSerializer(serializers.Serializer):
    vanaf = serializers.DateField()

    def validate_vanaf(self, value):
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError("Vanaf moet in het verleden liggen.")
        return value
