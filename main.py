import os
import json
import time
import enum
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.client import MQTTMessage

load_dotenv()

NEWBEST_MQTT_BROKER = os.getenv("NEWBEST_MQTT_BROKER")
NEWBEST_MQTT_USER = os.getenv("NEWBEST_MQTT_USER")
NEWBEST_MQTT_PWD = os.getenv("NEWBEST_MQTT_PWD")
NEWBEST_MQTT_HOME = os.getenv("NEWBEST_MQTT_HOME")
NEWBEST_MQTT_TOPIC_PREFIX = f"newbest/{NEWBEST_MQTT_HOME}"
newbest_mqtt = mqtt.Client(CallbackAPIVersion.VERSION2)
newbest_mqtt.username_pw_set(NEWBEST_MQTT_USER, NEWBEST_MQTT_PWD)

HA_MQTT_BROKER = os.getenv("HA_MQTT_BROKER")
HA_MQTT_USER = os.getenv("HA_MQTT_USER")
HA_MQTT_PWD = os.getenv("HA_MQTT_PWD")
ha_mqtt = mqtt.Client(CallbackAPIVersion.VERSION2)
ha_mqtt.username_pw_set(HA_MQTT_USER, HA_MQTT_PWD)

KNX_DEVICE_MAP = {}

class DeviceType(enum.IntEnum):
    LIGHT = 6               # 灯
    AC = 9                  # 空调
    FLOOR_HEATING = 10      # 地暖
    LIVING_ROOM_AC = 73     # 客厅空调开关/设置温度/风速/模式
    # LEGRAND_CONTROL = 83    # 罗格朗可视对讲
    # VMC = 301               # 新风


def load_knx_device_map():
    with open("./KNX-projectConfig.json", "r") as f:
        data = json.load(f)
        for group in data.get("homeConfig", {}).get("data", {}).get("DEVICE_GROUP", []):
            area = group.get("NAME")
            for device in group.get("DEVICE", []):
                device_type_id = device.get("DEVICE_TYPE_ID")
                device_id = device.get("DEVICE_ID")
                name = device.get("NAME")
                KNX_DEVICE_MAP[device_id] = [device_type_id, name, area]


def parse_device_id(info: dict):
    device_id = info.get("deviceId")
    device_type_id = info.get("deviceTypeId")
    return int(device_id), int(device_type_id)


def ha_push_config(info: dict):
    try:
        device_id, device_type_id = parse_device_id(info)
    except Exception:
        return
    if device_id not in KNX_DEVICE_MAP:
        print("skip", info)
        return
    device_name, area = KNX_DEVICE_MAP[device_id][1:]
    if device_type_id == DeviceType.LIGHT:
        # https://www.home-assistant.io/integrations/light.mqtt/
        unique_id = f"knx_light_{device_id}"
        topic_prefix = f"homeassistant/light/{unique_id}"
        topic = f"{topic_prefix}/config"
        payload = {
            "unique_id": unique_id,
            "name": device_name,
            "state_topic": f"{topic_prefix}/state",
            "command_topic": f"{topic_prefix}/set",
            "device": {
                "name": "",
                "suggested_area": area,
                "identifiers": [unique_id]
            },
        }
        ha_mqtt.publish(topic, json.dumps(payload), 1, False)
        ha_update_state(info)
    elif device_type_id == DeviceType.AC or device_type_id == DeviceType.LIVING_ROOM_AC:
        unique_id = f"knx_ac_{device_id}"
        topic_prefix = f"homeassistant/climate/{unique_id}"
        topic = f"{topic_prefix}/config"
        payload = {
            "unique_id": unique_id,
            "name": device_name,
            "power_command_topic": f"{topic_prefix}/power/set",
            "modes": ["off", "cool", "heat", "fan_only", "dry"],
            "mode_command_topic": f"{topic_prefix}/mode/set",
            "mode_state_topic": f"{topic_prefix}/mode/state",
            "temperature_command_topic": f"{topic_prefix}/temperature/set",
            "temperature_state_topic": f"{topic_prefix}/temperature/state",
            "current_temperature_topic": f"{topic_prefix}/current_temperature/state",
            "min_temp": 16,
            "max_temp": 30,
            "temp_step": 0.5,
            "temperature_unit": "C",
            "fan_modes": ["low", "medium", "high", "auto"],
            "fan_mode_command_topic": f"{topic_prefix}/fan_mode/set",
            "fan_mode_state_topic": f"{topic_prefix}/fan_mode/state",
            "device": {
                "name": "",
                "suggested_area": area,
                "identifiers": [unique_id]
            },
        }
        ha_mqtt.publish(topic, json.dumps(payload), 1, False)
        ha_update_state(info)
    elif device_type_id == DeviceType.FLOOR_HEATING:
        unique_id = f"knx_fh_{device_id}"
        topic_prefix = f"homeassistant/climate/{unique_id}"
        topic = f"{topic_prefix}/config"
        payload = {
            "unique_id": unique_id,
            "name": device_name,
            "modes": ["off", "heat"],
            "mode_command_topic": f"{topic_prefix}/mode/set",
            "mode_state_topic": f"{topic_prefix}/mode/state",
            "temperature_command_topic": f"{topic_prefix}/temperature/set", # 设置目标温度
            "temperature_state_topic": f"{topic_prefix}/temperature/state", # 当前目标温度
            "current_temperature_topic": f"{topic_prefix}/current_temperature/state",
            "min_temp": 10,
            "max_temp": 30,
            "temp_step": 0.5,
            "temperature_unit": "C",
            "device": {
                "name": "",
                "suggested_area": area,
                "identifiers": [unique_id]
            },
        }
        ha_mqtt.publish(topic, json.dumps(payload), 1, False)
        ha_update_state(info)
    else:
        print(device_name, info)


