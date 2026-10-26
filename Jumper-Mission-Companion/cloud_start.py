"""Start exactly one WSGI worker; visitor engines must share one bounded pool."""
import os
import sys


def main():
    port=int(os.environ.get('PORT','10000'))
    if not 1<=port<=65535:raise ValueError('PORT must be a valid TCP port')
    os.execv(sys.executable,[sys.executable,'-m','gunicorn','--bind',f'0.0.0.0:{port}',
        '--workers','1','--threads','4','--timeout','120','--graceful-timeout','30',
        '--access-logfile','-','--error-logfile','-','cloud_server:create_app()'])


if __name__=='__main__':main()
