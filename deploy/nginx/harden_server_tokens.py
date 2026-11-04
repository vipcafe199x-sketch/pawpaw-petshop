"""Install a small Nginx http-scope snippet; validate and roll back on failure.

Run as root: python3 deploy/nginx/harden_server_tokens.py
Does not edit vhosts, certificates, proxy routes, packages or database data.
"""
import os
from pathlib import Path
import subprocess
import tempfile

CONTENT=b'# Managed PawPaw hardening: version only; does not replace security updates.\nserver_tokens off;\n'


def atomic_write(path,data):
    fd,name=tempfile.mkstemp(prefix='.pawpaw-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as file: file.write(data)
        os.chmod(name,0o644);os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def harden(directory='/etc/nginx/conf.d',nginx='nginx'):
    path=Path(directory)/'pawpaw-security.conf'
    if not path.parent.is_dir(): raise RuntimeError('Nginx conf.d directory missing; no change made')
    if path.is_symlink(): raise RuntimeError('Refusing to overwrite a symlink')
    before=path.read_bytes() if path.exists() else None
    if before is not None and before!=CONTENT: raise RuntimeError('Existing unmanaged snippet; no change made')
    def run(*args): subprocess.run([nginx,*args],check=True,capture_output=True,text=True)
    run('-t')
    if before==CONTENT: return False
    atomic_write(path,CONTENT)
    try:
        run('-t');run('-s','reload')
    except Exception:
        if before is None: path.unlink(missing_ok=True)
        else: atomic_write(path,before)
        run('-t');run('-s','reload')
        raise RuntimeError('Nginx change failed; previous snippet restored') from None
    return True


if __name__=='__main__':
    if os.geteuid()!=0: raise SystemExit('Run with sudo/root; no config changed')
    harden()
    print('Nginx snippet configured and config syntax validated; verify external Server header separately.')
