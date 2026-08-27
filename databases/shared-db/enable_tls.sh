#!/bin/sh
set -e
cd /var/lib/postgresql/data

# Generate self-signed certificate
openssl req -new -x509 -days 365 -nodes \
  -out server.crt \
  -keyout server.key \
  -subj '/CN=carelock-fhir/O=CareLock/C=PK'

chmod 600 server.key
chown postgres:postgres server.crt server.key

# Remove old ssl lines and add fresh ones
grep -v '^ssl' postgresql.conf > postgresql.conf.tmp
mv postgresql.conf.tmp postgresql.conf
echo "ssl = on"                    >> postgresql.conf
echo "ssl_cert_file = 'server.crt'" >> postgresql.conf
echo "ssl_key_file = 'server.key'"  >> postgresql.conf

echo "TLS_CONFIGURED_OK"
cat postgresql.conf | grep ^ssl
