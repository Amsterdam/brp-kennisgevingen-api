# Generated by Django 5.1.5 on 2025-02-06 11:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BSNMutation",
            fields=[
                (
                    "bsn",
                    models.CharField(max_length=9, primary_key=True, serialize=False, unique=True),
                ),
                ("mutation_date", models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("application_id", models.CharField(max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "bsn",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="brp_kennisgevingen.bsnmutation",
                    ),
                ),
            ],
            options={
                "unique_together": {("application_id", "bsn", "start_date")},
            },
        ),
        migrations.CreateModel(
            name="NewResident",
            fields=[
                (
                    "bsn",
                    models.CharField(max_length=9, primary_key=True, serialize=False, unique=True),
                ),
                ("mutation_date", models.DateTimeField(null=True)),
            ],
        ),
    ]
