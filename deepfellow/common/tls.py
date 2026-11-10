# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Internal CA: generate or import a CA and issue component certificates signed by it."""

import os
import re
import socket
from collections.abc import Sequence
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from itertools import pairwise
from pathlib import Path
from typing import TypeVar

import certifi
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from deepfellow.common.defaults import CA_BUNDLE_FILENAME, DF_DEEPFELLOW_DIRECTORY
from deepfellow.common.echo import echo

CA_DIR = DF_DEEPFELLOW_DIRECTORY / "ca"
CA_VALIDITY = timedelta(days=3650)
CERT_VALIDITY = timedelta(days=730)
CLOCK_SKEW = timedelta(minutes=5)
MIN_RSA_KEY_SIZE = 2048
CN_MAX_LENGTH = 64
# Files a component keeps in its `ssl` dir, with their host permissions: the key is owner-only
SSL_FILE_MODES = {"key.pem": 0o600, "cert.pem": 0o644}

_T = TypeVar("_T", bound=x509.ExtensionType)

# Ed25519, Ed448 and DSA CA keys are rejected: browsers don't accept them in TLS certificate chains
_SigningKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey
# Curves browsers accept in TLS certificate chains
_EC_CURVES = (ec.SECP256R1, ec.SECP384R1, ec.SECP521R1)
# An ASCII host name: dot-separated labels of letters, digits, `-` and `_` (Docker service names may have it)
_HOST_NAME = re.compile(
    r"(?=.{1,253}$)([A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?\.)*[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?"
)
_KEY_USAGES = (
    "digital_signature",
    "content_commitment",
    "key_encipherment",
    "data_encipherment",
    "key_agreement",
    "key_cert_sign",
    "crl_sign",
    "encipher_only",
    "decipher_only",
)


class CAError(Exception):
    """The CA is missing, unreadable or cannot be used to issue certificates."""


class CAExistsError(CAError):
    """A CA already exists and overwriting it was not requested."""


def generate_ca(ca_dir: Path = CA_DIR, overwrite: bool = False) -> None:
    """Generate an ECDSA P-256 CA and save it as `ca.pem` and `ca.key` in `ca_dir`.

    Args:
        ca_dir: Directory to save the CA in.
        overwrite: Replace an existing CA. Every certificate issued by the old CA stops being trusted.

    Raises:
        CAExistsError: If `ca_dir` already holds a CA and `overwrite` is false.
        CAError: If `ca_dir` can't be checked or the CA files can't be written.
    """
    _check_overwrite(ca_dir, overwrite)
    key = ec.generate_private_key(ec.SECP256R1())
    name = _name(f"DeepFellow CA ({socket.gethostname()})")
    cert = _certificate(
        name,
        name,
        key.public_key(),
        key,
        _now() + CA_VALIDITY,
        x509.BasicConstraints(ca=True, path_length=0),
        _key_usage(key_cert_sign=True, crl_sign=True),
    )
    _save_ca(ca_dir, cert.public_bytes(Encoding.PEM), _private_pem(key))


def import_ca(
    cert_path: Path, key_path: Path, password: str | None = None, ca_dir: Path = CA_DIR, overwrite: bool = False
) -> None:
    """Validate a client CA and copy its files unchanged to `ca_dir`.

    Args:
        cert_path: PEM file with the CA certificate, optionally followed by its issuers.
        key_path: PEM file with the CA private key, optionally encrypted.
        password: Password of an encrypted key.
        ca_dir: Directory to save the CA in.
        overwrite: Replace an existing CA. Every certificate issued by the old CA stops being trusted.

    Raises:
        CAExistsError: If `ca_dir` already holds a CA and `overwrite` is false.
        CAError: If the files can't be read, the CA is invalid (the message lists every problem), or `ca_dir`
            can't be checked or written.
    """
    _check_overwrite(ca_dir, overwrite)
    cert_pem, key_pem = _read(cert_path), _read(key_path)
    if b"PRIVATE KEY" in cert_pem:
        raise CAError("The CA certificate file contains a private key; give the key in a separate file.")
    chain, key = _parse(cert_pem, key_pem, password)
    if problems := _validate(chain, key):
        raise CAError(f"Invalid CA: {'; '.join(problems)}.")
    if (expiry := _expiry(chain)) < _now() + CERT_VALIDITY:
        echo.warning(f"The CA chain expires on {expiry:%Y-%m-%d}; certificates it issues end then too.")
    if any(_extension(cert, x509.NameConstraints) for cert in chain):
        echo.warning("The CA chain has name constraints; clients reject certificates for names outside them.")
    if chain[-1].issuer != chain[-1].subject:
        echo.warning("The CA file doesn't end with a root CA; add the root after the CA, or clients may reject it.")
    _save_ca(ca_dir, cert_pem, key_pem)


