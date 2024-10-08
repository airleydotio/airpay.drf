from django.conf import settings
from django.core.mail import EmailMessage


class Email:
    def __init__(self, to, subject, body=None, template_id=None, dynamic_template_data=None):
        self.template_id = template_id
        self.message = EmailMessage(
            to=[to],
            subject=subject,
            body=body,
            from_email=settings.EMAIL_HOST_USER
        )
        self.message.template_id = template_id
        self.message.merge_global_data = dynamic_template_data

    def add_to_list(self, to):
        # Add a recipient to the email
        self.message.to.append(to)

    def send(self):
        try:
            self.message.send()
        except Exception as e:
            raise Exception(str(e))
