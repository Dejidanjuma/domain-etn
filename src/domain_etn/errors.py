"""Typed product errors. Never a successful registration."""

from __future__ import annotations


class ProductError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status
