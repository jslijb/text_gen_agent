import http.server, socketserver, os
os.chdir(r'D:\Python\text_gen_agent\output\videos')
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('127.0.0.1', 8001), H) as s:
    s.serve_forever()
