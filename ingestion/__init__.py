"""Ingestion package exposing the public API for the prototype."""

from .config import AppConfig
from .pipeline import IngestionPipeline

__all__ = ["AppConfig", "IngestionPipeline"]
