"""Zuverlässigere Internetverbindungen.

Python probiert die Adressen eines Servers nacheinander und wartet bei jeder
die volle Zeit ab. Ist IPv6 im Heimnetz nur halb eingerichtet, kann das bei
Diensten mit vielen Adressen (z. B. Google/YouTube) Minuten dauern.

Hier werden die Adressen deshalb gestaffelt fast gleichzeitig angefragt
(„Happy Eyeballs“, IPv4 zuerst): Die erste Verbindung, die klappt, wird
genommen. Danach gilt die normale Wartezeit für die Antwort.
"""

from __future__ import annotations

import errno
import selectors
import socket
import time

CONNECT_TIMEOUT = 8.0   # Höchstdauer für den Verbindungsaufbau insgesamt
STAGGER = 0.25          # Abstand, bevor die nächste Adresse zusätzlich probiert wird
_original = socket.create_connection


def _ordered(infos):
    v4 = [i for i in infos if i[0] == socket.AF_INET]
    v6 = [i for i in infos if i[0] != socket.AF_INET]
    out = []
    while v4 or v6:  # abwechselnd, IPv4 zuerst
        if v4:
            out.append(v4.pop(0))
        if v6:
            out.append(v6.pop(0))
    return out


def _create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *args, **kwargs):
    host, port = address[0], address[1]
    try:
        infos = _ordered(socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM))
    except OSError:
        return _original(address, timeout, source_address, *args, **kwargs)
    if not infos:
        return _original(address, timeout, source_address, *args, **kwargs)

    has_timeout = timeout is not socket._GLOBAL_DEFAULT_TIMEOUT and timeout is not None
    limit = min(timeout, CONNECT_TIMEOUT) if has_timeout else CONNECT_TIMEOUT
    deadline = time.monotonic() + limit
    sel = selectors.DefaultSelector()
    pending: list[socket.socket] = []
    last_error: OSError | None = None
    winner = None
    try:
        queue = list(infos)
        while (queue or pending) and winner is None:
            if queue:
                family, socktype, proto, _, sockaddr = queue.pop(0)
                try:
                    sock = socket.socket(family, socktype, proto)
                    sock.setblocking(False)
                    if source_address:
                        sock.bind(source_address)
                    code = sock.connect_ex(sockaddr)
                    if code in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EAGAIN):
                        pending.append(sock)
                        sel.register(sock, selectors.EVENT_WRITE)
                    else:
                        last_error = OSError(code, errno.errorcode.get(code, "Verbindungsfehler"))
                        sock.close()
                except OSError as exc:
                    last_error = exc
                    continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait = min(STAGGER, remaining) if queue else remaining
            for key, _ in sel.select(wait):
                sock = key.fileobj
                code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                sel.unregister(sock)
                pending.remove(sock)
                if code == 0:
                    winner = sock
                    break
                last_error = OSError(code, errno.errorcode.get(code, "Verbindungsfehler"))
                sock.close()
            if not queue and not pending:
                break
    finally:
        for sock in pending:
            if sock is not winner:
                try:
                    sel.unregister(sock)
                except Exception:
                    pass
                sock.close()
        sel.close()

    if winner is None:
        if last_error is not None:
            raise last_error
        raise socket.timeout(f"Zeitüberschreitung beim Verbinden mit {host}")
    winner.setblocking(True)
    winner.settimeout(timeout if has_timeout else None)
    return winner


def install() -> None:
    """Gilt für alle Verbindungen der App (urllib nutzt socket.create_connection)."""
    socket.create_connection = _create_connection