def issue_certificate(out_dir: Path, names: Sequence[str], password: str | None = None, ca_dir: Path = CA_DIR) -> None:
    """Issue a CA-signed certificate for a component and save it to `out_dir`.

    Writes `key.pem` (new ECDSA P-256 key), `cert.pem` (the certificate followed by the CA chain) and `ca.pem`
    (the CA chain to trust), so `out_dir` holds everything the component needs.

    Args:
        out_dir: Directory to save the files in.
        names: ASCII host names (punycode for internationalized ones) and IP addresses the component is reached by;
            the first one is also the CN.
        password: Password of an encrypted CA key.
        ca_dir: Directory with the CA.

    Raises:
        ValueError: If `names` is empty or a single string.
        CAError: If a name is invalid, the CA can't be read or is no longer valid, or the files can't be written.
    """
    if not names or isinstance(names, str):
        raise ValueError("A certificate needs a list of at least one name.")
    if invalid := [name for name in names if not is_ip_address(name) and not _HOST_NAME.fullmatch(name)]:
        raise CAError(
            f"Invalid certificate names {invalid}: use IP addresses or ASCII host names (punycode for non-ASCII ones)."
        )
    chain, ca_key = _parse(_read(ca_dir / "ca.pem"), _read(ca_dir / "ca.key"), password)
    if problems := _validate(chain, ca_key):
        raise CAError(f"The CA in {ca_dir} can't issue certificates: {'; '.join(problems)}.")
    ca_ski = _extension(chain[0], x509.SubjectKeyIdentifier)
    key = ec.generate_private_key(ec.SECP256R1())
    cert = _certificate(
        _name(names[0]),
        chain[0].subject,
        key.public_key(),
        ca_key,
        min(_now() + CERT_VALIDITY, _expiry(chain)),
        x509.BasicConstraints(ca=False, path_length=None),
        _key_usage(digital_signature=True),
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
        x509.SubjectAlternativeName(
            [x509.IPAddress(ip_address(name)) if is_ip_address(name) else x509.DNSName(name) for name in names]
        ),
        x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski)
        if ca_ski
        else x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
    )
    chain_pem = b"".join(ca.public_bytes(Encoding.PEM) for ca in chain)
    _write_files(
        out_dir,
        {
            "key.pem": (_private_pem(key), SSL_FILE_MODES["key.pem"]),
            "cert.pem": (cert.public_bytes(Encoding.PEM) + chain_pem, SSL_FILE_MODES["cert.pem"]),
            "ca.pem": (chain_pem, SSL_FILE_MODES["cert.pem"]),
        },
    )


def write_ca_bundle(out_dir: Path, ca_dir: Path = CA_DIR) -> None:
    """Write `ca-bundle.pem` to `out_dir`: the public CAs followed by the CA chain from `ca_dir`, if there is one.

    Clients that load only the file `SSL_CERT_FILE` points at (httpx, LiteLLM) then trust both public sites
    and components with certificates from the CA. Without a CA (no `ca.pem`) the bundle holds only the public CAs.

    Args:
        out_dir: Directory to save `ca-bundle.pem` in.
        ca_dir: Directory with the CA; only its certificate is read, never its key.

    Raises:
        CAError: If `ca.pem` can't be read, holds no PEM certificate (e.g. is empty) or holds a private key,
            or the bundle can't be written.
    """
    ca_pem = ca_dir / "ca.pem"
    try:
        chain_pem = ca_pem.read_bytes()
    except FileNotFoundError:
        echo.debug(f"No CA in {ca_dir}; the CA trust bundle holds only public CAs.")
        chain_pem = None
    except OSError as exc:
        raise CAError(f"Can't read {ca_pem}: {exc.strerror}.") from exc
    if chain_pem is not None:
        # The bundle is world-readable and mounted into containers; the PEM parser would skip a key block
        if b"PRIVATE KEY" in chain_pem:
            raise CAError(f"The CA certificate {ca_pem} contains a private key; keep the key in ca.key only.")
        try:
            x509.load_pem_x509_certificates(chain_pem)
        except ValueError as exc:
            raise CAError(f"The CA certificate {ca_pem} is not a PEM certificate or is malformed.") from exc
    public_pem = certifi.contents().encode()
    if not public_pem.endswith(b"\n"):
        public_pem += b"\n"
    # Containers may run as a non-root user, so the directory must not keep a restrictive umask's mode
    _write_files(
        out_dir,
        {CA_BUNDLE_FILENAME: (public_pem + (chain_pem or b""), SSL_FILE_MODES["cert.pem"])},
        dir_mode=0o755,
    )


