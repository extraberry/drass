"""Domain errors. Each carries an API error_code and HTTP status (PRD s75)."""
from typing import Optional


class DrassError(Exception):
    error_code = "ERROR"
    http_status = 400

    def __init__(self, message: str, fields: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.fields = fields


class Forbidden(DrassError): error_code, http_status = "FORBIDDEN", 403
class ValidationFailed(DrassError): error_code, http_status = "VALIDATION_ERROR", 422
class InvalidTransition(DrassError): error_code, http_status = "INVALID_TRANSITION", 409
class StaleState(DrassError): error_code, http_status = "STALE_STATE", 409
class DuplicateResearch(DrassError): error_code, http_status = "DUPLICATE_RESEARCH", 409
class Conflict(DrassError): error_code, http_status = "CONFLICT", 409
class NotFound(DrassError): error_code, http_status = "NOT_FOUND", 404
class AuthFailed(DrassError): error_code, http_status = "AUTH_FAILED", 401
class SessionExpired(DrassError): error_code, http_status = "SESSION_EXPIRED", 401
class AccountLocked(DrassError): error_code, http_status = "ACCOUNT_LOCKED", 423
class AccountDisabled(DrassError): error_code, http_status = "ACCOUNT_DISABLED", 403
class StorageError(DrassError): error_code, http_status = "STORAGE_ERROR", 500
class EmbeddingUnavailable(DrassError): error_code, http_status = "EMBEDDING_UNAVAILABLE", 503
