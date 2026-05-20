from __future__ import annotations

import asyncio
import errno
import logging
import os
import traceback

from collections.abc import Callable


Error = str



class HTTPRequest:
    def __init__(self) -> None:
        self.method: str = ""
        self.path: str = ""
        self.http_version: str = ""

        self.headers: list[str] = []
        self.headers_dict: dict[str, str] = {}
        self.body: bytes = b""

        self.cookies: dict[str, str] = {}
        self.catchall: dict[str, str] = {}

        # NOTE(vanya): Sorted by preference, user's most preffered language first
        self.preffered_languages: list[str] = []



class HTTPResponse:
    def __init__(self) -> None:
        self.status_code: int = 200
        self.headers: list[str] = []
        self.body: bytes = b""
    

    def to_bytes(self) -> bytes:
        header_str = "\r\n".join([
            f"HTTP/1.1 {self.status_code} OK",
            f"Content-Length: {len(self.body)}",
            *self.headers,
        ])
        return header_str.encode("utf-8") + b"\r\n\r\n" + self.body
    

    def set_data(self, p_data: bytes) -> HTTPResponse:
        self.body = p_data
        return self


    def set_cookie(self, p_name: str, p_value: str, p_path: str="/", p_expiration_seconds: int=0) -> HTTPResponse:
        cookie_str: str = f"{p_name}={p_value}; Path={p_path}"
        
        if p_expiration_seconds > 0:
            cookie_str += f"; Max-Age={p_expiration_seconds}"
        
        self.headers.append(f"Set-Cookie: {cookie_str}")

        return self


    @staticmethod
    def ok(p_data: bytes=b"", p_headers: list[str]=[]) -> HTTPResponse:
        new_response = HTTPResponse()
        new_response.status_code = 200
        new_response.body = p_data
        new_response.headers.extend(p_headers)
        return new_response


    @staticmethod
    def not_found(p_data: bytes=b"", p_headers: list[str]=[]) -> HTTPResponse:
        new_response = HTTPResponse()
        new_response.status_code = 404
        new_response.body = p_data
        new_response.headers.extend(p_headers)
        return new_response


    @staticmethod
    def reject(p_data: bytes=b"", p_headers: list[str]=[]) -> HTTPResponse:
        new_response = HTTPResponse()
        new_response.status_code = 403
        new_response.body = p_data
        new_response.headers.extend(p_headers)
        return new_response


    @staticmethod
    def redirect(p_location: str, p_data: bytes=b"", p_headers: list[str]=[]) -> HTTPResponse:
        new_response = HTTPResponse()
        new_response.status_code = 302
        new_response.headers.append(f"Location: {p_location}")
        new_response.body = p_data
        new_response.headers.extend(p_headers)

        return new_response


    @staticmethod
    def raw_file(p_path: str) -> HTTPResponse:
        if os.path.exists(p_path) and os.path.isfile(p_path):
            with open(p_path, "rb") as f:
                return HTTPResponse.ok(f.read())
        return HTTPResponse.not_found()


class HTTPServer:
    logger = logging.getLogger("HTTPServer")
    logger.setLevel(logging.INFO)

    def __init__(self) -> None:
        self.request_handler: Callable = None


    async def serve_forever(self, p_http_request_handler: Callable, p_port: int=8000) -> Error:
        self.request_handler = p_http_request_handler
        
        try:
            server = await asyncio.start_server(self.handle_client, "::1", p_port)

            self.logger.info(f"Server up at `http://[::1]:{p_port}` (Press Ctrl+C to stop)")

            async with server:
                await server.serve_forever()

        except OSError as error:
            match error.errno:
                case errno.EADDRINUSE:
                    self.logger.error(f"OSError .errno=EADDRINUSE ({error.errno}) - Port already in use.")
                case errno.EACCES:
                    self.logger.error(f"OSError .errno=EACCES ({error.errno}) - Permission denied by the OS.")
                case errno.EINVAL:
                    self.logger.error(f"OSError .errno=EINVAL ({error.errno}) - Invalid address.")
                case errno.EAFNOSUPPORT:
                    self.logger.error(f"OSError .errno=EAFNOSUPPORT ({error.errno}) - Address family not supported.")
                case errno.EADDRNOTAVAIL:
                    self.logger.error(f"OSError .errno=EADDRNOTAVAIL ({error.errno}) - Trying to bind to an IP not assigned to your machine.")
                case errno.EOPNOTSUPP:
                    self.logger.error(f"OSError .errno=EOPNOTSUPP ({error.errno}) - Binding not supported by the OS.")
                case _:
                    self.logger.error(f"OSError .errno={error.errno} - Unhandled by moeserver error!")
            return "SERVER_BIND_FAIL"
        
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            return "SERVER_ERROR"
        
        return "OK"


    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            self.logger.debug(f"New client at `{writer.get_extra_info('peername')}`")

            # NOTE(vanya): Request info is a bundle of data
            # which goes through the entire pipeline starting here, an HTTP receiever.
            # It is used to store all the data related to the request,
            # such as - method, path, headers, body, cookies, catchall
            request = HTTPRequest()
            
            # NOTE(vanya): Recieve request line
            request_line_bytes: bytes = await reader.readline()
            if not request_line_bytes:
                return

            request_line: str = request_line_bytes.decode("utf-8")
            request_line_parts: list[str] = request_line.split(" ", 2)

            request.method = request_line_parts[0]
            request.path = request_line_parts[1]
            request.http_version = request_line_parts[2].strip() # NOTE(vanya): Remove trailing \r\n

            self.logger.debug(f"Received request `{request.method} {request.path} {request.http_version}`")

            # NOTE(vanya): Recieve headers
            while True:
                header = await reader.readline()
                if header == b'\r\n' or header == b'\n' or not header:
                    # NOTE(vanya): End of headers
                    break
                else:
                    # NOTE(vanya): Store raw AND parsed header
                    header_str: str = header.decode("utf-8").rstrip("\r\n")
                    request.headers.append(header_str)

                    header_parts: list[str] = header_str.split(": ", 2)
                    request.headers_dict[header_parts[0]] = header_parts[1]

            # NOTE(vanya): Receive body
            content_length = int(request.headers_dict.get("Content-Length", "0"))

            request.body = b""
            if content_length > 0:
                request.body = await reader.readexactly(content_length)

            # NOTE(vanya): Get response from request handler
            response: HTTPResponse = await self.request_handler(request)

            # NOTE(vanya): Send response
            writer.write(response.to_bytes())
            await writer.drain()

        except Exception as e:
            self.logger.error(f"Client handling error: {e}")
            traceback.print_exc()
        
        finally:
            self.logger.debug(f"Closing client connection")
            writer.close()
            await writer.wait_closed()
