# -*- coding: utf-8 -*-
"""Generate a QR code PNG for a given URL.

Run:  python icbf_qr.py https://YOURNAME.github.io/icbf-planner/

Writes icbf-planner-qr.png (teal) and icbf-planner-qr-bw.png (black, best for print).
"""
import sys
import qrcode
from qrcode.constants import ERROR_CORRECT_M

HERE_DEFAULT = "https://claude.ai/code/artifact/0c2f1499-170c-4efa-93b6-baf4e210f43f"


def make(url, path, fill):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=2, box_size=12)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color=fill, back_color="white").convert("RGB").save(path)
    return qr.version


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else HERE_DEFAULT
    v = make(url, "icbf-planner-qr.png", "#0e7c86")
    make(url, "icbf-planner-qr-bw.png", "black")
    print(f"URL: {url}")
    print(f"QR version {v} (lower = simpler/easier to scan)")
    print("Wrote icbf-planner-qr.png and icbf-planner-qr-bw.png")


if __name__ == "__main__":
    main()
