"""统一异常定义"""


class AppException(Exception):
    """应用基础异常"""

    def __init__(self, message: str, code: str = None, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", code: str = "NOT_FOUND"):
        super().__init__(message, code, 404)


class ValidationError(AppException):
    def __init__(self, message: str = "参数校验失败", code: str = "VALIDATION_ERROR"):
        super().__init__(message, code, 422)


class AuthenticationError(AppException):
    def __init__(self, message: str = "认证失败", code: str = "AUTH_ERROR"):
        super().__init__(message, code, 401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "无权限访问", code: str = "FORBIDDEN"):
        super().__init__(message, code, 403)


class ConflictError(AppException):
    def __init__(self, message: str = "资源冲突", code: str = "CONFLICT"):
        super().__init__(message, code, 409)


class LLMError(AppException):
    def __init__(self, message: str = "AI 服务调用失败", code: str = "LLM_ERROR"):
        super().__init__(message, code, 502)


class ImageGenerationError(AppException):
    def __init__(self, message: str = "图片生成失败", code: str = "IMAGE_GEN_ERROR"):
        super().__init__(message, code, 502)
