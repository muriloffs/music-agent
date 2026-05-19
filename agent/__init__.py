"""music-agent package init.

Injects truststore so httpx/requests use the OS certificate store instead of
the bundled certifi CAs. Needed on Windows where the bundled CAs may miss
intermediates that Windows update keeps current; without this, live HTTPS
fetches (Stereogum, Quietus, Bandcamp, Last.fm, etc) fail with
CERTIFICATE_VERIFY_FAILED in the local dev environment.

Also points GRPC at the certifi cert bundle. The google.generativeai SDK
uses gRPC underneath, which has its own SSL stack independent of Python's
ssl module — truststore does not patch it. On Linux (GitHub Actions runner)
gRPC finds system CAs automatically; on Windows it cannot, so we explicitly
point it at certifi's bundle.

Linux: both fixes are harmless no-ops there.
"""

import os
import certifi

# Make gRPC (used by google.generativeai) trust certifi's CA bundle.
# Must be set BEFORE the SDK imports its gRPC channel.
os.environ.setdefault("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", certifi.where())

import truststore

truststore.inject_into_ssl()
