# webui/decorators.py
"""Shared decorators cho webui routes."""

import functools
import logging
from flask import jsonify

logger = logging.getLogger(__name__)


def handle_route_errors(f):
    """Decorator wrap route handlers với standardized error handling.

    Usage:
        @app.route("/api/endpoint")
        @handle_route_errors
        def my_endpoint():
            return jsonify({"data": result})
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({"error": str(e)}), 400
        except FileNotFoundError as e:
            logger.warning(f"Not found in {f.__name__}: {e}")
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    return wrapper
