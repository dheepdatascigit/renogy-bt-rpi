import logging
import configparser
import os
import sys
from renogybt import InverterClient, RoverClient, RoverHistoryClient, BatteryClient, DataLogger, Utils
import asyncio
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
import json

conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
#collected_data = None

logging.basicConfig(level=logging.INFO)

config_file = sys.argv[1] if len(sys.argv) > 1 else 'config.ini'
config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), config_file)
config = configparser.ConfigParser(inline_comment_prefixes=('#'))
config.read(config_path)
data_logger: DataLogger = DataLogger(config)

# Azure IOT hub
async def aziothub_sendmsg(mqttmsg):
    # Fetch the connection string from an environment variable
    conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")

    # Create instance of the device client using the authentication provider
    device_client = IoTHubDeviceClient.create_from_connection_string(conn_str)

    # Connect the device client.
    await device_client.connect()

    # Send a single message
    msg = Message(mqttmsg, content_encoding='utf-8', content_type='application/json')
    print("Sending message...")
    # await device_client.send_message("This is a message that is being sent")
    #await device_client.send_message(mqttmsg)
    await device_client.send_message(msg)
    print("Message successfully sent!")

    # finally, shut down the client
    await device_client.shutdown()


# the callback func when you receive data
def on_data_received(client, data):
    filtered_data = Utils.filter_fields(data, config['data']['fields'])
    logging.info(f"{client.ble_manager.device.name} => {filtered_data}")
    global collected_data
    collected_data = filtered_data
    if config['remote_logging'].getboolean('enabled'):
        data_logger.log_remote(json_data=filtered_data)
    if config['mqtt'].getboolean('enabled'):
        data_logger.log_mqtt(json_data=filtered_data)
    if config['pvoutput'].getboolean('enabled') and config['device']['type'] == 'RNG_CTRL':
        data_logger.log_pvoutput(json_data=filtered_data)
    if not config['data'].getboolean('enable_polling'):
        client.stop()

# error callback
def on_error(client, error):
    logging.error(f"on_error: {error}")

# start client
if config['device']['type'] == 'RNG_CTRL':
    RoverClient(config, on_data_received, on_error).start()
    asyncio.run(aziothub_sendmsg(json.dumps(collected_data)))
elif config['device']['type'] == 'RNG_CTRL_HIST':
    RoverHistoryClient(config, on_data_received, on_error).start()
elif config['device']['type'] == 'RNG_BATT':
    BatteryClient(config, on_data_received, on_error).start()
elif config['device']['type'] == 'RNG_INVT':
    InverterClient(config, on_data_received, on_error).start()
else:
    logging.error("unknown device type")