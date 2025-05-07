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
    LEGRAND_CONTROL = 83    # 罗格朗可视对讲
    VMC = 301               # 新风


def load_knx_device_map():
    with open("./KNX-projectConfig.json", "r") as f:
        data = json.load(f)
        for group in data.get("homeConfig", {}).get("data", {}).get("DEVICE_GROUP", []):
            for device in group.get("DEVICE", []):
                device_type_id = device.get("DEVICE_TYPE_ID")
                device_id = device.get("DEVICE_ID")
                name = device.get("NAME")
                KNX_DEVICE_MAP[device_id] = [device_type_id, name]


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
    device_name = KNX_DEVICE_MAP[device_id][1]
    on_off = info.get("On/Off") # "0" | "1"
    room_point = info.get("RoomPoint")
    set_point = info.get("SetPoint")
    fan_speed = info.get("FanSpeed")
    mode = info.get("Mode")
    value_status = info.get("ValveStatus")

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
        }
        ha_mqtt.publish(topic, json.dumps(payload), 1, True)
        if on_off == "1":
            ha_mqtt.publish(f"{topic_prefix}/state", b"ON", 1, True)
        elif on_off == "0":
            ha_mqtt.publish(f"{topic_prefix}/state", b"OFF", 1, True)
    elif device_type_id == DeviceType.AC or device_type_id == DeviceType.LIVING_ROOM_AC:
        print(device_name, on_off, room_point, set_point, fan_speed, mode)
    elif device_type_id == DeviceType.FLOOR_HEATING:
        print(device_name, room_point, value_status)
    else:
        print(device_name, info)


def ha_update_state(state: dict):
    try:
        device_id, device_type_id = parse_device_id(state)
    except Exception:
        return
    if device_type_id == DeviceType.LIGHT:
        on_off = state.get("On/Off")
        unique_id = f"knx_light_{device_id}"
        topic_prefix = f"homeassistant/light/{unique_id}"
        if on_off == "1":
            ha_mqtt.publish(f"{topic_prefix}/state", b"ON", 1, True)
        elif on_off == "0":
            ha_mqtt.publish(f"{topic_prefix}/state", b"OFF", 1, True)


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


def on_ha_message(_client, _userdata, msg: MQTTMessage):
    print("on_ha_msg", msg.topic, msg.payload)
    splits = msg.topic.split("/")
    if len(splits) != 4:
        return
    prefix, componet, obj_id, cmd = splits
    if prefix != "homeassistant":
        return
    if cmd == "set":
        if componet == "light":
            device_id = obj_id.replace("knx_light_", "")
            nb_topic = f"{NEWBEST_MQTT_TOPIC_PREFIX}/exec/"
            is_on = msg.payload == b"ON"
            nb_payload = {
                "On/Off": "1" if is_on else "0",
                "deviceId": device_id,
            }
            newbest_mqtt.publish(nb_topic, json.dumps(nb_payload))
            return


def run():
    load_knx_device_map()

    ha_mqtt.connect(HA_MQTT_BROKER)
    ha_mqtt.subscribe("homeassistant/#")
    ha_mqtt.on_message = on_ha_message
    ha_mqtt.on_connect = on_ha_connect
    ha_mqtt.loop_start()

    newbest_mqtt.connect(NEWBEST_MQTT_BROKER)
    newbest_mqtt.subscribe(f"{NEWBEST_MQTT_TOPIC_PREFIX}/#")
    newbest_mqtt.on_message = on_newbest_msg
    newbest_mqtt.loop_start()
    newbest_mqtt.publish(f"{NEWBEST_MQTT_TOPIC_PREFIX}/home/statusInfo/", "{}")

    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        newbest_mqtt.loop_stop()
        ha_mqtt.loop_stop()

if __name__ == "__main__":
    run()
