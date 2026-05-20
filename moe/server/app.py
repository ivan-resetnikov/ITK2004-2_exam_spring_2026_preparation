import logging
import asyncio
import inspect

from .http import HTTPServer, HTTPRequest, HTTPResponse
from .html import HTMLRenderer, HTML

from collections.abc import Callable



Error = str



class Route:
    def __init__(self, p_method: str, p_path: str, p_handler: Callable) -> None:
        self.method: str = p_method
        self.path: str = p_path
        self.handler: Callable = p_handler



class App:
    logger: logging.Logger = logging.getLogger("App")
    logger.setLevel(logging.INFO)
    
    def __init__(self) -> None:
        # NOTE(vanya): The two must be in sync
        self.routes: list[Route] = []
        self.method_routes: dict[str, list[Route]] = {}

        self.public_prefix: str = ""
        self.public_handler: Callable = None

        self.http_server: HTTPServer = None
        self.html_renderer: HTMLRenderer = HTMLRenderer()

    
    def get(self, p_route: str) -> Callable:

        def definition_wrapper(p_decorated_function: Callable) -> Callable:

            async def call_wrapper(p_request_info: HTTPRequest) -> HTTPResponse:
                if inspect.iscoroutinefunction(p_decorated_function):
                    return await p_decorated_function(p_request_info)
                else:
                    return p_decorated_function(p_request_info)

            self.register_route("GET", p_route, call_wrapper)

            return call_wrapper

        return definition_wrapper


    def post(self, p_route: str) -> Callable:

        def definition_wrapper(p_decorated_function: Callable) -> Callable:
            
            async def call_wrapper(p_request_info: HTTPRequest) -> HTTPResponse:
                if inspect.iscoroutinefunction(p_decorated_function):
                    return await p_decorated_function(p_request_info)
                else:
                    return p_decorated_function(p_request_info)

            self.register_route("POST", p_route, call_wrapper)

            return call_wrapper

        return definition_wrapper
    

    def public(self, p_prefix: str) -> Callable:

        def definition_wrapper(p_decorated_function: Callable) -> Callable:
            
            async def call_wrapper(p_request_info: HTTPRequest) -> HTTPResponse:
                if inspect.iscoroutinefunction(p_decorated_function):
                    return await p_decorated_function(p_request_info)
                else:
                    return p_decorated_function(p_request_info)

            self.public_prefix = p_prefix
            self.public_handler = call_wrapper

            return call_wrapper

        return definition_wrapper
    

    def register_route(self, p_method: str, p_path: str, p_handler: Callable) -> None:
        new_route = Route(p_method, p_path, p_handler)

        self.logger.debug(f"Registering route `{p_method} {p_path}`")

        self.routes.append(new_route)
        self.method_routes[p_method] = self.method_routes.get(p_method, []) + [new_route]


    def serve_until_KeyboardInterrupt(self, p_port: int = 8000) -> Error:
        self.http_server = HTTPServer()
        
        try:
            return asyncio.run(self.http_server.serve_forever(self.handle_http_request, p_port))
        
        except KeyboardInterrupt:
            self.logger.info("Received KeyboardInterrupt, closing server")
            return "OK"
    

    async def handle_http_request(self, p_request: HTTPRequest) -> bytes:
        self.logger.debug(f"Handling HTTP request `{p_request.method} {p_request.path}`")

        if p_request.method == "GET" and self.public_handler and p_request.path.startswith(self.public_prefix):
            self.logger.debug(f"Using public handler for path `{p_request.path}`")
            return await self.public_handler(p_request)

        # TODO(vanya): Implement  
        method_routes: list[Route] = self.method_routes.get(p_request.method)

        for route in method_routes:
            route_path_parts: list[str] = route.path.split("/")
            requested_path_parts: list[str] = p_request.path.split("/")

            if len(route_path_parts) != len(requested_path_parts):
                continue

            part_index_to_check: int = 0
            while part_index_to_check < len(route_path_parts):
                route_path_part: str = route_path_parts[part_index_to_check]
                requested_path_part: str = requested_path_parts[part_index_to_check]
                
                part_matched: bool = False

                if route_path_part.startswith("[") and route_path_part.endswith("]"):
                    # NOTE(vanya): Catchall key
                    catchall_key: str = route_path_part[1:-1]

                    p_request.catchall[catchall_key] = requested_path_part
                    part_matched = True

                else:
                    part_matched = (route_path_part == requested_path_part)
                
                if part_matched:
                    # NOTE(vanya): Check if matched the entire path
                    if part_index_to_check + 1 == len(route_path_parts):
                        # NOTE(vanya): Route matched, call handler
                        self.logger.debug(f"Using route `{route.path}`")

                        # NOTE(vanya): Parse cookies
                        for header_line in p_request.headers:
                            if header_line.startswith("Cookie: "):
                                cookie_line: str = header_line.split(": ", 2)[1]

                                key, value = cookie_line.split("=", 2)

                                p_request.cookies[key] = value
                        
                        return await route.handler(p_request)
                else:
                    # NOTE(vanya): Part didn't match
                    break
                
                part_index_to_check += 1
        
        self.logger.debug(f"Route not found, returning 404")
        return HTTPResponse.not_found()
    