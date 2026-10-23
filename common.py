
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import html
import json
from pathlib import Path


class Store:
    def __init__(self, path, default):
        self.path = Path(path)

        if self.path.exists():
            try:
                self.data = json.loads(
                    self.path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                self.data = default.copy()
        else:
            self.data = default.copy()

    def save(self):
        self.path.write_text(
            json.dumps(self.data, indent=2),
            encoding="utf-8"
        )


def escape(value):
    return html.escape(str(value))


def heading(text):
    return f"<h2>{escape(text)}</h2>"


def note(text):
    return f"<p>{escape(text)}</p>"


def table(headers, rows):
    output = "<table border='1' cellpadding='8'>"

    output += "<tr>"
    for header in headers:
        output += f"<th>{escape(header)}</th>"
    output += "</tr>"

    for row in rows:
        output += "<tr>"
        for value in row:
            output += f"<td>{escape(value)}</td>"
        output += "</tr>"

    output += "</table>"
    return output


def form(action, fields, button_text):
    output = f"<form method='post'>"
    output += f"<input type='hidden' name='action' value='{escape(action)}'>"

    for name, label, input_type, default in fields:
        output += f"<label>{escape(label)}:</label>"
        output += (
            f"<input type='{escape(input_type)}' "
            f"name='{escape(name)}' "
            f"value='{escape(default)}'>"
        )
        output += "<br><br>"

    output += f"<button type='submit'>{escape(button_text)}</button>"
    output += "</form>"

    return output


def run(title, view, handle, host="127.0.0.1", port=8000):

    class Handler(BaseHTTPRequestHandler):

        def send_page(self, body):
            page = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{escape(title)}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 1000px;
                        margin: 40px auto;
                        padding: 20px;
                    }}

                    input {{
                        width: 500px;
                        padding: 8px;
                    }}

                    button {{
                        padding: 10px 15px;
                        margin-bottom: 15px;
                        cursor: pointer;
                    }}

                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin-top: 15px;
                        margin-bottom: 20px;
                    }}

                    th, td {{
                        text-align: left;
                        padding: 8px;
                    }}
                </style>
            </head>
            <body>
                <h1>{escape(title)}</h1>
                {body}
            </body>
            </html>
            """

            encoded = page.encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(encoded))
            )
            self.end_headers()

            self.wfile.write(encoded)

        def do_GET(self):
            try:
                self.send_page(view())
            except Exception as error:
                self.send_page(
                    note(f"Error: {error}")
                )

        def do_POST(self):
            try:
                length = int(
                    self.headers.get("Content-Length", 0)
                )

                body = self.rfile.read(length).decode("utf-8")
                parsed = parse_qs(body)

                data = {
                    key: values[0]
                    for key, values in parsed.items()
                }

                result = handle(data)
                self.send_page(
                    view() + result
                )

            except Exception as error:
                self.send_page(
                    view() + note(f"Error: {error}")
                )

        def log_message(self, format, *args):
            return

    server = HTTPServer((host, port), Handler)

    print(
        f"Running {title} at "
        f"http://{host}:{port}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
