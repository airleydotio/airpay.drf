from firebase_admin import messaging


class FirebaseMessage:
    def __init__(self):
        pass

    @staticmethod
    def send(title, body, token_ids, silent=False):
        """
        Send push notification to specified device tokens.
        """
        messages = [messaging.Message(
            data={
                "title": title,
                "body": body,
                'silent': silent
            },
            token=token_id,
        ) for token_id in token_ids]

        try:
            response = messaging.send_all(messages)
            return response
        except Exception as e:
            print(e)
            return False
