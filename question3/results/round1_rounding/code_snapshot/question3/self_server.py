"""Local SELF HTTP fixture, default port 2027 (official default is 2026)."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,HTTPServer
from .cases import random_case
from .simulator import Simulator


def make_server(env,port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            status=400;response=dict(accepted=False,real_timestamp_ms=0,virtual_time_s=0)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>65536:status=413
                elif self.headers.get('Content-Type','').lower() not in ('application/json','application/json; charset=utf-8'):
                    status=415
                else:
                    def pairs(items):
                        d={}
                        for k,v in items:
                            if k in d:raise ValueError('Duplicate JSON key')
                            d[k]=v
                        return d
                    payload=json.loads(self.rfile.read(length).decode('utf-8'),object_pairs_hook=pairs,
                                       parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
                    if isinstance(payload,dict):status,response=env.request(self.path,payload)
            except (ValueError,UnicodeError):pass
            except ConnectionError:
                self.close_connection=True;return
            data=json.dumps(response,allow_nan=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    return HTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=2027);p.add_argument('--seed',type=int,default=0)
    args=p.parse_args();env=Simulator(random_case(args.seed));server=make_server(env,args.port)
    print(f'SELF ONLY http://127.0.0.1:{server.server_port}, robot_id=SELF',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
