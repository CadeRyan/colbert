"""HTTP layer of the ledger (ledger/api.py), called in-process through WSGI."""
import io
import json
import os
import tempfile
import unittest

from ledger import core
from ledger.api import App
from ledger.core import Ledger
from ledger.store import Contention, SqliteStore


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = SqliteStore(os.path.join(self.tmp, "l.sqlite"), core.INDEXES)
        self.app = App(Ledger(self.store), admin_token="secret", log=io.StringIO())

    def tearDown(self):
        self.store.close()

    def call(self, method, path, body=None, auth=None, raw=None, env_extra=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "", "CONTENT_LENGTH": str(len(data)),
               "wsgi.input": io.BytesIO(data), "REMOTE_ADDR": "127.0.0.1"}
        if auth:
            env["HTTP_AUTHORIZATION"] = "Bearer " + auth
        env.update(env_extra or {})
        out = {}

        def start(status, headers):
            out["status"], out["headers"] = int(status.split()[0]), dict(headers)
        payload = b"".join(self.app(env, start))
        try:
            out["json"] = json.loads(payload)
        except ValueError:
            out["text"] = payload.decode()
        return out

    def test_full_cycle(self):
        r = self.call("POST", "/v1/admin/seed", {"pairs": [[21181, 3001], [67607, 3003]]}, auth="admin:secret")
        self.assertEqual((r["status"], r["json"]["added"]), (200, 2))
        self.call("POST", "/v1/admin/config", {"worker_trust_after": 0, "engine_trust_after": 0, "dc_fraction": 0.0}, auth="admin:secret")
        reg = self.call("POST", "/v1/register", {"owner": "<b>me</b>", "name": "pc"})["json"]
        auth = "%s:%s" % (reg["worker_id"], reg["token"])
        a = self.call("POST", "/v1/work", {"info": {"engine": "e1", "backend": "cpu"}}, auth=auth)["json"]["assignment"]
        self.assertEqual((a["k"], a["n"]), (21181, 3001))
        r = self.call("POST", "/v1/progress", {"assignment": a["id"], "report": {"iteration": 5}}, auth=auth)
        self.assertEqual(r["json"]["action"], "continue")
        res = {"k": 21181, "n": 3001, "result": "composite", "res64": "0123456789abcdef", "iterations": 3000, "engine": "e1", "backend": "cpu"}
        r = self.call("POST", "/v1/result", {"assignment": a["id"], "result": res}, auth=auth)
        self.assertEqual((r["status"], r["json"]["status"]), (200, "done"))
        s = self.call("GET", "/v1/status")
        self.assertEqual(s["json"]["counts"], {"done": 1})
        self.assertEqual(s["headers"].get("Access-Control-Allow-Origin"), "*")
        page = self.call("GET", "/")
        self.assertIn("Colbert", page["text"])
        self.assertIn("&lt;b&gt;me&lt;/b&gt;", page["text"], "owner names are escaped on the status page")
        self.assertNotIn("<b>me</b>", page["text"])

    def test_factor_over_http(self):
        self.call("POST", "/v1/admin/seed", {"pairs": [[21181, 3001]]}, auth="admin:secret")
        reg = self.call("POST", "/v1/register", {"owner": "me", "name": "pc"})["json"]
        auth = "%s:%s" % (reg["worker_id"], reg["token"])
        a = self.call("POST", "/v1/work", {"info": {"engine": "e1", "backend": "opencl: gpu"}}, auth=auth)["json"]["assignment"]
        bad = {"k": 21181, "n": 3001, "factor": "7", "engine": "e1", "backend": "opencl: gpu"}
        r = self.call("POST", "/v1/result", {"assignment": a["id"], "result": bad}, auth=auth)
        self.assertEqual((r["status"], r["json"]["error"]["code"] if isinstance(r["json"].get("error"), dict) else r["json"].get("code")), (422, "not_a_factor"))
        good = dict(bad, factor="3")                      # 21181*2^3001+1 = 0 (mod 3)
        r = self.call("POST", "/v1/result", {"assignment": a["id"], "result": good}, auth=auth)
        self.assertEqual((r["status"], r["json"]["status"]), (200, "factored"))
        s = self.call("GET", "/v1/status")["json"]
        self.assertEqual((s["counts"], s["factors"]), ({"factored": 1}, 1))
        self.assertIn("Factors found by P", self.call("GET", "/")["text"])

    def test_auth_and_errors(self):
        self.assertEqual(self.call("POST", "/v1/work", {})["status"], 401)
        self.assertEqual(self.call("POST", "/v1/work", {}, auth="wx:bad")["status"], 401)
        self.assertEqual(self.call("GET", "/v1/admin/config")["status"], 401)
        self.assertEqual(self.call("GET", "/v1/admin/config", auth="admin:wrong")["status"], 401)
        self.assertEqual(self.call("GET", "/v1/admin/config", auth="admin:secret")["status"], 200)
        self.assertEqual(self.call("GET", "/nowhere")["status"], 404)
        self.assertEqual(self.call("GET", "/v1/register")["status"], 405)
        self.assertEqual(self.call("POST", "/v1/register", raw=b"not json")["status"], 400)
        self.assertEqual(self.call("POST", "/v1/register", raw=b"[1,2]")["status"], 400)
        big = b'{"x":"' + b"a" * (2 << 20) + b'"}'
        self.assertEqual(self.call("POST", "/v1/register", raw=big)["status"], 413)
        self.assertEqual(self.call("POST", "/v1/admin/config", {"nope": 1}, auth="admin:secret")["status"], 400)
        self.assertEqual(self.call("POST", "/v1/admin/seed", {"pairs": "x"}, auth="admin:secret")["status"], 400)

    def test_registration_limit_ignores_a_forged_forwarded_for(self):
        # behind one proxy (Cloud Run): the client controls everything before the last entry
        self.app.proxy_hops = 1
        codes = [self.call("POST", "/v1/register", {"owner": "x"},
                           env_extra={"HTTP_X_FORWARDED_FOR": "10.0.0.%d, 203.0.113.7" % i})["status"] for i in range(12)]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertEqual(codes[10:], [429, 429], "a new forged first entry each time doesn't reset the limit")
        other = self.call("POST", "/v1/register", {"owner": "y"}, env_extra={"HTTP_X_FORWARDED_FOR": "203.0.113.8"})
        self.assertEqual(other["status"], 200, "another real address has its own limit")
        # no proxy (python3 -m ledger serve): the header is ignored, the connection address counts
        self.app.proxy_hops = 0
        codes = [self.call("POST", "/v1/register", {"owner": "z"},
                           env_extra={"HTTP_X_FORWARDED_FOR": "198.51.100.%d" % i, "REMOTE_ADDR": "192.0.2.5"})["status"] for i in range(11)]
        self.assertEqual(codes[-1], 429)

    def test_factor_with_bad_credentials_is_refused_before_it_is_checked(self):
        huge = {"k": 1, "n": 2 ** 31 - 1, "factor": "3"}
        r = self.call("POST", "/v1/result", {"assignment": "a0", "result": huge}, auth="wnobody:wrong")
        self.assertEqual((r["status"], r["json"]["code"]), (401, "unauthorized"))

    def test_admin_disabled_without_token(self):
        app = App(Ledger(self.store), admin_token="", log=io.StringIO())
        self.app = app
        self.assertEqual(self.call("GET", "/v1/admin/config", auth="admin:")["status"], 403)

    def test_contention_is_503_with_retry_after(self):
        reg = self.call("POST", "/v1/register", {"owner": "a"})["json"]

        def busy(*a, **k):
            raise Contention("busy")
        self.app.L.request_work = busy
        r = self.call("POST", "/v1/work", {"info": {"engine": "e"}}, auth="%s:%s" % (reg["worker_id"], reg["token"]))
        self.assertEqual(r["status"], 503)
        self.assertTrue(r["headers"]["Retry-After"].isdigit())

    def test_status_is_cached(self):
        calls = []
        real = self.app.L.status
        self.app.L.status = lambda: calls.append(1) or real()
        for _ in range(5):
            self.call("GET", "/v1/status")
        self.assertEqual(len(calls), 1)

    def test_registration_rate_limit(self):
        codes = [self.call("POST", "/v1/register", {"owner": "x"})["status"] for _ in range(15)]
        self.assertIn(429, codes)


if __name__ == "__main__":
    unittest.main()
