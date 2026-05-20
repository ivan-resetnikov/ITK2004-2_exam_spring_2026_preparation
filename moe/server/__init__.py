# moesql Copyright (c) 2026, Ivan Reshetnikov - All rights reserved.

# NOTE(vanya): Enable logging
import logging

logging.basicConfig(level=logging.DEBUG)


# NOTE(vanya): Shorthands for commonly used types and functions
from .app import App

from .http import HTTPServer
from .http import HTTPRequest
from .http import HTTPResponse

from .html import HTMLRenderer
from .html import HTML
