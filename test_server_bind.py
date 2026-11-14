import sys
import socket
from pathlib import Path

# Test binding socket on 8000 directly
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("0.0.0.0", 8000))
    s.listen(1)
    print("Socket 0.0.0.0:8000 successfully bound and listening!")
except Exception as e:
    print("Bind error:", e)
finally:
    s.close()
