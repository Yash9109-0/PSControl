"""Generate a tiny silent black MP4 (base64) for the NoSleep wake-lock fallback."""

import base64
import struct


class BitWriter:
    def __init__(self):
        self.bits = []

    def write(self, value, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((value >> i) & 1)

    def u(self, value, n):
        self.write(value, n)

    def ue(self, value):
        x = value + 1
        n = x.bit_length()
        for _ in range(n - 1):
            self.write(0, 1)
        self.write(x, n)

    def se(self, value):
        k = abs(value) * 2 - (1 if value <= 0 else 0)
        self.ue(k)

    def align(self):
        self.write(1, 1)
        while len(self.bits) % 8:
            self.write(0, 1)

    def bytes(self):
        out = bytearray()
        acc = 0
        nb = 0
        for b in self.bits:
            acc = (acc << 1) | b
            nb += 1
            if nb == 8:
                out.append(acc)
                acc = 0
                nb = 0
        if nb:
            out.append(acc << (8 - nb))
        return bytes(out)


def nal(rbsp):
    data = rbsp.bytes()
    out = bytearray(b"\x00\x00\x00\x01")
    i = 0
    while i < len(data):
        out.append(data[i])
        if i >= 2 and data[i - 2] == 0 and data[i - 1] == 0 and data[i] == 3:
            out.append(3)
        i += 1
    return bytes(out)


def box(t, body, full=False, version=0, flags=0):
    if full:
        hdr = struct.pack(">I", 12 + len(body)) + t.encode() + struct.pack(">I", (version << 24) | flags)
    else:
        hdr = struct.pack(">I", 8 + len(body)) + t.encode()
    return hdr + body


def sps():
    w = BitWriter()
    w.u(66, 8)
    w.u(0, 8)
    w.u(30, 8)
    w.ue(0)
    w.ue(1)
    w.u(0, 1)
    w.ue(0)
    w.ue(0)
    w.u(0, 1)
    w.u(0, 1)
    w.ue(0)
    w.ue(0)
    w.u(0, 1)
    w.ue(1)
    w.u(0, 1)
    w.ue(0)
    w.ue(0)
    w.u(1, 1)
    w.u(0, 1)
    w.u(0, 1)
    w.u(0, 1)
    w.align()
    return nal(w)


def pps():
    w = BitWriter()
    w.ue(0)
    w.ue(0)
    w.u(0, 1)
    w.u(0, 1)
    w.ue(0)
    w.ue(0)
    w.ue(0)
    w.u(0, 1)
    w.u(0, 2)
    w.se(0)
    w.se(0)
    w.se(0)
    w.u(0, 1)
    w.u(0, 1)
    w.u(0, 1)
    w.align()
    return nal(w)


def idr():
    w = BitWriter()
    w.ue(0)
    w.ue(7)
    w.ue(0)
    w.ue(0)
    w.u(0, 4)
    w.u(0, 1)
    w.align()
    return nal(w)


# Build NAL units
sps_nal = sps()
pps_nal = pps()
idr_nal = idr()
print("SPS", len(sps_nal), "PPS", len(pps_nal), "IDR", len(idr_nal))

# mdat = SPS + PPS + IDR
mdat = sps_nal + pps_nal + idr_nal
idr_offset = len(sps_nal + pps_nal)
idr_size = len(idr_nal)

# ---------------- boxes ----------------

# ftyp
ftyp = box("ftyp", struct.pack("<I", 0x00000200) + b"isomiso2avc1mp41")

# mvhd
mvhd_body = (
    struct.pack(">I", 0) + struct.pack(">I", 0) +  # creation, modification
    struct.pack(">I", 90000) + struct.pack(">I", 90000) +  # timescale, duration
    struct.pack(">I", 0x00010000) + struct.pack(">I", 0x00010000) +  # rate, volume+reserved
    b"\x00" * 10 +  # reserved
    struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) +  # matrix
    struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) +  # pre_defined
    struct.pack(">I", 0) + struct.pack(">I", 0)  # next_track_ID
)
mvhd = box("mvhd", mvhd_body, full=True, version=0, flags=0)

