"""Prints the current Steam Guard code for STEAM_SHARED_SECRET (base64), same algorithm as the mobile app."""

import base64
import hashlib
import hmac
import os
import struct
import time

ALPHABET = "23456789BCDFGHJKMNPQRTVWXY"


def code(secret: str, t: float) -> str:
    mac = hmac.new(base64.b64decode(secret), struct.pack(">Q", int(t) // 30), hashlib.sha1).digest()
    o = mac[-1] & 0x0F
    n = struct.unpack(">I", mac[o : o + 4])[0] & 0x7FFFFFFF
    out = ""
    for _ in range(5):
        out += ALPHABET[n % len(ALPHABET)]
        n //= len(ALPHABET)
    return out


if __name__ == "__main__":
    print(code(os.environ["STEAM_SHARED_SECRET"], time.time()))
