"""Streamlit dashboard sections extracted from the legacy app.py."""

from .dashboard import (
                        render_connection_overview,
                        render_data_board,
                        render_error_log,
                        render_operations_panel,
                        render_table_overview,
)

__all__ = [
    "render_connection_overview",
    "render_data_board",
    "render_table_overview",
    "render_operations_panel",
    "render_error_log",
]
