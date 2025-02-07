from abc import ABC
from celery import shared_task
import celery

from airpay.helpers.email.email import Email

class BaseTaskWithRetry(ABC, celery.Task):
    autoretry_for = (Exception, )
    retry_kwargs = {'max_retries': 3, 'countdown': 10}


@shared_task(base=BaseTaskWithRetry)
def send_email(data: dict):
    print('Sending email')
    try:
        email = Email(
            to=data.get('to'),
            subject=data.get('subject'),
            body=data.get('body'),
            template_id=data.get('template_id'),
            dynamic_template_data=data.get('dynamic_template_data')
        )
        email.send()
        print('Email sent')
    except Exception as e:
        print('Error sending email: ', e)
        raise e
    