def local_names(service: str, host: str | None = None) -> list[str]:
    """Names a service on this host is reached by: its Docker service name, loopback names and `host`.

    Args:
        service: Docker Compose service name.
        host: Host name or address the service is published under; defaults to this machine's host name.
    """
    return list(dict.fromkeys([service, "localhost", "127.0.0.1", "::1", host or socket.gethostname()]))


def is_ip_address(value: str) -> bool:
    """Whether `value` is an IPv4 or IPv6 address rather than a host name."""
    try:
        ip_address(value)
    except ValueError:
        return False
    return True


def write_ssl_file(path: Path, content: bytes, mode: int) -> None:
    """Write `content` to `path` with permissions `mode`."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    # os.open applies `mode` only to a new file, so an existing one gets it here, before the write
    os.fchmod(fd, mode)
    with os.fdopen(fd, "wb") as file:
        file.write(content)


def _validate(chain: list[x509.Certificate], key: _SigningKey) -> list[str]:
    """Problems that make `chain[0]` with `key` unusable for issuing certificates."""
    ca, now = chain[0], _now()
    constraints, usage = _extension(ca, x509.BasicConstraints), _extension(ca, x509.KeyUsage)
    checks = {
        "the key does not match the certificate": key.public_key() == ca.public_key(),
        f"a key in the chain is not RSA {MIN_RSA_KEY_SIZE}+ bits or EC on named curve P-256, P-384 or P-521": all(
            map(_has_strong_key, chain)
        ),
        "a certificate in the chain has an unknown critical extension": not any(
            ext.critical and isinstance(ext.value, x509.UnrecognizedExtension)
            for cert in chain
            for ext in cert.extensions
        ),
        "the certificate is not a CA (basicConstraints CA:TRUE)": bool(constraints and constraints.ca),
        "the certificate may not sign certificates (keyUsage keyCertSign)": bool(usage and usage.key_cert_sign),
        "a certificate in the chain is expired or not yet valid": all(
            cert.not_valid_before_utc <= now < cert.not_valid_after_utc for cert in chain
        ),
        "a certificate in the chain limits extendedKeyUsage without serverAuth": all(
            (eku := _extension(cert, x509.ExtendedKeyUsage)) is None
            or {ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE} & set(eku)
            for cert in chain
        ),
        "an issuer in the chain is not a CA allowed to sign certificates": all(map(_is_issuer, chain[1:])),
        "an issuer's pathlen forbids this CA from issuing": all(
            (bc := _extension(cert, x509.BasicConstraints)) is None or bc.path_length is None or bc.path_length >= i
            for i, cert in enumerate(chain)
        ),
    }
    problems = [problem for problem, ok in checks.items() if not ok]
    if chain_problem := _chain_problem(chain):
        problems.append(chain_problem)
    return problems


def _has_strong_key(cert: x509.Certificate) -> bool:
    """Whether browsers accept the key of `cert` in a TLS chain: RSA of `MIN_RSA_KEY_SIZE`+ bits or EC on `_EC_CURVES`.

    An EC key with explicit curve parameters loads as its named curve, so it's caught by re-encoding the key
    (always with the curve's name) and looking for it in the certificate.
    """
    public_key = cert.public_key()
    if isinstance(public_key, rsa.RSAPublicKey):
        return public_key.key_size >= MIN_RSA_KEY_SIZE
    return (
        isinstance(public_key, ec.EllipticCurvePublicKey)
        and isinstance(public_key.curve, _EC_CURVES)
        and public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) in cert.tbs_certificate_bytes
    )


def _is_issuer(cert: x509.Certificate) -> bool:
    """Whether `cert` is a CA (basicConstraints CA:TRUE) whose keyUsage, if any, allows keyCertSign."""
    constraints, usage = _extension(cert, x509.BasicConstraints), _extension(cert, x509.KeyUsage)
    return bool(constraints and constraints.ca) and (usage is None or usage.key_cert_sign)


def _expiry(chain: list[x509.Certificate]) -> datetime:
    """When the first certificate in `chain` expires; a certificate can't outlive any of its issuers."""
    return min(cert.not_valid_after_utc for cert in chain)


def _chain_problem(chain: list[x509.Certificate]) -> str | None:
    """Why a certificate in `chain` isn't verifiably issued by the one after it, or `None` if every one is."""
    for cert, issuer in pairwise(chain):
        if cert.issuer != issuer.subject:
            return "the chain is out of order or has a certificate that didn't issue the one before it"
        try:
            cert.verify_directly_issued_by(issuer)
        except InvalidSignature:
            return f"the signature of {cert.subject.rfc4514_string()} doesn't verify"
        except (ValueError, TypeError) as exc:
            return f"the signature of {cert.subject.rfc4514_string()} can't be checked ({exc})"
    return None


def _parse(cert_pem: bytes, key_pem: bytes, password: str | None) -> tuple[list[x509.Certificate], _SigningKey]:
    """Load the CA chain and key, turning every failure into a `CAError`."""
    try:
        chain = x509.load_pem_x509_certificates(cert_pem)
        for cert in chain:
            _ = cert.extensions  # cryptography parses extensions lazily; a malformed one fails here, not later
    except ValueError as exc:
        raise CAError("The CA certificate is not a PEM certificate or is malformed.") from exc
    try:
        key = load_pem_private_key(key_pem, password.encode() if password is not None else None)
    except TypeError as exc:
        raise CAError("The CA key is encrypted; a password is required." if password is None else str(exc)) from exc
    except ValueError as exc:
        raise CAError("The CA key can't be loaded: wrong password or not a PEM key.") from exc
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise CAError(f"The CA key type {type(key).__name__} is not supported; use an RSA or EC key.")
    return chain, key


def _certificate(
    subject: x509.Name,
    issuer: x509.Name,
    public_key: ec.EllipticCurvePublicKey,
    signing_key: _SigningKey,
    not_after: datetime,
    *extensions: x509.ExtensionType,
) -> x509.Certificate:
    """Build and sign a certificate valid from a few minutes ago (clock skew) until `not_after`."""
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - CLOCK_SKEW)
        .not_valid_after(not_after)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
    )
    for extension in extensions:
        builder = builder.add_extension(
            extension, critical=isinstance(extension, (x509.BasicConstraints, x509.KeyUsage))
        )
    return builder.sign(signing_key, hashes.SHA256())


