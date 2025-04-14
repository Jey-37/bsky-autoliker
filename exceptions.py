class HttpException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code

class TooManyRequestsException(HttpException):
    def __init__(self, message=None):
        super().__init__(429, message)

class BadRequestException(HttpException):
    def __init__(self, message=None):
        super().__init__(400, message)
