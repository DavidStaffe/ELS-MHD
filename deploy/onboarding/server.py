"""Public, socket-activated certificate onboarding. No application imports/state."""
import datetime
import io
import os
from pathlib import Path
import re
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
import qrcode
import qrcode.image.svg

ORIGIN = "http://10.0.0.1:8081"


def assets(raw):
    # Reject bundles, keys and trailing payloads; serve only canonical public DER.
    if not re.fullmatch(rb"\s*-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*", raw):
        raise ValueError("Expected exactly one public PEM certificate")
    cert = x509.load_pem_x509_certificate(raw)
    if not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError("Not a CA")
    if not cert.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign:
        raise ValueError("CA cannot sign certificates")
    now = datetime.datetime.now(datetime.timezone.utc)
    # Debian Bookworm cryptography predates the *_utc properties.
    before = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before.replace(tzinfo=datetime.timezone.utc)
    after = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
    if not before <= now <= after:
        raise ValueError("CA outside validity period")
    fingerprint = ":".join(f"{b:02X}" for b in cert.fingerprint(hashes.SHA256()))
    qr = qrcode.make(ORIGIN + "/", image_factory=qrcode.image.svg.SvgPathImage)
    stream = io.BytesIO()
    qr.save(stream)
    page = (Path(__file__).with_name("index.html").read_text(encoding="utf-8")
            .replace("{{FINGERPRINT}}", fingerprint).encode())
    return {
        "/": ("text/html; charset=utf-8", page),
        "/ca.crt": ("application/pkix-cert", cert.public_bytes(serialization.Encoding.DER)),
        "/qr.svg": ("image/svg+xml", stream.getvalue()),
        "/fingerprint.txt": ("text/plain; charset=utf-8", (fingerprint + "\n").encode()),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    resources = {}

    def log_message(self, *args):
        pass  # Do not persist client addresses, paths, headers or cookies.

    def handle_one_request(self):
        self.connection.settimeout(3)
        super().handle_one_request()

    def do_GET(self):
        self.respond(False)

    def do_HEAD(self):
        self.respond(True)

    def respond(self, head):
        allowed = (self.headers.get_all("Host") == ["10.0.0.1:8081"]
                   and self.path in self.resources)
        kind, body = self.resources[self.path] if allowed else ("text/plain", b"Not found\n")
        self.send_response(200 if allowed else 404)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if allowed and self.path == "/ca.crt":
            self.send_header("Content-Disposition", 'attachment; filename="els-mhd-ca.crt"')
        self.end_headers()
        if not head:
            self.wfile.write(body)


def main():
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise RuntimeError("Requires systemd hotspot socket")
    Handler.resources = assets((Path(os.environ["CREDENTIALS_DIRECTORY"]) / "ca.crt").read_bytes())
    server = HTTPServer(("10.0.0.1", 8081), Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = socket.socket(fileno=3)
    if server.socket.getsockname() != ("10.0.0.1", 8081):
        raise RuntimeError("Unexpected socket binding")
    server.serve_forever()


if __name__ == "__main__":
    main()
