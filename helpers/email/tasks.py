from celery import shared_task

from airpay.helpers.email.email import Email


@shared_task()
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