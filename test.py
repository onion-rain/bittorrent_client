import os

b1 = b''
b2 = b'adsf'
b3 = b'\x00\xf0\x00\x00\x00\x00\x00\x00\xf0\x00\x08\x00\x00\x00\x00\x08\x00x\n\x16\x0e'
b4 = bytes(range(20))
b5 = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13'
b6 = b'\x09'
b7 = b'\x0a'

# fd = os.open("test",  os.O_RDWR | os.O_CREAT | os.O_BINARY)
# os.write(fd, b7)
f = open("test", 'wb')
f.write(b7)