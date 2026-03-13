from typing import Any


class NovelCreatorException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: dict[str, Any] | None = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class BookNotFoundError(NovelCreatorException):
    def __init__(self, book_id: int):
        super().__init__(message=f"书籍不存在 (ID: {book_id})", status_code=404)


class ChapterNotFoundError(NovelCreatorException):
    def __init__(self, book_id: int, chapter_number: int):
        super().__init__(
            message=f"第{chapter_number}章不存在",
            status_code=404,
            details={"book_id": book_id, "chapter": chapter_number},
        )


class AIServiceError(NovelCreatorException):
    def __init__(self, message: str, original_error: Exception | None = None):
        details = {"original_error": str(original_error)} if original_error else {}
        super().__init__(message=message, status_code=503, details=details)


class ValidationError(NovelCreatorException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)
