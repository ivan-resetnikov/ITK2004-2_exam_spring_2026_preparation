import moe.server
import moe.sql


app = moe.server.App()

@app.get("/")
def _(p_request: moe.server.HTTPRequest) -> moe.server.HTTPResponse:
    return moe.server.HTTPResponse.raw_file("./pages/index.html")


app.serve_until_KeyboardInterrupt(8000)