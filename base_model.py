"""
Optional default base model for airpay.

Hosts may instead set AIRPAY['BASE_MODEL'] to their own abstract model.
This module must not import host-app packages.
"""

import uuid

from django.db import models


class AirpayTimestampedModel(models.Model):
    """Maps created_at/updated_at onto create_date/update_date DB columns."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="create_date",
        verbose_name="Created At",
        help_text="Timestamp when the record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column="update_date",
        verbose_name="Updated At",
        help_text="Timestamp when the record was last updated",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class AirpaySoftDeleteModel(models.Model):
    """Soft-delete flag only (no deleted_at — not in the airpay schema)."""

    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class AirpayUUIDModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )

    class Meta:
        abstract = True


class AirpayBaseModel(AirpayUUIDModel, AirpayTimestampedModel, AirpaySoftDeleteModel):
    """Default airpay base: UUID PK + mapped timestamps + soft delete."""

    class Meta:
        abstract = True

    def __str__(self):
        if hasattr(self, "name"):
            return str(self.name)
        return str(self.id)
