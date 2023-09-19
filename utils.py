import struct

def pack_dict(data, buf = bytes()):
    if isinstance(data, dict):
        for k, v in data.items():
            buf += k.encode("utf-8")
            if isinstance(v, bytes):
                buf += v
            elif isinstance(v, int):
                buf += struct.pack("!i", v)
            elif isinstance(v, (list, dict)):
                pack_dict(v, buf)
    elif isinstance(data, list):
        for element in data:
           pack_dict(element, buf)
    elif isinstance(data, bytes):
            buf += data
    else:
        buf += struct.pack("!i", data)

    return buf
