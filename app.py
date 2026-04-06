from app import create_app
import os
import webbrowser
from threading import Timer

app = create_app()

if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", "5000"))

    def open_browser():
        webbrowser.open_new(f"http://{host}:{port}/")

    Timer(0.8, open_browser).start()
    app.run(host=host, port=port, debug=True)