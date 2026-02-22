"""
Helper to import Lambda handler modules for testing.

Lambda handlers use sys.path.insert(0, "../../shared") and bare imports
like `from lambda_responses import ...`. This module sets up the Python
path and sys.modules so that handlers can be loaded via importlib.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

# Resolve paths
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BACKEND_PATH = os.path.join(_REPO_ROOT, "backend")
_SHARED_PATH = os.path.join(_BACKEND_PATH, "shared")


def _ensure_shared_imports():
    """Pre-import shared package and alias flat module names in sys.modules."""
    if _BACKEND_PATH not in sys.path:
        sys.path.insert(0, _BACKEND_PATH)
    if _SHARED_PATH not in sys.path:
        sys.path.insert(0, _SHARED_PATH)

    # Import as package modules (relative imports work)
    import shared.constants
    import shared.utils
    import shared.lambda_responses
    import shared.aws_clients
    import shared.models

    # Alias flat names so handler-style `from utils import ...` works
    sys.modules.setdefault("constants", shared.constants)
    sys.modules.setdefault("utils", shared.utils)
    sys.modules.setdefault("lambda_responses", shared.lambda_responses)
    sys.modules.setdefault("aws_clients", shared.aws_clients)
    sys.modules.setdefault("models", shared.models)


def load_handler(handler_path: str, module_name: str | None = None):
    """
    Load a Lambda handler module with mocked AWS clients.

    Args:
        handler_path: Path relative to backend/ (e.g. "lambdas/jobs/download_partial.py")
        module_name: Optional module name for sys.modules cache

    Returns:
        The loaded module with lambda_handler attribute.
        Module-level AWS clients (dynamodb, s3_client, etc.) will be MagicMock
        instances that should be replaced before calling lambda_handler.
    """
    _ensure_shared_imports()

    full_path = os.path.join(_BACKEND_PATH, handler_path)
    if module_name is None:
        module_name = f"_handler_{os.path.basename(handler_path).replace('.py', '')}"

    # Remove cached module to get a fresh import
    if module_name in sys.modules:
        del sys.modules[module_name]

    mock_dynamodb = MagicMock()
    mock_s3 = MagicMock()
    mock_sfn = MagicMock()

    with patch("shared.aws_clients.get_dynamodb_resource", return_value=mock_dynamodb), \
         patch("shared.aws_clients.get_s3_client", return_value=mock_s3), \
         patch("shared.aws_clients.get_sfn_client", return_value=mock_sfn):
        spec = importlib.util.spec_from_file_location(module_name, full_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    return mod
