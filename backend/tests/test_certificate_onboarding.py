"""Synthetic certificates and local HTTP only; no production access."""
import datetime
import http.client
import importlib.util
from pathlib import Path
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('onboarding', ROOT / 'deploy/onboarding/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def certificate(ca=True, sign=True, expired=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'synthetic CA')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now - datetime.timedelta(days=2))
            .not_valid_after(now + datetime.timedelta(days=-1 if expired else 1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, sign, sign, False, False), critical=True)
            .sign(key, hashes.SHA256()))
    return cert, key


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def test_exact_public_certificate_and_der_fingerprint(monkeypatch):
    original = module.qrcode.make
    encoded = []
    def make(data, **kwargs):
        encoded.append(data)
        return original(data, **kwargs)
    monkeypatch.setattr(module.qrcode, 'make', make)
    cert, key = certificate()
    resources = module.assets(pem(cert))
    assert encoded == ['http://10.0.0.1:8081/']
    assert set(resources) == {'/', '/ca.crt', '/qr.svg', '/fingerprint.txt'}
    downloaded = x509.load_der_x509_certificate(resources['/ca.crt'][1])
    assert downloaded == cert
    assert resources['/fingerprint.txt'][1].decode().strip().replace(':', '') == cert.fingerprint(hashes.SHA256()).hex().upper()
    assert b'{{FINGERPRINT}}' not in resources['/'][1]
    assert b'<svg' in resources['/qr.svg'][1]
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    for bad in (pem(cert) + private, private, pem(cert) * 2, pem(cert) + b'extra'):
        with pytest.raises(ValueError):
            module.assets(bad)


@pytest.mark.parametrize('kwargs', [{'ca': False}, {'sign': False}, {'expired': True}])
def test_reject_invalid_ca(kwargs):
    with pytest.raises(ValueError):
        module.assets(pem(certificate(**kwargs)[0]))


def test_http_allowlist_methods_headers_and_no_application_surface():
    module.Handler.resources = module.assets(pem(certificate()[0]))
    server = module.HTTPServer(('127.0.0.1', 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for method, path, host, expected in [
            ('GET', '/', '10.0.0.1:8081', 200),
            ('HEAD', '/ca.crt', '10.0.0.1:8081', 200),
            *[('GET', path, '10.0.0.1:8081', 404) for path in
              ['/api/meta', '/login', '/ca.key', '/../config/tls/ca.key', '/%2e%2e/ca.key', '/?x=1', 'http://10.0.0.1:8081/']],
            ('GET', '/', 'evil.example', 404),
            ('POST', '/', '10.0.0.1:8081', 501),
        ]:
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            connection.request(method, path, headers={'Host': host, 'Cookie': 'synthetic=value'})
            response = connection.getresponse()
            assert response.status == expected
            assert response.getheader('Set-Cookie') is None
            assert response.getheader('Access-Control-Allow-Origin') is None
            if method in ('GET', 'HEAD'):
                assert response.getheader('Cache-Control') == 'no-store'
                assert "form-action 'none'" in response.getheader('Content-Security-Policy')
            if method == 'HEAD':
                assert response.read() == b''
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_startup_requires_systemd(monkeypatch):
    monkeypatch.delenv('LISTEN_PID', raising=False)
    with pytest.raises(RuntimeError, match='systemd'):
        module.main()


def test_hotspot_is_fixed_and_runtime_unchanged():
    socket = (ROOT / 'deploy/systemd/els-mhd-onboarding.socket').read_text()
    assert 'ListenStream=10.0.0.1:8081' in socket
    assert 'BindToDevice=wlan0' in socket and 'FreeBind=no' in socket
    service = (ROOT / 'deploy/systemd/els-mhd-onboarding.service').read_text()
    assert 'LoadCredential=ca.crt:/opt/els-mhd/config/tls/ca.crt' in service
    assert 'InaccessiblePaths=/opt' in service
    installer = (ROOT / 'deploy/onboarding/install.sh').read_text()
    assert 'flock -n' in installer and 'bundle.json' in installer
    assert 'docker compose' not in installer
