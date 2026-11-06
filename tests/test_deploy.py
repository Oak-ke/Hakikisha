import io
import json

from fastapi.testclient import TestClient

from app import db as dbmod
from app import main


def test_site_and_config_served(tmp_path):
    dbmod.set_db(dbmod.DB(str(tmp_path / "t.db")))
    c = TestClient(main.app)
    r = c.get("/")
    assert r.status_code == 200 and "Hakikisha" in r.text
    assert c.get("/checker.js").status_code == 200
    assert 'HAKIKISHA_API = "."' in c.get("/config.js").text
    assert c.get("/health").json() == {"ok": True}  # API routes still win over the static mount


def test_cors_for_github_pages(tmp_path):
    dbmod.set_db(dbmod.DB(str(tmp_path / "t.db")))
    c = TestClient(main.app)
    r = c.options("/check", headers={"Origin": "https://oak-ke.github.io",
                                     "Access-Control-Request-Method": "POST",
                                     "Access-Control-Request-Headers": "content-type"})
    assert r.headers.get("access-control-allow-origin") == "https://oak-ke.github.io"


def test_passenger_wsgi_entry(tmp_path):
    """Simulate how Passenger calls the app on cPanel."""
    dbmod.set_db(dbmod.DB(str(tmp_path / "t.db")))
    from passenger_wsgi import application

    body = json.dumps({"text": "Miracle cure for prostate, lipa na M-Pesa till 512345"}).encode()
    environ = {
        "REQUEST_METHOD": "POST", "PATH_INFO": "/check", "QUERY_STRING": "", "SCRIPT_NAME": "",
        "SERVER_NAME": "localhost", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
        "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body), "wsgi.errors": io.StringIO(), "wsgi.url_scheme": "http",
        "wsgi.version": (1, 0), "wsgi.multithread": True, "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    status = {}

    def start_response(s, headers, exc_info=None):
        status["s"] = s

    out = b"".join(application(environ, start_response))
    assert status["s"].startswith("200")
    assert json.loads(out)["results"][0]["level"] == "high"
