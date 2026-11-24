from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from policy import CredentialRedirects, origin


class RedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.received = []

        class Receiver(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.received.append((self.path, self.headers.get("Authorization")))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                pass

        cls.other = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)

        class Redirector(Receiver):
            def do_GET(self):
                if self.path == "/same":
                    target = "/accepted"
                elif self.path == "/cross":
                    target = f"http://127.0.0.1:{cls.other.server_port}/accepted"
                else:
                    return super().do_GET()
                self.send_response(302)
                self.send_header("Location", target)
                self.send_header("Content-Length", "0")
                self.end_headers()

        cls.source = ThreadingHTTPServer(("127.0.0.1", 0), Redirector)
        cls.threads = []
        for server in (cls.source, cls.other):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.base = f"http://127.0.0.1:{cls.source.server_port}"

    @classmethod
    def tearDownClass(cls):
        for server in (cls.source, cls.other):
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=2)

    def setUp(self):
        self.received.clear()

    def request(self, path):
        return Request(self.base + path, headers={"Authorization": "Bearer synthetic-fixture-token"})

    def test_default_policy_refuses_before_second_request(self):
        with self.assertRaises(HTTPError):
            build_opener(ProxyHandler({}), CredentialRedirects()).open(self.request("/same"), timeout=2)
        self.assertEqual(self.received, [])

    def test_explicit_same_origin_read_can_keep_its_credential(self):
        with build_opener(ProxyHandler({}), CredentialRedirects(allow_same_origin_reads=True)).open(self.request("/same"), timeout=2) as response:
            self.assertEqual(response.read(), b"ok")
        self.assertEqual(self.received, [("/accepted", "Bearer synthetic-fixture-token")])

    def test_cross_origin_refuses_even_when_same_origin_is_allowed(self):
        with self.assertRaises(HTTPError):
            build_opener(ProxyHandler({}), CredentialRedirects(allow_same_origin_reads=True)).open(self.request("/cross"), timeout=2)
        self.assertEqual(self.received, [])

    def test_unprotected_transport_is_a_real_negative_control(self):
        with build_opener(ProxyHandler({})).open(self.request("/cross"), timeout=2) as response:
            self.assertEqual(response.read(), b"ok")
        self.assertEqual(self.received, [("/accepted", "Bearer synthetic-fixture-token")])

    def test_scheme_host_and_port_all_participate_in_origin(self):
        handler = CredentialRedirects(allow_same_origin_reads=True)
        request = Request("https://api.example.invalid/resource", headers={"Authorization": "fixture"})
        for target in ("http://api.example.invalid/resource", "https://other.example.invalid/resource",
                       "https://api.example.invalid:444/resource", "https://api.example.invalid:0/resource",
                       "https://user@api.example.invalid/resource"):
            with self.subTest(target=target):
                self.assertIsNone(handler.redirect_request(request, None, 302, "found", {}, target))
        self.assertEqual(origin("https://API.example.invalid:443/other"), origin(request.full_url))

    def test_write_request_is_not_replayed_or_converted_to_read(self):
        handler = CredentialRedirects(allow_same_origin_reads=True)
        request = Request("https://api.example.invalid/write", data=b"private input", method="POST")
        self.assertIsNone(handler.redirect_request(request, None, 303, "see other", {}, "https://api.example.invalid/other"))
