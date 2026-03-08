from fastapi import HTTPException
class ServiceException(HTTPException):
    def __init__(self, code: int = 400, message: str = "业务异常", data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(status_code=400, detail=message)