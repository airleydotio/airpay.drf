"""
Custom base model for airpay that maps created_at/updated_at to create_date/update_date database columns.
This allows airpay models to use the new field names while maintaining compatibility with existing database schema.
"""

from django.db import models
from apps.core.models import UUIDModel

class AirpayTimestampedModel(models.Model):
    """
    Timestamped model compatible with airpay's existing database schema.
    Maps created_at -> create_date and updated_at -> update_date at the database level.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='create_date',  # Map to existing database column
        verbose_name='Created At',
        help_text='Timestamp when the record was created'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='update_date',  # Map to existing database column
        verbose_name='Updated At',
        help_text='Timestamp when the record was last updated'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']


class AirpaySoftDeleteModel(models.Model):
    """
    Soft delete model compatible with airpay's existing database schema.
    Note: Only includes is_deleted field, not deleted_at (not in airpay schema).
    """
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class AirpayBaseModel(UUIDModel, AirpayTimestampedModel, AirpaySoftDeleteModel):
    """
    Base model for airpay that combines UUID, custom timestamps (with db_column mapping), and soft delete.
    """

    class Meta:
        abstract = True

    def __str__(self):
        """Default string representation using name or id"""
        if hasattr(self, 'name'):
            return str(self.name)
        return str(self.id)
