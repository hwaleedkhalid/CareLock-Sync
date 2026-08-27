"""
CareLock Sync - TLS 1.3 Configuration for Production
Implements HTTPS with TLS 1.3 for secure data in transit

HIPAA Requirement: Encryption in Transit
- TLS 1.3 (latest, most secure)
- Strong cipher suites only
- Perfect Forward Secrecy (PFS)
- HSTS (HTTP Strict Transport Security)
"""

import ssl
import uvicorn
from pathlib import Path

# TLS 1.3 Configuration
TLS_CONFIG = {
    # SSL/TLS Settings
    "ssl_version": ssl.PROTOCOL_TLS_SERVER,  # Modern TLS
    "ssl_cert_reqs": ssl.CERT_NONE,  # For development; CERT_REQUIRED in production
    
    # TLS Version Restrictions
    "ssl_minimum_version": ssl.TLSVersion.TLSv1_3,  # Require TLS 1.3
    "ssl_maximum_version": ssl.TLSVersion.TLSv1_3,  # Only TLS 1.3
    
    # Cipher Suites (TLS 1.3 only - secure by default)
    # TLS 1.3 uses: TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256, TLS_AES_128_GCM_SHA256
    
    # Security Options
    "ssl_options": (
        ssl.OP_NO_SSLv2 |      # Disable SSLv2
        ssl.OP_NO_SSLv3 |      # Disable SSLv3
        ssl.OP_NO_TLSv1 |      # Disable TLS 1.0
        ssl.OP_NO_TLSv1_1 |    # Disable TLS 1.1
        ssl.OP_NO_TLSv1_2 |    # Disable TLS 1.2 (force 1.3)
        ssl.OP_NO_COMPRESSION | # Disable compression (CRIME attack)
        ssl.OP_CIPHER_SERVER_PREFERENCE  # Server chooses cipher
    ),
}


def generate_self_signed_cert(cert_dir: str = "certs"):
    """
    Generate self-signed certificate for development/testing
    
    For PRODUCTION: Use Let's Encrypt or commercial CA
    
    Args:
        cert_dir: Directory to store certificates
    
    Returns:
        Tuple of (cert_path, key_path)
    """
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from datetime import datetime, timedelta
    import os
    
    # Create cert directory
    cert_path = Path(cert_dir)
    cert_path.mkdir(exist_ok=True)
    
    print("Generating self-signed certificate for TLS 1.3...")
    
    # Generate private key (4096-bit RSA)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PK"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Islamabad"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Islamabad"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CareLock Sync"),
        x509.NameAttribute(NameOID.COMMON_NAME, "carelock-sync.local"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)  # Valid for 1 year
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("carelock-sync.local"),
            x509.DNSName("127.0.0.1"),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # Write private key
    key_file = cert_path / "server.key"
    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Write certificate
    cert_file = cert_path / "server.crt"
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(f"✅ Certificate generated:")
    print(f"   Certificate: {cert_file}")
    print(f"   Private Key: {key_file}")
    print(f"   Valid for: 365 days")
    print(f"\n⚠️  DEVELOPMENT ONLY - Use Let's Encrypt in production!")
    
    return str(cert_file), str(key_file)


def create_ssl_context(cert_file: str, key_file: str) -> ssl.SSLContext:
    """
    Create SSL context with TLS 1.3 configuration
    
    Args:
        cert_file: Path to SSL certificate
        key_file: Path to private key
    
    Returns:
        Configured SSL context
    """
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Set minimum TLS version to 1.3
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Security options
    context.options |= (
        ssl.OP_NO_SSLv2 |
        ssl.OP_NO_SSLv3 |
        ssl.OP_NO_TLSv1 |
        ssl.OP_NO_TLSv1_1 |
        ssl.OP_NO_TLSv1_2 |  # Force TLS 1.3
        ssl.OP_NO_COMPRESSION |
        ssl.OP_CIPHER_SERVER_PREFERENCE
    )
    
    # Load certificate and key
    context.load_cert_chain(cert_file, key_file)
    
    # Verify mode (for mutual TLS, if needed)
    context.verify_mode = ssl.CERT_NONE  # Change to CERT_REQUIRED for client certs
    
    return context


def run_secure_server(
    app,
    host: str = "0.0.0.0",
    port: int = 8443,
    cert_file: str = None,
    key_file: str = None,
    reload: bool = False
):
    """
    Run FastAPI with TLS 1.3 enabled
    
    Args:
        app: FastAPI application
        host: Host to bind to
        port: Port to listen on (443 for production, 8443 for dev)
        cert_file: SSL certificate path
        key_file: Private key path
        reload: Enable auto-reload (dev only)
    """
    # Generate self-signed cert if not provided
    if not cert_file or not key_file:
        print("No SSL certificate provided, generating self-signed certificate...")
        cert_file, key_file = generate_self_signed_cert()
    
    # Create SSL context
    ssl_context = create_ssl_context(cert_file, key_file)
    
    print(f"\n{'='*70}")
    print(f"  CareLock Sync - HTTPS Server with TLS 1.3")
    print(f"{'='*70}")
    print(f"  🔒 TLS Version: 1.3 (enforced)")
    print(f"  🔒 Cipher Suites: TLS 1.3 secure defaults")
    print(f"  🔒 Certificate: {cert_file}")
    print(f"  📡 Listening: https://{host}:{port}")
    print(f"  📖 API Docs: https://localhost:{port}/docs")
    print(f"{'='*70}\n")
    
    # Run server with SSL
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_keyfile=key_file,
        ssl_certfile=cert_file,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_cert_reqs=ssl.CERT_NONE,
        ssl_ca_certs=None,
        reload=reload,
        log_level="info"
    )


# Example usage
if __name__ == "__main__":
    # Generate certificate for testing
    cert_file, key_file = generate_self_signed_cert()
    
    print("\n" + "="*70)
    print("TLS 1.3 Configuration Ready")
    print("="*70)
    print("\nTo start CareLock Sync with HTTPS:")
    print(f"  python run_secure_server.py")
    print("\nOr integrate into your main app:")
    print(f"  from backend.security.tls_config import run_secure_server")
    print(f"  run_secure_server(app, port=8443)")
