import mscl
import time
import json

import argparse

parser = argparse.ArgumentParser(description="Lord IMU Data Logger")

parser.add_argument("path", type=str, help="Serial port to connect to")
parser.add_argument("--baudRate", type=int, dest="baudRate", help="Baud rate to use", default=115200)

args = parser.parse_args()

def stream_data():
	node = mscl.DisplacementNode(mscl.Connection.Serial(args.path, args.baudRate))
	while True:
		# get all the packets that have been collected, with a timeout of 500 milliseconds
		packets = node.getDataPackets(500)

		for packet in packets:
			packetDict = {
				"ns": packet.collectedTimestamp().nanoseconds()
			}
			for dataPoint in packet.data():
				if dataPoint.valid():
					packetDict[dataPoint.channelName()] = dataPoint.as_float()

			yield packetDict

packetPrefix = ""
with open(f"{time.time()}.json", "a") as f:
	f.write("[")
	try:
		for packet in stream_data():
			f.write(packetPrefix+json.dumps(packet))
			packetPrefix = ","
	except KeyboardInterrupt:
		print("Finishing writing data...")
		f.write("]")
		f.close()