def ha_update_state(state: dict):
    try:
        device_id, device_type_id = parse_device_id(state)
    except Exception:
        return
    on_off = state.get("On/Off")
    mode = state.get("Mode")                # 模式，制冷、制热之类的
    room_point = state.get("RoomPoint")     # 实际温度
    set_point = state.get("SetPoint")       # 目标温度
    fan_speed = state.get("FanSpeed")
    value_status = state.get("ValveStatus")

    if device_type_id == DeviceType.LIGHT:
        unique_id = f"knx_light_{device_id}"
        topic_prefix = f"homeassistant/light/{unique_id}"
        if on_off == "1":
            ha_mqtt.publish(f"{topic_prefix}/state", b"ON", 1, True)
        elif on_off == "0":
            ha_mqtt.publish(f"{topic_prefix}/state", b"OFF", 1, True)
    elif device_type_id in [DeviceType.AC, DeviceType.LIVING_ROOM_AC]:
        unique_id = f"knx_ac_{device_id}"
        topic_prefix = f"homeassistant/climate/{unique_id}"
        if on_off == "0":
            ha_mqtt.publish(f"{topic_prefix}/mode/state", b"off", 1, True)
        elif on_off == "1":
            if mode == "1":
                ha_mqtt.publish(f"{topic_prefix}/mode/state", b"cool", 1, True)
            elif mode == "2":
                ha_mqtt.publish(f"{topic_prefix}/mode/state", b"fan_only", 1, True)
            elif mode == "3":
                ha_mqtt.publish(f"{topic_prefix}/mode/state", b"dry", 1, True)
            elif mode == "4":
                ha_mqtt.publish(f"{topic_prefix}/mode/state", b"heat", 1, True)
            if fan_speed == "5":
                ha_mqtt.publish(f"{topic_prefix}/fan_mode/state", b"high", 1, True)
            elif fan_speed == "3" or fan_speed == "4":
                ha_mqtt.publish(f"{topic_prefix}/fan_mode/state", b"medium", 1, True)
            elif fan_speed == "1" or fan_speed == "2":
                ha_mqtt.publish(f"{topic_prefix}/fan_mode/state", b"low", 1, True)
            elif fan_speed == "0":
                ha_mqtt.publish(f"{topic_prefix}/fan_mode/state", b"auto", 1, True)
        if set_point:
            ha_mqtt.publish(f"{topic_prefix}/temperature/state", set_point, 1, True)
        if room_point:
            ha_mqtt.publish(f"{topic_prefix}/current_temperature/state", room_point, 1, True)
    elif device_type_id == DeviceType.FLOOR_HEATING:
        unique_id = f"knx_fh_{device_id}"
        topic_prefix = f"homeassistant/climate/{unique_id}"
        if value_status == "0":
            ha_mqtt.publish(f"{topic_prefix}/mode/state", b"off", 1, True)
        elif value_status == "1":
            ha_mqtt.publish(f"{topic_prefix}/mode/state", b"heat", 1, True)
        if set_point:
            ha_mqtt.publish(f"{topic_prefix}/temperature/state", set_point, 1, True)
        if room_point:
            ha_mqtt.publish(f"{topic_prefix}/current_temperature/state", room_point, 1, True)


