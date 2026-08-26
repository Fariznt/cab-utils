"""
Stand up a plain HTTP listener to receive Telnyx's inbound SMS webhook and
print what arrives (sender, text, event type). This is a connectivity check
only, not the real webhook - the real inbound handler (conversation logic,
signature verification) lives in sms/views.py once that's built.

Point the Cloudflare tunnel (localhost:8000 by default) and Telnyx's Messaging
Profile inbound webhook URL at whatever public URL routes here, then text the
Telnyx number and watch this print.

Usage:
    python -m sms.scripts.listen_for_sms [--port 8000]
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from sms.scripts._bootstrap import require_env

# Python fully buffers stdout when it's not a terminal (nohup, a log redirect,
# run_in_background) - without this, prints below sit unseen until the buffer
# fills or the process exits.
sys.stdout.reconfigure(line_buffering=True)


class TelnyxWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()

        try:
            payload = json.loads(body)
            data = payload["data"]
            message = data["payload"]
            print(f"event_type: {data.get('event_type')}")
            print(f"from: {message.get('from', {}).get('phone_number')}")
            print(f"to: {[t.get('phone_number') for t in message.get('to', [])]}")
            print(f"text: {message.get('text')!r}")
            print(f"received_at: {message.get('received_at')}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Couldn't parse payload as a Telnyx message event ({e}); raw body:")
            print(body.decode(errors="replace"))
        print("-" * 40)

    def log_message(self, format, *args):
        pass  # silence default request logging, we print what matters ourselves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    webhook_url = require_env("TELNYX_INBOUND_WEBHOOK_URL")
    server = HTTPServer(("0.0.0.0", args.port), TelnyxWebhookHandler)
    print(f"Listening on :{args.port} for Telnyx webhooks (Ctrl+C to stop)")
    print(f"Point Telnyx's inbound webhook at: {webhook_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
