from rest_framework.response import Response


class SendResponse:
    def __init__(self, status_code, message, data=None, error=None, success=None):
        self.status_code = status_code
        self.message = message
        self.error = error
        self.success = success
        self.data = data

    def send(self):
        return Response(
            status=self.status_code,
            data={
                'message': self.message,
                'error': self.error,
                'success': self.success,
                'data': self.data
            }
        )
