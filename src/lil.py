from typing import Any, Union
import mscl
import time
import json

import argparse

import sqlite3

from os import makedirs

parser = argparse.ArgumentParser(description="Lord IMU Data Logger")

parser.add_argument("path", type=str, help="Serial port to connect to")
parser.add_argument("--savePath", type=str, default=".",
                    help="Path to save files to")
parser.add_argument("--fileType", type=str, default="sqlite",
                    help="Format to save data in, options are sqlite or json")
parser.add_argument("--baudRate", type=int, dest="baudRate",
                    help="Baud rate to use", default=115200)
parser.add_argument("--newFileInterval", type=int, dest="newFileInterval",
                    help="Interval in seconds to create a new file", default=-1)
parser.add_argument('--ignoreFields', nargs='+', default=["gpsCorrelTimestampTow", "gpsCorrelTimestampWeekNum",
                    "gpsCorrelTimestampFlags", "estFilterGpsTimeTow", "estFilterGpsTimeWeekNum"])

args = parser.parse_args()

node = mscl.DisplacementNode(mscl.Connection.Serial(args.path, args.baudRate))


def stream_data():
    while True:
        # get all the packets that have been collected, with a timeout of 500 milliseconds
        packets = node.getDataPackets(500)

        for packet in packets:
            packetDict = {
                "ns": packet.collectedTimestamp().nanoseconds()
            }
            for dataPoint in packet.data():
                channelName = dataPoint.channelName()
                if dataPoint.valid() and channelName not in args.ignoreFields:
                    packetDict[channelName] = dataPoint.as_float()

            yield packetDict


def new_json_file(closeAt: Union[int, None]):
    packetPrefix = ""

    file = f"{args.savePath}\\{time.time()}.json"
    if args.savePath != ".":
        makedirs(args.savePath, exist_ok=True)

    print(f"[{time.time()}] - Opening new file {file} for writing...")
    with open(file, "a") as f:
        f.write("[")
        try:
            for packet in stream_data():
                f.write(packetPrefix+json.dumps(packet))
                packetPrefix = ","
                if closeAt != None and time.time() >= closeAt:
                    break
        finally:
            print(f"[{time.time()}] - Writing end of file \"{file}\"...")
            f.write("]")
            f.close()


def new_sqlite_file(closeAt: Union[int, None]):
    file = f"{args.savePath}\\{time.time()}.db"
    if args.savePath != ".":
        makedirs(args.savePath, exist_ok=True)

    print(f"[{time.time()}] - Opening new file {file} for writing...")
    db = sqlite3.connect(file)

    cur = db.cursor()
    cur.execute("PRAGMA page_size = 65536")

    first100Packets: Union[list[dict[str, float]], None] = []
    lastInsert = 0

    try:
        for packet in stream_data():
            if (first100Packets != None):
                first100Packets.append(packet)
                if (len(first100Packets) >= 100):
                    rowNames: dict[str, str] = {}
                    for packet in first100Packets:
                        for key in packet.keys():
                            rowNames[key] = type(packet[key]).__name__
                    create_table(cur, rowNames)

                    for packet in first100Packets:
                        insert_packet(packet)

                    first100Packets = None
                    continue
            else:
                insert_packet(packet)

                # Insert data every second
                if (time.time()-lastInsert >= 1):
                    lastInsert = time.time()
                    cur.execute("BEGIN TRANSACTION")
                    for batch in packetBuffer:
                        cur.executemany(
                            f"INSERT INTO packets ({','.join(batch['keys'])}) VALUES ({','.join(['?']*len(batch['keys']))})", batch["values"])
                    packetBuffer.clear()
                    cur.execute("COMMIT")

            if closeAt != None and time.time() >= closeAt:
                break
    finally:
        print("Closing DB")
        cur.close()
        db.commit()
        db.close()


packetBuffer = []


def insert_packet(packet: dict):
    keys = packet.keys()
    values = tuple([packet[key] for key in keys])
    for batch in packetBuffer:
        if (batch["keys"] == keys):
            batch["values"].append(values)
            return

    packetBuffer.append({
        "keys": keys,
        "values": [values]
    })


def create_table(cur: sqlite3.Cursor, tableDef: dict):
    values = ', '.join([f'{key} {tableDef[key]}' for key in tableDef.keys()])
    cur.execute(f"CREATE TABLE packets ({values})")


while True:
    if args.newFileInterval == -1:
        closeAt = None
    else:
        closeAt = time.time()+args.newFileInterval

    if (args.fileType == "json"):
        new_json_file(closeAt)
    if (args.fileType == "sqlite"):
        new_sqlite_file(closeAt)
