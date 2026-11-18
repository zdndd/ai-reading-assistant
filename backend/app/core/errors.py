class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BookNotFoundError(AppError):
    status_code = 404
    code = "book_not_found"


class InvalidDocumentError(AppError):
    status_code = 422
    code = "invalid_document"


class DocumentTooLargeError(AppError):
    status_code = 413
    code = "document_too_large"


class ModelUnavailableError(AppError):
    status_code = 503
    code = "model_unavailable"


class InvalidQuestionError(AppError):
    status_code = 422
    code = "invalid_question"


class GenerationError(AppError):
    status_code = 502
    code = "generation_failed"
