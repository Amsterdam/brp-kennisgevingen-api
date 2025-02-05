from datetime import date, timedelta

from django.db import models
from django.utils import timezone


class BSNMutation(models.Model):
    """
    This table contains all BSN with an active subscription. The mutation date is supplied by
    an external process.
    """

    bsn = models.CharField(max_length=9, unique=True)
    mutation_date = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.pk} ({self.mutation_date})"


class SubscriptionManager(models.Manager):

    def active(self):
        today = timezone.now().date()
        return self.filter(end_date__gte=today)

    def create_with_bsn(self, application_id: str, bsn: str, start_date: date, end_date: date):
        bsn_instance, _ = BSNMutation.objects.get_or_create(bsn=bsn)
        return self.create(
            application_id=application_id,
            bsn=bsn_instance,
            start_date=start_date,
            end_date=end_date,
        )


class SubscriptionTooLongException(Exception):
    pass


class Subscription(models.Model):
    """
    A subscription can be added to receive indications if a person has been updated in the BRP
    """

    application_id = models.CharField(max_length=255)
    bsn = models.ForeignKey(BSNMutation, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    objects = SubscriptionManager()

    class Meta:
        unique_together = [
            "application_id",
            "bsn",
            "start_date",
        ]

    def __str__(self):
        return f"{self.application_id} {self.bsn_id} ({self.start_date}-{self.end_date})"

    def set_end_date(self, end_date):
        today = timezone.now().date()
        if end_date > today + timedelta(days=183):
            raise SubscriptionTooLongException(
                "End date cannot be further in the future than 183 days"
            )
        self.end_date = end_date

        if not self.start_date:
            self.start_date = today

        self.save()


class NewResident(models.Model):
    """
    The new residents table contains all added or updated persons in the BRP for Amsterdam.
    Could be newborns, movers or deceased
    """

    bsn = models.CharField(max_length=9, unique=True)
    mutation_date = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.pk} ({self.mutation_date})"
