# NewBest-HomeAssistant MQTT Bridge

## Usage
1. Export `projectConfig.json` from NewBest Admin, save as `KNX-projectConfig.json`
2. Get `NEWBEST_MQTT_BROKER`, `NEWBEST_MQTT_USER`, `NEWBEST_MQTT_PWD` from NewBest Admin, write them to `.env`
3. Get `NEWBEST_MQTT_HOME` by subscribing the topic `newbest/+/exec/`, write it to `.env`
4. Setup mosquitto in your HomeAssistant, write `HA_MQTT_BROKER`, `HA_MQTT_USER` and `HA_MQTT_PWD` to `.env`
5. Exec `uv run main.py` to run

### systemd
- `cp ./nb_ha_bridge.service /etc/systemd/system/nb_ha_bridge.service`
- `systemctl daemon-reload`
- `systemctl start nb_ha_bridge`
- `systemctl enable nb_ha_bridge`
