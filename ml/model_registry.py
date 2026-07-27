"""
Model artifact paths and load/save helpers (joblib).
"""

import os
from typing import Any, Optional

import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "models", "artifacts")


def artifact_path(name: str) -> str:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    return os.path.join(ARTIFACTS_DIR, name)


def save_model(obj: Any, filename: str) -> str:
    path = artifact_path(filename)
    joblib.dump(obj, path)
    return path


def load_model(filename: str) -> Optional[Any]:
    path = artifact_path(filename)
    if not os.path.exists(path):
        return None
    return joblib.load(path)


def model_exists(filename: str) -> bool:
    return os.path.exists(artifact_path(filename))