# tkhd
tkhd_body = (
    struct.pack(">I", 0x00000007) + struct.pack(">I", 0) + struct.pack(">I", 1) +  # flags, track id, reserved
    struct.pack(">I", 0) + struct.pack(">I", 0) +  # creation, modification
    struct.pack(">H", 1) + struct.pack(">H", 0) +  # layer, alternate_group
    struct.pack(">H", 0) + struct.pack(">H", 0) +  # volume, reserved
    struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 0) +  # matrix
    struct.pack(">H", 16) + struct.pack(">H", 16) + struct.pack(">H", 16) + struct.pack(">H", 16)  # width,height
)
tkhd = box("tkhd", tkhd_body, full=True, version=0, flags=0x000001)

# mdhd
mdhd_body = struct.pack(">I", 0) + struct.pack(">I", 0) + struct.pack(">I", 90000) + struct.pack(">I", 90000) + b"\x00\x01" + b"\x00\x00"
mdhd = box("mdhd", mdhd_body, full=True, version=0, flags=0)

# hdlr
hdlr_body = struct.pack(">I", 0) + b"vide" + b"\x00" * 12 + b"VideoHandler"
hdlr = box("hdlr", hdlr_body, full=True, version=0, flags=0)

# vmhd
vmhd_body = struct.pack(">H", 0) + b"\x00" * 6
vmhd = box("vmhd", vmhd_body, full=True, version=0, flags=0)

# dref (url self-reference)
url_body = b""  # flags 0x000001 => empty body
dref_body = struct.pack(">I", 1) + box("url ", url_body, full=True, version=0, flags=0x000001)
dinf = box("dinf", box("dref", dref_body, full=True, version=0, flags=0))

# stsd + avc1 + avcC
profile = 66
compatibility = 0
level = 30
length_size = 3  # 4-byte NAL length
avcc = (
    bytes([1, profile, compatibility, level]) +
    bytes([0xFC | 1]) +  # lengthSizeMinusOne(2bits)+reserved(3bits)+numSPS(5bits)=1
    struct.pack(">H", len(sps_nal)) + sps_nal +
    bytes([1]) +  # numPPS
    struct.pack(">H", len(pps_nal)) + pps_nal
)
avc1_body = (
    b"\x00" * 6 +  # reserved
    struct.pack(">H", 1) +  # data_reference_index
    struct.pack(">H", 16) + struct.pack(">H", 16) +  # width height
    struct.pack(">I", 0x00480000) + struct.pack(">I", 0x00480000) +  # horiz/vert res
    struct.pack(">I", 0) +  # reserved
    struct.pack(">H", 1) +  # frame_count
    b"\x00" * 32 +  # compressor name
    struct.pack(">H", 24) + struct.pack(">H", 0xFFFF) +  # depth, pre_defined
    avcc
)
stsd_body = struct.pack(">I", 1) + box("avc1", avc1_body)
stsd = box("stsd", stsd_body, full=True, version=0, flags=0)

# stts: 1 entry, sample_count=1, delta=90000 (1s at 90k)
stts_body = struct.pack(">I", 1) + struct.pack(">I", 1) + struct.pack(">I", 90000)
stts = box("stts", stts_body, full=True, version=0, flags=0)

# stsc: 1 entry
stsc_body = struct.pack(">I", 1) + struct.pack(">I", 1) + struct.pack(">I", 1) + struct.pack(">I", 1)
stsc = box("stsc", stsc_body, full=True, version=0, flags=0)

# stsz: variable sizes, 1 entry, then size
stsz_body = struct.pack(">I", 0) + struct.pack(">I", 1) + struct.pack(">I", idr_size)
stsz = box("stsz", stsz_body, full=True, version=0, flags=0)

# stco: 1 entry, offset of idr in mdat
stco_body = struct.pack(">I", 1) + struct.pack(">I", idr_offset)
stco = box("stco", stco_body, full=True, version=0, flags=0)

stbl = box("stbl", stsd + stts + stsc + stsz + stco)
minf = box("minf", vmhd + dinf + stbl)
mdia = box("mdia", mdhd + hdlr + minf)
trak = box("trak", tkhd + mdia)
moov = box("moov", mvhd + trak)

mp4 = ftyp + box("mdat", mdat) + moov

print("total MP4 bytes:", len(mp4))
b64 = base64.b64encode(mp4).decode()
DATA_URI = "data:video/mp4;base64," + b64
print("DATA_URI:", DATA_URI)
open("video_b64.txt", "w").write(b64)
