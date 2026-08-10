# Align migration state with AirpayBaseModel without touching DB columns.
#
# Models historically used create_date/update_date (and CharField PKs).
# AirpayBaseModel exposes created_at/updated_at via db_column=create_date/
# update_date and UUIDField PKs. Without a state-only migration, deploy
# `makemigrations` tries to AddField(created_at, auto_now_add=True) and
# prompts interactively → EOFError.

import uuid

from django.db import migrations, models

_MODELS = (
    "airplan",
    "airplanfeatures",
    "airseller",
    "paymentgateway",
    "subscriptions",
    "razorpayrouteonboardingdetails",
    "razorpayonboardingaddress",
    "airpaytransferlogs",
)


def _state_ops_for(model_name: str) -> list:
    return [
        migrations.RenameField(
            model_name=model_name,
            old_name="create_date",
            new_name="created_at",
        ),
        migrations.RenameField(
            model_name=model_name,
            old_name="update_date",
            new_name="updated_at",
        ),
        migrations.AlterField(
            model_name=model_name,
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                db_column="create_date",
                help_text="Timestamp when the record was created",
                verbose_name="Created At",
            ),
        ),
        migrations.AlterField(
            model_name=model_name,
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                db_column="update_date",
                help_text="Timestamp when the record was last updated",
                verbose_name="Updated At",
            ),
        ),
        migrations.AlterField(
            model_name=model_name,
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterModelOptions(
            name=model_name,
            options={"ordering": ["-created_at"]},
        ),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("airpay", "0004_airplan_gateway_plan_id"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                op for model_name in _MODELS for op in _state_ops_for(model_name)
            ],
            database_operations=[],
        ),
    ]
