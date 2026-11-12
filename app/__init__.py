VERSION = "0.6.1.1"

# Verbindungen: IPv4 zuerst, kurze Wartezeit je Adresse (siehe net.py)
from . import net as _net

_net.install()

# macOS mit Python von python.org: Zertifikate des Systems nutzen (siehe certs.py)
from . import certs as _certs
from . import storage as _storage

_certs.install(_storage.config_dir())
