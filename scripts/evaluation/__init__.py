"""Fail-closed sealed evaluation utilities."""

from .sealed import (EnginePin, MatchResult, SealedProtocol, validate_engine,
                     validate_protocol)

__all__ = ["EnginePin", "MatchResult", "SealedProtocol", "validate_engine",
           "validate_protocol"]
