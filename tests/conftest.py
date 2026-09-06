"""Bảo đảm test localhost không bị proxy môi trường chặn (sandbox/CI)."""

import os


def _add_no_proxy_hosts(name):
    current = os.environ.get(name, "")
    values = [item.strip() for item in current.split(",") if item.strip()]
    for host in ("127.0.0.1", "localhost"):
        if host not in values:
            values.append(host)
    os.environ[name] = ",".join(values)


_add_no_proxy_hosts("NO_PROXY")
_add_no_proxy_hosts("no_proxy")