def on_newbest_connect(_client, _userdata, flags, reason, properties):
    print("on_newbest_connect", flags, reason, properties)
    newbest_mqtt.subscribe(f"{NEWBEST_MQTT_TOPIC_PREFIX}/#")
    newbest_mqtt.publish(f"{NEWBEST_MQTT_TOPIC_PREFIX}/home/statusInfo/", "{}")


def on_newbest_msg(_client, _userdata, msg: MQTTMessage):
    print("on_newbest_msg", msg.topic, msg.payload)
    payload = json.loads(msg.payload.decode("utf-8"))
    if msg.topic == f"{NEWBEST_MQTT_TOPIC_PREFIX}/home/statusInfo/res":
        for info in payload.get("info", []):
            ha_push_config(info)
    elif msg.topic == f"{NEWBEST_MQTT_TOPIC_PREFIX}/status":
        ha_update_state(payload)


def on_ha_connect(_client, _userdata, flags, reason, properties):
    print("on_ha_connect", flags, reason, properties)
    ha_mqtt.subscribe("homeassistant/#")
    if newbest_mqtt.is_connected():
        newbest_mqtt.publish(f"{NEWBEST_MQTT_TOPIC_PREFIX}/home/statusInfo/", "{}")


def on_ha_message(_client, _userdata, msg: MQTTMessage):
    print("on_ha_msg", msg.topic, msg.payload)
    splits = msg.topic.split("/")
    if len(splits) == 4:
        prefix, component, obj_id, cmd = splits
        sub = None
    elif len(splits) == 5:
        prefix, component, obj_id, sub, cmd = splits
    else:
        return
    if prefix != "homeassistant":
        return
    is_on = msg.payload == b"ON"
    nb_topic = f"{NEWBEST_MQTT_TOPIC_PREFIX}/exec/"
    nb_payload = None
    if component == "light" and cmd == "set":
        device_id = obj_id.replace("knx_light_", "")
        nb_payload = {
            "On/Off": "1" if is_on else "0",
            "deviceId": device_id,
        }
    elif component == "climate" and cmd == "set":
        device_id = obj_id.replace("knx_ac_", "")
        if sub == "power":
            nb_payload = {
                "On/Off": "1" if is_on else "0",
                "deviceId": device_id,
            }
        elif sub == "mode":
            mode = None
            if msg.payload == b"off":
                nb_payload = {
                    "On/Off": "0",
                    "deviceId": device_id,
                }
            elif msg.payload == b"cool":
                mode = "1"
            elif msg.payload == b"fan_only":
                mode = "2"
            elif msg.payload == b"dry":
                mode = "3"
            elif msg.payload == b"heat":
                mode = "4"
            if mode:
                # 需要先确保空调是开启的
                newbest_mqtt.publish(nb_topic, json.dumps({
                    "On/Off": "1",
                    "deviceId": device_id,
                }))
                time.sleep(1)
                nb_payload = {
                    "Mode": mode,
                    "deviceId": device_id,
                }
        elif sub == "temperature":
            nb_payload = {
                "SetPoint": msg.payload.decode("utf-8"),
                "deviceId": device_id,
            }
        elif sub == "fan_mode":
            speed = 0
            if msg.payload == b"low":
                speed = 1
            elif msg.payload == b"medium":
                speed = 3
            elif msg.payload == b"high":
                speed = 5
            elif msg.payload == b"auto":
                speed = 0
            nb_payload = {
                "FanSpeed": f"{speed}",
                "deviceId": device_id,
            }
    if nb_payload:
        newbest_mqtt.publish(nb_topic, json.dumps(nb_payload))


def on_disconnect(client, userdata, rc, reason, properties):
    print("Disconnected with result code " + str(rc))
    if rc != 0:
        print("Unexpected disconnection. Will attempt to reconnect.")
        reconnect(client)


def reconnect(client):
    while True:
        try:
            client.reconnect()
            print("Reconnected successfully")
            break
        except:
            print("Reconnection failed, trying again in 5 seconds...")
            time.sleep(5)  # 重连间隔时间


def run():
    load_knx_device_map()

    ha_mqtt.connect(HA_MQTT_BROKER)
    ha_mqtt.on_connect = on_ha_connect
    ha_mqtt.on_message = on_ha_message
    ha_mqtt.on_disconnect = on_disconnect
    ha_mqtt.loop_start()

    newbest_mqtt.connect(NEWBEST_MQTT_BROKER)
    newbest_mqtt.on_connect = on_newbest_connect
    newbest_mqtt.on_message = on_newbest_msg
    newbest_mqtt.on_disconnect = on_disconnect
    newbest_mqtt.loop_start()

    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        newbest_mqtt.loop_stop()
        ha_mqtt.loop_stop()


if __name__ == "__main__":
    run()
