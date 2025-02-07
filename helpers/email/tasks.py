from abc import ABC
from celery import shared_task
import celery

from airpay.helpers.email.email import Email

class BaseTaskWithRetry(ABC, celery.Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {'max_retries': 3}
    abstract = True

@shared_task(
    bind=True,
    base=BaseTaskWithRetry,
    soft_time_limit=1  # 1 second timeout for email sending
)
def send_email(self, data: dict):
    """Send an email using the Email helper class.
    
    Args:
        data (dict): Dictionary containing email data including:
            to: Recipient email
            subject: Email subject
            body: Email body (optional)
            template_id: Email template ID (optional) 
            dynamic_template_data: Template variables (optional)
    """
    try:
        email = Email(
            to=data.get('to'),
            subject=data.get('subject'),
            body=data.get('body'),
            template_id=data.get('template_id'),
            dynamic_template_data=data.get('dynamic_template_data')
        )
        return email.send()
    except Exception as exc:
        # Let BaseTaskWithRetry handle retries with exponential backoff
        raise exc