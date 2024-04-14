#!/usr/bin/env python3

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from private import PRIVATEKEY256
import socketserver
import json

class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(2048).strip()
        print("Received from {}:".format(self.client_address[0]))
        bstr = self.data
        jsn = json.loads(bstr)
        print(jsn)
        print(jsn["payload"])
#        print(bstr.decode("ascii"))
#        iv = self.data[0:16]
#        cyper = AES.new(PRIVATEKEY256, AES.MODE_CBC, iv)
#        msg = cyper.decrypt(self.data[16:])
#        print(msg.strip())
        self.request.sendall('ACK'.encode())

if __name__ == "__main__":
    HOST, PORT = "", 5050
    with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
        try:
            server.serve_forever()
        finally:
            server.shutdown()
            

