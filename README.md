# NewBest-HomeAssistant MQTT Bridge

## Usage
1. Find ip of NewBest Admin, login with username `newbest` and password `pass`
2. Export `projectConfig.json` from NewBest Admin, save as `KNX-projectConfig.json`
3. Get `NEWBEST_MQTT_BROKER`, `NEWBEST_MQTT_USER`, `NEWBEST_MQTT_PWD` from NewBest Admin, set them in `.env`
4. Get `NEWBEST_MQTT_HOME` by subscribing the topic `newbest/+/exec/`, set it in `.env`
5. Setup mosquitto in your HomeAssistant, set `HA_MQTT_BROKER`, `HA_MQTT_USER` and `HA_MQTT_PWD` in `.env`
6. Exec `uv run main.py` to run

### systemd
- `cp ./nb_ha_bridge.service /etc/systemd/system/nb_ha_bridge.service`
- `systemctl daemon-reload`
- `systemctl start nb_ha_bridge`
- `systemctl enable nb_ha_bridge`

### Optional: replace newbest's mqtt broker to self-host one
1. Change the broker url in NewBest Admin to mosquitto's
2. Make `NEWBEST_MQTT_BROKER`, `NEWBEST_MQTT_USER`, `NEWBEST_MQTT_PWD` the same as `HA_MQTT_BROKER`, `HA_MQTT_USER` and `HA_MQTT_PWD`
