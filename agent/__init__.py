"""music-agent package init.

Injects truststore so httpx/requests use the OS certificate store instead of
the bundled certifi CAs. Needed on Windows where the bundled CAs may miss
intermediates that Windows update keeps current; without this, live HTTPS
fetches (Stereogum, Quietus, Bandcamp, Gemini, Last.fm, etc) fail with
CERTIFICATE_VERIFY_FAILED in the local dev environment.

Linux (GitHub Actions runner) does not require this — system CAs are
already what Python uses. Calling inject_into_ssl() there is a harmless
no-op, so it stays unconditional.
"""

import truststore

truststore.inject_into_ssl()
