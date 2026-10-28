"""Rough text extraction from a PDF's Flate streams (text-showing operators only)."""
import re, sys, zlib
data = open(sys.argv[1], "rb").read()
out = []
for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
    try:
        s = zlib.decompress(m.group(1))
    except Exception:
        continue
    for t in re.findall(rb"\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj", s, re.S):
        chunk = t[0] or t[1]
        parts = re.findall(rb"\(((?:\\.|[^\\)])*)\)", chunk) if t[0] else [chunk]
        out.append(b"".join(parts).decode("latin-1"))
    out.append("\n")
print(re.sub(r"\n{3,}", "\n\n", "".join(o if o == "\n" else o + " " for o in out)))
