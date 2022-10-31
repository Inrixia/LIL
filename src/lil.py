import mscl
import time
import json

import argparse

parser = argparse.ArgumentParser(description="Lord IMU Data Logger")

parser.add_argument("path", type=str, help="Serial port to connect to")
parser.add_argument("--savePath", type=str, default=".", help="Path to save files to")
parser.add_argument("--baudRate", type=int, dest="baudRate", help="Baud rate to use", default=115200)
parser.add_argument("--newFileInterval", type=int, dest="newFileInterval", help="Interval in seconds to create a new file", default=60*60)

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
				if dataPoint.valid():
					packetDict[dataPoint.channelName()] = dataPoint.as_float()

			yield packetDict



def new_file(closeAt):
	packetPrefix = ""
	file = f"{args.savePath}\\{time.time()}.json"
	print(f"[{time.time()}] - Opening new file {file} for writing...")
	with open(file, "a") as f:
		f.write("[")
		try:
			for packet in stream_data():
				f.write(packetPrefix+json.dumps(packet))
				packetPrefix = ","
				if time.time() >= closeAt:
					break
		finally:
			print(f"[{time.time()}] - Writing end of file \"{file}\"...")
			f.write("]")
			f.close()

while True:
	new_file(time.time()+args.newFileInterval)