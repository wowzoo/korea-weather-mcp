"""Korea Weather MCP Server

A Model Context Protocol server that provides Korean weather forecasts using KMA API.
"""

__version__ = "0.1.0"

from .weather import main

__all__ = ["main"]