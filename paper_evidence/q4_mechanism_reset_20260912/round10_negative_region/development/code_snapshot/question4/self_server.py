"""Local mixed-source HTTP server. Never starts the official application."""
import argparse
from question3.self_server import make_server
from .cases import make_case
from .simulator import Simulator

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=2028)
    p.add_argument('--seed',type=int,default=0);p.add_argument('--family',default='uniform')
    args=p.parse_args();server=make_server(Simulator(make_case(args.seed,args.family)),args.port)
    print(f'SELF Q4 http://127.0.0.1:{server.server_port} robot_id=SELF',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
