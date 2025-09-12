#!/usr/bin/env python3
import argparse, socket, json, time

def run_client(host: str, port: int, reconnect_delay: float):
    while True:
        try:
            with socket.create_connection((host, port), timeout=10) as s:
                s.settimeout(30)
                print(f"[CLIENT] Połączono z {host}:{port}")
                buf = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        raise ConnectionError("Serwer zamknął połączenie")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line.decode("utf-8"))
                        except json.JSONDecodeError:
                            print("[CLIENT] Błędny JSON:", line[:120])
                            continue
                        if "error_x" in msg:
                            print(f"[CLIENT] error_x={msg['error_x']:.2f}, ts={msg.get('ts')}")
                            # TODO: tu dodaj sterowanie serwem / zapisem / PID itp.
                        else:
                            # np. {"status":"connected"}
                            print("[CLIENT] meta:", msg)
        except (OSError, ConnectionError, socket.timeout) as e:
            print(f"[CLIENT] problem z połączeniem: {e}. Ponawiam za {reconnect_delay}s...")
            time.sleep(reconnect_delay)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Adres IP laptopa (serwera)")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--reconnect", type=float, default=2.0)
    args = ap.parse_args()
    run_client(args.host, args.port, args.reconnect)