def _check_overwrite(ca_dir: Path, overwrite: bool) -> None:
    """Raise `CAExistsError` if `ca_dir` already holds a CA and `overwrite` is false, `CAError` if it can't tell."""
    if overwrite:
        return
    for path in (ca_dir / "ca.pem", ca_dir / "ca.key"):
        try:
            path.stat()
        except FileNotFoundError:
            continue
        except OSError as exc:  # Path.exists() would hide it: raise on 3.10-3.13, return False on 3.14+
            raise CAError(f"Can't check {path}: {exc.strerror}.") from exc
        raise CAExistsError(f"A CA already exists in {ca_dir}.")


def _save_ca(ca_dir: Path, cert_pem: bytes, key_pem: bytes) -> None:
    """Write the CA files to an owner-only `ca_dir`."""
    _write_files(
        ca_dir,
        {"ca.pem": (cert_pem, SSL_FILE_MODES["cert.pem"]), "ca.key": (key_pem, SSL_FILE_MODES["key.pem"])},
        dir_mode=0o700,
    )


def _write_files(directory: Path, files: dict[str, tuple[bytes, int]], dir_mode: int | None = None) -> None:
    """Write `files` ({name: (content, mode)}) to `directory`, replacing them only once every one is written.

    Raises:
        CAError: If a file can't be written. A failure before the final renames leaves the files in
            `directory` as they were; one during them leaves a mix of old and new files, which the message
            lists. A crash between the renames can leave such a mix too.
    """
    temps = {name: directory / f".{name}.tmp" for name in files}
    replaced: list[str] = []
    current = directory
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if dir_mode is not None:
            directory.chmod(dir_mode)
        for name, (content, mode) in files.items():
            current = directory / name
            write_ssl_file(temps[name], content, mode)
        for name, temp in temps.items():
            current = directory / name
            temp.replace(current)
            replaced.append(name)
    except OSError as exc:
        for temp in temps.values():
            with suppress(OSError):
                temp.unlink()
        note = f" Already replaced: {', '.join(replaced)}." if replaced else ""
        raise CAError(f"Can't write {current}: {exc.strerror}.{note}") from exc


def _read(path: Path) -> bytes:
    """Read `path`, turning an OS error into a `CAError`."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CAError(f"Can't read {path}: {exc.strerror}.") from exc


def _extension(cert: x509.Certificate, extension_type: type[_T]) -> _T | None:
    """The value of the certificate's extension of `extension_type`, or `None` if it has none."""
    try:
        return cert.extensions.get_extension_for_class(extension_type).value
    except x509.ExtensionNotFound:
        return None


def _key_usage(**enabled: bool) -> x509.KeyUsage:
    """`KeyUsage` with only the `enabled` usages set."""
    return x509.KeyUsage(**dict.fromkeys(_KEY_USAGES, False) | enabled)


def _name(common_name: str) -> x509.Name:
    """Subject with only a CN, cut to the 64 characters X.509 allows (clients check the SAN, not the CN)."""
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name[:CN_MAX_LENGTH])])


def _private_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Unencrypted PKCS#8 PEM of a private key."""
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


def _now() -> datetime:
    """Current UTC time."""
    return datetime.now(timezone.utc)
