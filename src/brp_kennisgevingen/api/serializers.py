from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
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
    _links = serializers.SerializerMethodField()

    @extend_schema_field(UpdatesLinksSerializer)
    def get__links(self, obj):
        return UpdatesLinksSerializer(
            {
                "self": HalLinkSerializer({"href": obj["full_path"]}).data,
                "ingeschrevenPersoon": HalLinkSerializer(
                    {
                        "href": "/ingeschrevenpersonen/{burgerservicenummer}",
                        "templated": True,
                    }
                ).data,
            }
        ).data


class DateInputSerializer(serializers.Serializer):
    vanaf = serializers.DateField()

    def validate_vanaf(self, value):
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError("Vanaf moet in het verleden liggen.")
        # Return a timezone aware datetime
        return datetime.combine(value, datetime.min.time()).replace(
            tzinfo=timezone.get_current_timezone()
        )
