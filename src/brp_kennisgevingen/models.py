from django.db import models
from django.db.models import Q
from django.utils import timezone


class BSNMutation(models.Model):
    """
    This table contains all BSN with an active subscription. The mutation date is supplied by
    an external process.
    """

    bsn = models.CharField(max_length=9, unique=True, primary_key=True)
    inserted_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.pk} ({self.inserted_at})"


class BSNChange(models.Model):
    """
    The BSNChanges table contains all changed BSNs in the BRP for Amsterdam.
    Includes the old BSN and the new BSN that the old one changed to.
    """

    application_id = models.CharField(max_length=255)
    old_bsn = models.CharField(max_length=9, unique=True)
    new_bsn = models.CharField(max_length=9, unique=True, null=True)
    inserted_at = models.DateTimeField()
    valid_from = models.DateTimeField()

    def __str__(self):
        return f"old BSN: {self.old_bsn}, new BSN: {self.new_bsn}"


class SubscriptionManager(models.Manager):

    def active(self):
        today = timezone.now().date()
        return self.filter(Q(end_date__gt=today) | Q(end_date__isnull=True))

    def updatable(self):
        # Records which are updatable are either active or have a start date of today
        today = timezone.now().date()
        return self.filter(Q(end_date__gt=today) | Q(end_date__isnull=True) | Q(start_date=today))


class SubscriptionTooLongException(Exception):
    pass


class Subscription(models.Model):
    """
    A subscription can be added to receive indications if a person has been updated in the BRP
    """

    application_id = models.CharField(max_length=255)
    bsn = models.CharField(max_length=9)
    start_date = models.DateField()
    end_date = models.DateField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionManager()

    class Meta:
        unique_together = [
            "application_id",
            "bsn",
            "start_date",
        ]

    def __str__(self):
        date_range = (
            f"({self.start_date}-{self.end_date})" if self.end_date else f"({self.start_date}-)"
        )
        return f"{self.pk} {self.application_id} {date_range}"

    def set_end_date(self, end_date):
        today = timezone.now().date()
        self.end_date = end_date

        if not self.start_date:
            self.start_date = today

        self.save()


class NewResident(models.Model):
    """
    The new residents table contains all added or updated persons in the BRP for Amsterdam.
    Could be newborns, movers or deceased
    """

    bsn = models.CharField(max_length=9, unique=True, primary_key=True)
    birthdate = models.DateField(null=True)
    inserted_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.pk} ({self.inserted_at})"
