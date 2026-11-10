# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import os
import re
import ssl
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from unittest import mock

import certifi
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa, x25519
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    KeySerializationEncryption,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID

from deepfellow.common.defaults import CA_BUNDLE_FILENAME
from deepfellow.common.tls import (
    CAError,
    CAExistsError,
    generate_ca,
    import_ca,
    issue_certificate,
    local_names,
    write_ca_bundle,
    write_ssl_file,
)

NOW = datetime.now(timezone.utc)

# P-256 CA (valid until 2126) whose key is encoded with explicit curve parameters, made with
# `openssl ecparam -name prime256v1 -genkey -param_enc explicit`; cryptography can't produce one
EXPLICIT_CURVE_CA_PEM = b"""-----BEGIN CERTIFICATE-----
MIICgjCCAiegAwIBAgIUMIMhFhKUvKHzNdM0j8Sli15338cwCgYIKoZIzj0EAwIw
EzERMA8GA1UEAwwIRXhwbGljaXQwIBcNMjYxMTA1MTQwOTAzWhgPMjEyNjEwMTIx
NDA5MDNaMBMxETAPBgNVBAMMCEV4cGxpY2l0MIIBSzCCAQMGByqGSM49AgEwgfcC
AQEwLAYHKoZIzj0BAQIhAP////8AAAABAAAAAAAAAAAAAAAA////////////////
MFsEIP////8AAAABAAAAAAAAAAAAAAAA///////////////8BCBaxjXYqjqT57Pr
vVV2mIa8ZR0GsMxTsPY7zjw+J9JgSwMVAMSdNgiG5wSTamZ44ROdJreBn36QBEEE
axfR8uEsQkf4vOblY6RA8ncDfYEt6zOg9KE5RdiYwpZP40Li/hp/m47n60p8D54W
K84zV2sxXs7LtkBoN79R9QIhAP////8AAAAA//////////+85vqtpxeehPO5ysL8
YyVRAgEBA0IABHmdVuJEGdRRN8/IrE7EcEMLdmaaElq9fvtkBkgukPSap+u5Qw/b
pYg41RJnNoyMOJOrabnbaMfoR/kYi3Tb3cCjYzBhMB0GA1UdDgQWBBTX65R7pZLO
okCc+cDpA38EfG6suDAfBgNVHSMEGDAWgBTX65R7pZLOokCc+cDpA38EfG6suDAP
BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwICBDAKBggqhkjOPQQDAgNJADBG
AiEAiuZMYEwjqyH9vnX0gizpDPYuMg7beutH5glKD2Y2sP8CIQCteBCb7xndxhI5
KEOZS8YLzBlLuAHs5gatqr7s8qK03A==
-----END CERTIFICATE-----
"""
EXPLICIT_CURVE_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
MIIBeQIBADCCAQMGByqGSM49AgEwgfcCAQEwLAYHKoZIzj0BAQIhAP////8AAAAB
AAAAAAAAAAAAAAAA////////////////MFsEIP////8AAAABAAAAAAAAAAAAAAAA
///////////////8BCBaxjXYqjqT57PrvVV2mIa8ZR0GsMxTsPY7zjw+J9JgSwMV
AMSdNgiG5wSTamZ44ROdJreBn36QBEEEaxfR8uEsQkf4vOblY6RA8ncDfYEt6zOg
9KE5RdiYwpZP40Li/hp/m47n60p8D54WK84zV2sxXs7LtkBoN79R9QIhAP////8A
AAAA//////////+85vqtpxeehPO5ysL8YyVRAgEBBG0wawIBAQQg03iNqbD6lABI
6NasTaH84V9vxrEriGNX1mxbfJSNNKKhRANCAAR5nVbiRBnUUTfPyKxOxHBDC3Zm
mhJavX77ZAZILpD0mqfruUMP26WIONUSZzaMjDiTq2m522jH6Ef5GIt0293A
-----END PRIVATE KEY-----
"""

_Key = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey


def _ec_key() -> _Key:
    return ec.generate_private_key(ec.SECP256R1())


def _rsa_key(key_size: int = 2048) -> _Key:
    return rsa.generate_private_key(public_exponent=65537, key_size=key_size)


def _ca_cert(
    key: _Key,
    name: str = "Test CA",
    issuer: tuple[x509.Certificate, _Key] | None = None,
    ca: bool = True,
    path_length: int | None = None,
    key_cert_sign: bool = True,
    not_before: datetime = NOW - timedelta(days=1),
    not_after: datetime = NOW + timedelta(days=3650),
    minimal: bool = False,
    subject_key_identifier: bool = True,
    extensions: Sequence[x509.ExtensionType] = (),
    critical: bool = False,
) -> x509.Certificate:
    issuer_name, issuer_key = (issuer[0].subject, issuer[1]) if issuer else (None, key)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    usage = dict.fromkeys(
        (
            "digital_signature",
            "content_commitment",
            "key_encipherment",
            "data_encipherment",
            "key_agreement",
            "crl_sign",
            "encipher_only",
            "decipher_only",
        ),
        False,
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name or subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=ca, path_length=path_length if ca else None), critical=True)
    )
    if not minimal:
        builder = builder.add_extension(x509.KeyUsage(key_cert_sign=key_cert_sign, **usage), critical=True)
    if not minimal and subject_key_identifier:
        builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    for extension in extensions:
        builder = builder.add_extension(extension, critical=critical)
    return builder.sign(issuer_key, hashes.SHA256())


def _write_ca(
    directory: Path,
    certs: list[x509.Certificate],
    key: _Key,
    encryption: KeySerializationEncryption | None = None,
) -> tuple[Path, Path]:
    cert_path, key_path = directory / "client-ca.pem", directory / "client-ca.key"
    cert_path.write_bytes(b"".join(cert.public_bytes(Encoding.PEM) for cert in certs))
    key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, encryption or NoEncryption()))
    return cert_path, key_path


def _place_ca(ca_dir: Path, cert: x509.Certificate, key: _Key) -> None:
    ca_dir.mkdir()
    cert_path, key_path = _write_ca(ca_dir, [cert], key)
    cert_path.rename(ca_dir / "ca.pem")
    key_path.rename(ca_dir / "ca.key")


def _write_then_fail(path: Path, content: bytes, mode: int) -> None:
    """`write_ssl_file` that writes the first file for real and fails on every later one."""
    if any(path.parent.glob(".*.tmp")):
        raise PermissionError(13, "Permission denied")
    write_ssl_file(path, content, mode)


def _load_certs(path: Path) -> list[x509.Certificate]:
    return x509.load_pem_x509_certificates(path.read_bytes())


def _tls_handshake(client_context: ssl.SSLContext, server_context: ssl.SSLContext, server_hostname: str) -> None:
    """Run a TLS handshake in memory; raises `ssl.SSLCertVerificationError` if the client rejects the server."""
    client_in, client_out, server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO()
    client = client_context.wrap_bio(client_in, client_out, server_hostname=server_hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    pending = {"client": True, "server": True}
    while any(pending.values()):
        for name, side, side_out, peer_in in (
            ("client", client, client_out, server_in),
            ("server", server, server_out, client_in),
        ):
            try:
                side.do_handshake()
                pending[name] = False
            except ssl.SSLWantReadError:
                pass
            peer_in.write(side_out.read())


@pytest.fixture
def ca_dir(tmp_path: Path) -> Path:
    return tmp_path / "ca"


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "server"


def test_generate_ca_writes_ca_files_with_owner_only_key(ca_dir: Path) -> None:
    generate_ca(ca_dir)

    cert = _load_certs(ca_dir / "ca.pem")[0]
    key = load_pem_private_key((ca_dir / "ca.key").read_bytes(), None)
    basic_constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert basic_constraints.ca is True
    assert basic_constraints.path_length == 0
    assert cert.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign is True
    assert isinstance(cert.public_key(), ec.EllipticCurvePublicKey)
    assert key.public_key() == cert.public_key()
    assert ca_dir.stat().st_mode & 0o777 == 0o700
    assert (ca_dir / "ca.pem").stat().st_mode & 0o777 == 0o644
    assert (ca_dir / "ca.key").stat().st_mode & 0o777 == 0o600


@mock.patch("deepfellow.common.tls.socket.gethostname")
def test_generate_ca_cuts_common_name_for_long_hostname(mock_gethostname: mock.MagicMock, ca_dir: Path) -> None:
    mock_gethostname.return_value = "h" * 60

    generate_ca(ca_dir)

    common_name = _load_certs(ca_dir / "ca.pem")[0].subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert common_name == f"DeepFellow CA ({'h' * 60})"[:64]


def test_generate_ca_raises_when_ca_exists(ca_dir: Path) -> None:
    generate_ca(ca_dir)
    ca_pem = (ca_dir / "ca.pem").read_bytes()

    with pytest.raises(CAExistsError):
        generate_ca(ca_dir)

    assert (ca_dir / "ca.pem").read_bytes() == ca_pem


def test_generate_ca_raises_when_only_ca_key_exists(ca_dir: Path) -> None:
    ca_dir.mkdir()
    (ca_dir / "ca.key").write_bytes(b"client key")

    with pytest.raises(CAExistsError):
        generate_ca(ca_dir)

    assert (ca_dir / "ca.key").read_bytes() == b"client key"


@mock.patch("deepfellow.common.tls.write_ssl_file")
def test_generate_ca_keeps_old_ca_when_write_fails(mock_write_ssl_file: mock.MagicMock, ca_dir: Path) -> None:
    key = _ec_key()
    _place_ca(ca_dir, _ca_cert(key), key)
    old_files = {name: (ca_dir / name).read_bytes() for name in ("ca.pem", "ca.key")}
    mock_write_ssl_file.side_effect = _write_then_fail

    with pytest.raises(CAError, match="Can't write"):
        generate_ca(ca_dir, overwrite=True)

    assert {name: (ca_dir / name).read_bytes() for name in ("ca.pem", "ca.key")} == old_files
    assert sorted(path.name for path in ca_dir.iterdir()) == ["ca.key", "ca.pem"]


@mock.patch("deepfellow.common.tls.Path.stat")
def test_generate_ca_raises_when_ca_dir_unreadable(mock_stat: mock.MagicMock, ca_dir: Path) -> None:
    mock_stat.side_effect = PermissionError(13, "Permission denied")

    with pytest.raises(CAError, match=r"Can't check .*ca\.pem: Permission denied"):
        generate_ca(ca_dir)

    assert mock_stat.call_count == 1


def test_generate_ca_replaces_ca_when_overwrite(ca_dir: Path) -> None:
    generate_ca(ca_dir)
    ca_pem = (ca_dir / "ca.pem").read_bytes()

    generate_ca(ca_dir, overwrite=True)

    assert (ca_dir / "ca.pem").read_bytes() != ca_pem


def test_import_ca_copies_valid_ca_verbatim(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)

    import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert (ca_dir / "ca.pem").read_bytes() == cert_path.read_bytes()
    assert (ca_dir / "ca.key").read_bytes() == key_path.read_bytes()
    assert (ca_dir / "ca.key").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("cert_kwargs", "message"),
    [
        ({"ca": False}, "not a CA"),
        ({"minimal": True}, "keyCertSign"),
        ({"key_cert_sign": False}, "keyCertSign"),
        ({"not_after": NOW - timedelta(days=1)}, "expired or not yet valid"),
        ({"not_before": NOW + timedelta(days=1)}, "expired or not yet valid"),
    ],
)
def test_import_ca_raises_on_invalid_certificate(
    tmp_path: Path, ca_dir: Path, cert_kwargs: dict[str, object], message: str
) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, **cert_kwargs)], key)  # type: ignore[arg-type]

    with pytest.raises(CAError, match=message):
        import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert not ca_dir.exists()


def test_import_ca_raises_when_key_does_not_match(tmp_path: Path, ca_dir: Path) -> None:
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(_ec_key())], _ec_key())

    with pytest.raises(CAError, match="key does not match"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_rsa_key_too_short(tmp_path: Path, ca_dir: Path) -> None:
    key = _rsa_key(1024)
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)

    with pytest.raises(CAError, match=r"not RSA 2048\+ bits"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_issuer_pathlen_forbids_issuing(tmp_path: Path, ca_dir: Path) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root", path_length=0)
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    cert_path, key_path = _write_ca(tmp_path, [intermediate, root], intermediate_key)

    with pytest.raises(CAError, match="pathlen"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


@pytest.mark.parametrize(
    ("chain_builder", "root_not_after", "message"),
    [
        (
            lambda intermediate, root, _unrelated: [intermediate, root],
            NOW - timedelta(days=1),
            "expired or not yet valid",
        ),
        (lambda intermediate, _root, unrelated: [intermediate, unrelated], NOW + timedelta(days=3650), "out of order"),
        (lambda intermediate, root, _unrelated: [root, intermediate], NOW + timedelta(days=3650), "out of order"),
    ],
)
def test_import_ca_raises_on_invalid_chain(
    tmp_path: Path,
    ca_dir: Path,
    chain_builder: Callable[[x509.Certificate, x509.Certificate, x509.Certificate], list[x509.Certificate]],
    root_not_after: datetime,
    message: str,
) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root", not_after=root_not_after)
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    chain = chain_builder(intermediate, root, _ca_cert(_ec_key(), name="Unrelated"))
    cert_path, key_path = _write_ca(tmp_path, chain, intermediate_key)

    with pytest.raises(CAError, match=message):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


@pytest.mark.parametrize(
    ("root_kwargs", "valid"),
    [
        ({"ca": False}, False),
        ({"key_cert_sign": False}, False),
        ({"minimal": True}, True),
    ],
)
def test_import_ca_checks_issuer_is_ca(tmp_path: Path, ca_dir: Path, root_kwargs: dict[str, bool], valid: bool) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root", **root_kwargs)  # type: ignore[arg-type]
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    cert_path, key_path = _write_ca(tmp_path, [intermediate, root], intermediate_key)

    if valid:
        import_ca(cert_path, key_path, ca_dir=ca_dir)
    else:
        with pytest.raises(CAError, match="issuer in the chain is not a CA"):
            import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert (ca_dir / "ca.pem").exists() is valid


def test_import_ca_raises_when_ec_key_has_explicit_curve_parameters(tmp_path: Path, ca_dir: Path) -> None:
    cert_path, key_path = tmp_path / "ca.pem", tmp_path / "ca.key"
    cert_path.write_bytes(EXPLICIT_CURVE_CA_PEM)
    key_path.write_bytes(EXPLICIT_CURVE_KEY_PEM)

    with pytest.raises(CAError, match="named curve"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


@pytest.mark.parametrize("critical", [True, False])
def test_import_ca_rejects_only_critical_unknown_extension(tmp_path: Path, ca_dir: Path, critical: bool) -> None:
    key = _ec_key()
    unknown = x509.UnrecognizedExtension(x509.ObjectIdentifier("1.3.6.1.4.1.99999.1"), b"\x05\x00")
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, extensions=[unknown], critical=critical)], key)

    if critical:
        with pytest.raises(CAError, match="unknown critical extension"):
            import_ca(cert_path, key_path, ca_dir=ca_dir)
    else:
        import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert (ca_dir / "ca.pem").exists() is not critical


def test_import_ca_raises_when_ec_curve_unsupported(tmp_path: Path, ca_dir: Path) -> None:
    key = ec.generate_private_key(ec.SECP256K1())
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)

    with pytest.raises(CAError, match="named curve P-256, P-384 or P-521"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


@pytest.mark.parametrize(
    ("usages", "valid"),
    [
        ([ExtendedKeyUsageOID.CLIENT_AUTH], False),
        ([ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH], True),
        ([ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE], True),
    ],
)
def test_import_ca_checks_extended_key_usage_allows_server_auth(
    tmp_path: Path, ca_dir: Path, usages: list[x509.ObjectIdentifier], valid: bool
) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, extensions=[x509.ExtendedKeyUsage(usages)])], key)

    if valid:
        import_ca(cert_path, key_path, ca_dir=ca_dir)
    else:
        with pytest.raises(CAError, match="extendedKeyUsage without serverAuth"):
            import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert (ca_dir / "ca.pem").exists() is valid


def test_import_ca_raises_when_issuer_key_too_weak(tmp_path: Path, ca_dir: Path) -> None:
    root_key, intermediate_key = _rsa_key(1024), _ec_key()
    root = _ca_cert(root_key, name="Root")
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    cert_path, key_path = _write_ca(tmp_path, [intermediate, root], intermediate_key)

    with pytest.raises(CAError, match=r"not RSA 2048\+ bits"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_extension_malformed(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    malformed = x509.UnrecognizedExtension(ExtensionOID.KEY_USAGE, b"\x05\x00")
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, minimal=True, extensions=[malformed])], key)

    with pytest.raises(CAError, match="malformed"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_chain_signature_unsupported(tmp_path: Path, ca_dir: Path) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root")
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    # ecdsa-with-SHA256 swapped for an unknown OID of the same length
    der = intermediate.public_bytes(Encoding.DER).replace(
        bytes.fromhex("06082a8648ce3d040302"), bytes.fromhex("06082a8648ce3d040309")
    )
    cert_path, key_path = _write_ca(tmp_path, [x509.load_der_x509_certificate(der), root], intermediate_key)

    with pytest.raises(CAError, match="signature of CN=Intermediate can't be checked"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_chain_signature_invalid(tmp_path: Path, ca_dir: Path) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root")
    forged = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, _ec_key()))
    cert_path, key_path = _write_ca(tmp_path, [forged, root], intermediate_key)

    with pytest.raises(CAError, match="signature of CN=Intermediate doesn't verify"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


@mock.patch("deepfellow.common.tls.echo.warning")
def test_import_ca_warns_when_chain_has_name_constraints(
    mock_warning: mock.MagicMock, tmp_path: Path, ca_dir: Path
) -> None:
    key = _ec_key()
    constraints = x509.NameConstraints(permitted_subtrees=[x509.DNSName("corp.example")], excluded_subtrees=None)
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, extensions=[constraints])], key)

    import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert mock_warning.call_count == 1
    assert "name constraints" in mock_warning.call_args.args[0]


def test_import_ca_lists_every_problem(tmp_path: Path, ca_dir: Path) -> None:
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(_ec_key(), ca=False, key_cert_sign=False)], _ec_key())

    with pytest.raises(CAError, match=r"key does not match.*not a CA.*keyCertSign"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_certificate_file_contains_private_key(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)
    cert_path.write_bytes(cert_path.read_bytes() + key_path.read_bytes())

    with pytest.raises(CAError, match="contains a private key"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert not ca_dir.exists()


def test_import_ca_raises_when_password_missing(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key, BestAvailableEncryption(b"secret"))

    with pytest.raises(CAError, match="password is required"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_password_wrong(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key, BestAvailableEncryption(b"secret"))

    with pytest.raises(CAError, match="wrong password"):
        import_ca(cert_path, key_path, password="wrong", ca_dir=ca_dir)


def test_import_ca_keeps_key_encrypted_when_password_given(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key, BestAvailableEncryption(b"secret"))

    import_ca(cert_path, key_path, password="secret", ca_dir=ca_dir)

    assert (ca_dir / "ca.key").read_bytes() == key_path.read_bytes()
    assert b"ENCRYPTED" in (ca_dir / "ca.key").read_bytes()


@mock.patch("deepfellow.common.tls.echo.warning")
def test_import_ca_warns_when_ca_expires_soon(mock_warning: mock.MagicMock, tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key, not_after=NOW + timedelta(days=365))], key)

    import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert mock_warning.call_count == 1
    assert "expires" in mock_warning.call_args.args[0]
    assert (ca_dir / "ca.pem").exists()


@mock.patch("deepfellow.common.tls.echo.warning")
def test_import_ca_warns_when_chain_has_no_root(mock_warning: mock.MagicMock, tmp_path: Path, ca_dir: Path) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root")
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    cert_path, key_path = _write_ca(tmp_path, [intermediate], intermediate_key)

    import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert mock_warning.call_count == 1
    assert "root CA" in mock_warning.call_args.args[0]
    assert (ca_dir / "ca.pem").exists()


def test_import_ca_raises_when_certificate_not_pem(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)
    cert_path.write_bytes(b"not a certificate")

    with pytest.raises(CAError, match="not a PEM certificate"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_password_given_for_unencrypted_key(tmp_path: Path, ca_dir: Path) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)

    with pytest.raises(CAError, match="not encrypted"):
        import_ca(cert_path, key_path, password="secret", ca_dir=ca_dir)


@pytest.mark.parametrize(
    ("unsupported_key", "key_type"),
    [
        (ed25519.Ed25519PrivateKey.generate(), "Ed25519PrivateKey"),
        (x25519.X25519PrivateKey.generate(), "X25519PrivateKey"),
    ],
)
def test_import_ca_raises_when_key_type_unsupported(
    tmp_path: Path, ca_dir: Path, unsupported_key: ed25519.Ed25519PrivateKey | x25519.X25519PrivateKey, key_type: str
) -> None:
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)
    key_path.write_bytes(unsupported_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))

    with pytest.raises(CAError, match=f"{key_type} is not supported"):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_import_ca_raises_when_file_missing(tmp_path: Path, ca_dir: Path) -> None:
    with pytest.raises(CAError, match="Can't read"):
        import_ca(tmp_path / "missing.pem", tmp_path / "missing.key", ca_dir=ca_dir)


@mock.patch("deepfellow.common.tls.echo.warning")
def test_import_ca_warns_when_root_expires_before_ca(
    mock_warning: mock.MagicMock, tmp_path: Path, ca_dir: Path
) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root", not_after=NOW + timedelta(days=365))
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    cert_path, key_path = _write_ca(tmp_path, [intermediate, root], intermediate_key)

    import_ca(cert_path, key_path, ca_dir=ca_dir)

    assert mock_warning.call_count == 1
    assert f"expires on {root.not_valid_after_utc:%Y-%m-%d}" in mock_warning.call_args.args[0]


def test_import_ca_raises_when_ca_exists(tmp_path: Path, ca_dir: Path) -> None:
    generate_ca(ca_dir)
    key = _ec_key()
    cert_path, key_path = _write_ca(tmp_path, [_ca_cert(key)], key)

    with pytest.raises(CAExistsError):
        import_ca(cert_path, key_path, ca_dir=ca_dir)


def test_issue_certificate_signs_with_ca_and_sets_san(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)

    issue_certificate(out_dir, ["server", "localhost", "127.0.0.1", "10.0.0.5"], ca_dir=ca_dir)

    ca = _load_certs(ca_dir / "ca.pem")[0]
    cert = _load_certs(out_dir / "cert.pem")[0]
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    cert.verify_directly_issued_by(ca)
    assert san.get_values_for_type(x509.DNSName) == ["server", "localhost"]
    assert san.get_values_for_type(x509.IPAddress) == [ip_address("127.0.0.1"), ip_address("10.0.0.5")]
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    assert list(cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [
        ExtendedKeyUsageOID.SERVER_AUTH
    ]
    assert cert.not_valid_before_utc <= datetime.now(timezone.utc) - timedelta(minutes=4)
    usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    assert (usage.digital_signature, usage.key_cert_sign, usage.key_encipherment) == (True, False, False)
    assert {ext.oid: ext.critical for ext in cert.extensions} == {
        ExtensionOID.SUBJECT_KEY_IDENTIFIER: False,
        ExtensionOID.BASIC_CONSTRAINTS: True,
        ExtensionOID.KEY_USAGE: True,
        ExtensionOID.EXTENDED_KEY_USAGE: False,
        ExtensionOID.SUBJECT_ALTERNATIVE_NAME: False,
        ExtensionOID.AUTHORITY_KEY_IDENTIFIER: False,
    }
    assert abs(cert.not_valid_after_utc - datetime.now(timezone.utc) - timedelta(days=730)) < timedelta(minutes=1)
    assert (out_dir / "ca.pem").read_bytes() == (ca_dir / "ca.pem").read_bytes()
    assert (out_dir / "key.pem").stat().st_mode & 0o777 == 0o600
    assert (
        cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
        == ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    )


def test_issue_certificate_cuts_long_common_name(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)
    name = f"{'a' * 60}.example.com"

    issue_certificate(out_dir, [name], ca_dir=ca_dir)

    cert = _load_certs(out_dir / "cert.pem")[0]
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == name[:64]
    assert san.get_values_for_type(x509.DNSName) == [name]


@pytest.mark.parametrize("names", [[], "server"])
def test_issue_certificate_raises_when_names_not_a_list_of_names(
    ca_dir: Path, out_dir: Path, names: Sequence[str]
) -> None:
    generate_ca(ca_dir)

    with pytest.raises(ValueError, match="list of at least one name"):
        issue_certificate(out_dir, names, ca_dir=ca_dir)


def test_issue_certificate_caps_lifetime_at_ca_expiry(tmp_path: Path, ca_dir: Path, out_dir: Path) -> None:
    key = _ec_key()
    ca = _ca_cert(key, not_after=NOW + timedelta(days=365))
    import_ca(*_write_ca(tmp_path, [ca], key), ca_dir=ca_dir)

    issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    assert _load_certs(out_dir / "cert.pem")[0].not_valid_after_utc == ca.not_valid_after_utc


def test_issue_certificate_raises_when_ca_expired(ca_dir: Path, out_dir: Path) -> None:
    key = _ec_key()
    _place_ca(ca_dir, _ca_cert(key, not_after=NOW - timedelta(days=1)), key)

    with pytest.raises(CAError, match="expired or not yet valid"):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)


def test_issue_certificate_caps_lifetime_at_root_expiry(tmp_path: Path, ca_dir: Path, out_dir: Path) -> None:
    root_key, intermediate_key = _ec_key(), _ec_key()
    root = _ca_cert(root_key, name="Root", not_after=NOW + timedelta(days=365))
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key))
    _place_ca(ca_dir, intermediate, intermediate_key)
    (ca_dir / "ca.pem").write_bytes(b"".join(cert.public_bytes(Encoding.PEM) for cert in (intermediate, root)))

    issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    assert _load_certs(out_dir / "cert.pem")[0].not_valid_after_utc == root.not_valid_after_utc


def test_issue_certificate_raises_when_key_does_not_match_ca(ca_dir: Path, out_dir: Path) -> None:
    _place_ca(ca_dir, _ca_cert(_ec_key()), _ec_key())

    with pytest.raises(CAError, match="key does not match"):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    assert not out_dir.exists()


def test_issue_certificate_accepts_punycode_and_docker_names(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)

    issue_certificate(out_dir, ["xn--hst-kna.local", "df_server-1", "::1"], ca_dir=ca_dir)

    san = _load_certs(out_dir / "cert.pem")[0].extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["xn--hst-kna.local", "df_server-1"]
    assert san.get_values_for_type(x509.IPAddress) == [ip_address("::1")]


@pytest.mark.parametrize(
    "name", ["", "hôst.local", "straße.de", "host:8080", "[::1]", "https://x.y", "a..b", "-x", f"{'a' * 64}.com"]
)
def test_issue_certificate_raises_on_invalid_name(ca_dir: Path, out_dir: Path, name: str) -> None:
    generate_ca(ca_dir)

    with pytest.raises(CAError, match="Invalid certificate names"):
        issue_certificate(out_dir, ["server", name], ca_dir=ca_dir)

    assert not out_dir.exists()


def test_issue_certificate_raises_when_out_dir_is_a_file(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)
    out_dir.write_bytes(b"not a directory")

    with pytest.raises(CAError, match="Can't write"):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)


def test_issue_certificate_lists_replaced_files_when_rename_fails(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)
    (out_dir / "cert.pem").mkdir(parents=True)

    with pytest.raises(CAError, match=r"Can't write .*cert\.pem: Is a directory\. Already replaced: key\.pem\."):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    assert sorted(path.name for path in out_dir.iterdir()) == ["cert.pem", "key.pem"]


@mock.patch("deepfellow.common.tls.write_ssl_file")
def test_issue_certificate_keeps_old_files_when_write_fails(
    mock_write_ssl_file: mock.MagicMock, ca_dir: Path, out_dir: Path
) -> None:
    key = _ec_key()
    _place_ca(ca_dir, _ca_cert(key), key)
    out_dir.mkdir()
    for name in ("key.pem", "cert.pem", "ca.pem"):
        (out_dir / name).write_bytes(f"old {name}".encode())
    mock_write_ssl_file.side_effect = _write_then_fail

    with pytest.raises(CAError, match=f"Can't write {re.escape(str(out_dir / 'cert.pem'))}: Permission denied"):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    assert mock_write_ssl_file.call_count == 2

    assert {path.name: path.read_bytes() for path in out_dir.iterdir()} == {
        name: f"old {name}".encode() for name in ("key.pem", "cert.pem", "ca.pem")
    }


@pytest.mark.parametrize("key_factory", [_ec_key, _rsa_key])
def test_issue_certificate_signs_with_rsa_and_ec_ca_keys(
    tmp_path: Path, ca_dir: Path, out_dir: Path, key_factory: Callable[[], _Key]
) -> None:
    key = key_factory()
    ca = _ca_cert(key)
    import_ca(*_write_ca(tmp_path, [ca], key), ca_dir=ca_dir)

    issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    _load_certs(out_dir / "cert.pem")[0].verify_directly_issued_by(ca)


def test_issue_certificate_appends_chain_for_intermediate_ca(tmp_path: Path, ca_dir: Path, out_dir: Path) -> None:
    root_key, intermediate_key = _rsa_key(), _rsa_key()
    root = _ca_cert(root_key, name="Root", path_length=1)
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key), path_length=0)
    cert_path, key_path = _write_ca(tmp_path, [intermediate, root], intermediate_key, BestAvailableEncryption(b"pw"))
    import_ca(cert_path, key_path, password="pw", ca_dir=ca_dir)

    issue_certificate(out_dir, ["server"], password="pw", ca_dir=ca_dir)

    leaf, *chain = _load_certs(out_dir / "cert.pem")
    leaf.verify_directly_issued_by(intermediate)
    assert chain == [intermediate, root]


def test_issue_certificate_keeps_earlier_certificates(ca_dir: Path, tmp_path: Path) -> None:
    generate_ca(ca_dir)
    issue_certificate(tmp_path / "server", ["server"], ca_dir=ca_dir)
    server_cert = (tmp_path / "server" / "cert.pem").read_bytes()

    issue_certificate(tmp_path / "keycloak", ["keycloak"], ca_dir=ca_dir)

    ca = _load_certs(ca_dir / "ca.pem")[0]
    _load_certs(tmp_path / "keycloak" / "cert.pem")[0].verify_directly_issued_by(ca)
    assert (tmp_path / "server" / "cert.pem").read_bytes() == server_cert


def test_issue_certificate_signs_with_ca_without_subject_key_identifier(ca_dir: Path, out_dir: Path) -> None:
    key = _ec_key()
    ca = _ca_cert(key, subject_key_identifier=False)
    _place_ca(ca_dir, ca, key)

    issue_certificate(out_dir, ["server"], ca_dir=ca_dir)

    cert = _load_certs(out_dir / "cert.pem")[0]
    cert.verify_directly_issued_by(ca)
    assert (
        cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
        == x509.SubjectKeyIdentifier.from_public_key(key.public_key()).digest
    )


def test_issue_certificate_raises_when_no_ca(ca_dir: Path, out_dir: Path) -> None:
    with pytest.raises(CAError, match="Can't read"):
        issue_certificate(out_dir, ["server"], ca_dir=ca_dir)


@pytest.mark.parametrize(
    ("hostname", "expected"),
    [
        ("box", ["server", "localhost", "127.0.0.1", "::1", "box"]),
        ("localhost", ["server", "localhost", "127.0.0.1", "::1"]),
    ],
)
@mock.patch("deepfellow.common.tls.socket.gethostname")
def test_local_names_returns_unique_local_names(
    mock_gethostname: mock.MagicMock, hostname: str, expected: list[str]
) -> None:
    mock_gethostname.return_value = hostname

    result = local_names("server")

    assert result == expected


@mock.patch("deepfellow.common.tls.socket.gethostname")
def test_local_names_uses_given_host(mock_gethostname: mock.MagicMock) -> None:
    result = local_names("server", "df.example.com")

    assert result == ["server", "localhost", "127.0.0.1", "::1", "df.example.com"]
    assert mock_gethostname.call_count == 0


def test_write_ca_bundle_contains_public_cas_and_generated_ca(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    bundle = (out_dir / CA_BUNDLE_FILENAME).read_bytes()
    assert bundle == certifi.contents().encode() + (ca_dir / "ca.pem").read_bytes()


def test_write_ca_bundle_keeps_client_chain_order(tmp_path: Path, ca_dir: Path, out_dir: Path) -> None:
    root_key, intermediate_key = _rsa_key(), _rsa_key()
    root = _ca_cert(root_key, name="Root", path_length=1)
    intermediate = _ca_cert(intermediate_key, name="Intermediate", issuer=(root, root_key), path_length=0)
    import_ca(*_write_ca(tmp_path, [intermediate, root], intermediate_key), ca_dir=ca_dir)

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    chain_pem = b"".join(cert.public_bytes(Encoding.PEM) for cert in (intermediate, root))
    assert (out_dir / CA_BUNDLE_FILENAME).read_bytes().endswith(chain_pem)


@pytest.mark.parametrize("ca_dir_exists", [False, True])
def test_write_ca_bundle_writes_public_cas_only_when_no_ca(ca_dir: Path, out_dir: Path, ca_dir_exists: bool) -> None:
    if ca_dir_exists:
        ca_dir.mkdir()
        (ca_dir / "ca.key").write_bytes(b"orphaned key")

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    bundle_path = out_dir / CA_BUNDLE_FILENAME
    assert bundle_path.read_bytes() == certifi.contents().encode()
    assert bundle_path.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize("out_dir_exists", [False, True])
def test_write_ca_bundle_makes_directory_readable_by_containers_despite_umask(
    ca_dir: Path, out_dir: Path, out_dir_exists: bool
) -> None:
    if out_dir_exists:
        out_dir.mkdir(mode=0o700)
    old_umask = os.umask(0o077)

    try:
        write_ca_bundle(out_dir, ca_dir=ca_dir)
    finally:
        os.umask(old_umask)

    assert out_dir.stat().st_mode & 0o777 == 0o755
    assert (out_dir / CA_BUNDLE_FILENAME).stat().st_mode & 0o777 == 0o644


@mock.patch("deepfellow.common.tls.certifi.contents")
def test_write_ca_bundle_separates_public_cas_without_trailing_newline(
    mock_contents: mock.MagicMock, ca_dir: Path, out_dir: Path
) -> None:
    mock_contents.return_value = "-----END CERTIFICATE-----"
    generate_ca(ca_dir)

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    bundle = (out_dir / CA_BUNDLE_FILENAME).read_bytes()
    assert bundle == b"-----END CERTIFICATE-----\n" + (ca_dir / "ca.pem").read_bytes()


def test_write_ca_bundle_never_contains_private_key(ca_dir: Path, out_dir: Path) -> None:
    generate_ca(ca_dir)

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert b"PRIVATE KEY" not in (out_dir / CA_BUNDLE_FILENAME).read_bytes()
    assert [path.name for path in out_dir.iterdir()] == [CA_BUNDLE_FILENAME]


def test_write_ca_bundle_replaces_existing_bundle(ca_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir()
    (out_dir / CA_BUNDLE_FILENAME).write_bytes(b"old bundle")
    generate_ca(ca_dir)

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert (out_dir / CA_BUNDLE_FILENAME).read_bytes().endswith((ca_dir / "ca.pem").read_bytes())


@pytest.mark.parametrize("ca_pem", [b"not a certificate", b""])
def test_write_ca_bundle_raises_ca_error_for_malformed_ca_pem(ca_dir: Path, out_dir: Path, ca_pem: bytes) -> None:
    ca_dir.mkdir()
    (ca_dir / "ca.pem").write_bytes(ca_pem)
    out_dir.mkdir()
    (out_dir / CA_BUNDLE_FILENAME).write_bytes(b"old bundle")

    with pytest.raises(CAError, match="is not a PEM certificate"):
        write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert (out_dir / CA_BUNDLE_FILENAME).read_bytes() == b"old bundle"


@pytest.mark.parametrize("key_first", [True, False])
def test_write_ca_bundle_rejects_ca_pem_with_private_key(ca_dir: Path, out_dir: Path, key_first: bool) -> None:
    generate_ca(ca_dir)
    cert_pem, key_pem = (ca_dir / "ca.pem").read_bytes(), (ca_dir / "ca.key").read_bytes()
    (ca_dir / "ca.pem").write_bytes(key_pem + cert_pem if key_first else cert_pem + key_pem)

    with pytest.raises(CAError, match="contains a private key"):
        write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert not (out_dir / CA_BUNDLE_FILENAME).exists()


@mock.patch("deepfellow.common.tls.Path.read_bytes")
def test_write_ca_bundle_raises_ca_error_when_ca_pem_unreadable(
    mock_read_bytes: mock.MagicMock, ca_dir: Path, out_dir: Path
) -> None:
    mock_read_bytes.side_effect = PermissionError(13, "Permission denied")

    with pytest.raises(CAError, match=f"Can't read {re.escape(str(ca_dir / 'ca.pem'))}: Permission denied"):
        write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert not out_dir.exists()


@mock.patch("deepfellow.common.tls.write_ssl_file")
def test_write_ca_bundle_keeps_previous_bundle_when_write_fails(
    mock_write_ssl_file: mock.MagicMock, ca_dir: Path, out_dir: Path
) -> None:
    key = _ec_key()
    _place_ca(ca_dir, _ca_cert(key), key)
    out_dir.mkdir()
    (out_dir / CA_BUNDLE_FILENAME).write_bytes(b"old bundle")
    mock_write_ssl_file.side_effect = PermissionError(13, "Permission denied")

    with pytest.raises(CAError, match=f"Can't write {re.escape(str(out_dir / CA_BUNDLE_FILENAME))}"):
        write_ca_bundle(out_dir, ca_dir=ca_dir)

    assert {path.name: path.read_bytes() for path in out_dir.iterdir()} == {CA_BUNDLE_FILENAME: b"old bundle"}


def test_write_ca_bundle_lets_tls_client_trust_ca_issued_and_public_certificates(
    tmp_path: Path, ca_dir: Path, out_dir: Path
) -> None:
    generate_ca(ca_dir)
    issue_certificate(tmp_path / "server", ["server"], ca_dir=ca_dir)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(tmp_path / "server" / "cert.pem", tmp_path / "server" / "key.pem")

    write_ca_bundle(out_dir, ca_dir=ca_dir)

    client_context = ssl.create_default_context(cafile=out_dir / CA_BUNDLE_FILENAME)
    assert client_context.cert_store_stats()["x509_ca"] == certifi.contents().count("BEGIN CERTIFICATE") + 1
    _tls_handshake(client_context, server_context, "server")
    with pytest.raises(ssl.SSLCertVerificationError):
        _tls_handshake(ssl.create_default_context(cafile=certifi.where()), server_context, "server")
