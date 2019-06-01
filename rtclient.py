#!/usr/bin/env python

import argparse
from struct import pack,unpack
from sys import exit
from serial import Serial
from serial.serialutil import SerialException


def parse_trace(trace):
    # Traceformat:
    # 32 bits timestamp (little endian)
    # 16 bits duration (little endian)
    # 16 bits data length (little endian, Highest Bit used as readerToTag flag)
    # y Bytes data
    # x Bytes parity (one byte per 8 bytes data)

    timestamp = unpack('<I', trace[0:4])[0]
    duration = unpack('<H', trace[4:6])[0]
    data_len = unpack('<H', trace[6:8])[0]

    reader_to_tag = 'T' if (data_len & 0x8000) else 'R'
    data_len &= 0x7fff

    data = trace[8:8+data_len]
    parity = trace[8+data_len:]

    parity_len = (data_len-1)//8 + 1

    return reader_to_tag, timestamp, duration, data, parity


def proxmark3_snoop(serial_port):
    try:
        serial = Serial(serial_port, timeout=5)
    except SerialException as e:
        print(e)
        exit(e.errno)

    snoop_cmd = b''
    snoop_cmd += b'\x83\x03\x00\x00\x00\x00\x00\x00'    # snoop command number
    snoop_cmd += b'\x04\x00\x00\x00\x00\x00\x00\x00'    # param to signal realtime snoop
    snoop_cmd += b'\x00' * (544-len(snoop_cmd))

    serial.write(snoop_cmd)

    return serial


def check_parity(b, p):
    cnt = sum([(b>>i)&1 for i in range(8)])
    cnt += p & 1

    if cnt & 1:
        return True

    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simple python client for proxmark3 realtime snoop mode')
    parser.add_argument('port', help='proxmark3 serial port')
    args = parser.parse_args()

    serial = proxmark3_snoop(args.port)

    while True:
        tmp = serial.read(2)

        if len(tmp) == 0: continue

        cmd = 0
        cmd |= tmp[0]
        cmd |= tmp[1] << 8

        if cmd == 0x0100: # debug message
            data = serial.read(544-2)
            msg_len = unpack('<Q', data[6:14])[0] # extract debug message length (first usb command parameter)
            message = str(data[30:30+msg_len], 'ascii')
            print(message)
            continue
        elif cmd == 0xdead:
            print("snoop stopped")
            break
        elif cmd == 0x0318:
            trace_len = unpack('<H', serial.read(2))[0]
            trace = serial.read(trace_len)

            reader_to_tag, timestamp, duration, data, parity = parse_trace(trace)

            # print('{} | {:10} | {:10} | '.format(reader_to_tag, timestamp, duration), end='')
            print('{} | '.format(reader_to_tag), end='')
            for i in range(len(data)):
                p = parity[i >> 3] >> (7 - (i & 7))
                if check_parity(data[i], p):
                    print('{:02x} '.format(data[i]), end='')
                else:
                    print('{:02x}! '.format(data[i]), end='')

            print()
        else:
            print(hex(cmd))
            print("unrecognized command")
            break

    print('end')
    print(serial.read_all())
    serial.close()
