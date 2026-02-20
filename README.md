EcoWitt local web dashboard with meshtastic push service over protobuf

This is a small local webserver for displaying minimal information from your EcoWitt weather station.
The data will be retrieved directly from the station's push notifications via GW1100 and made available for sending as a 4-line text message over the meshtastic network via a channel configured within the script.
To function correctly, you will need to configure the custom section of the weather station's gateway by entering the Raspberry Pi's IP address, the "/ecowitt" path for sending data, the server port (8080), and the upload times.
The webserver will be available at http://Raspberry_IP:8080/


HARDWARE
- Raspberry PI
- Meshtastic hardware compatible


SOFTWARE
- Python
- pip
- flask
- pahno-mqtt
- meshtastic
- requests



INSTALLATION

sudo apt update
sudo apt install python3-pip
pip3 install flask paho-mqtt meshtastic requests
git clone https://github.com/arkanet/ecowitt-meshtastic.git
cd ./ecowitt-meshtastic/


EDITABLE VARIANTS

In this file you can edit WEB_PORT, MQTT_PORT, MQTT_TOPIC, MQTT_BROKER

nano ./python/server.py

For LOCATION using pluscode system copying the 2nd part of url (ex: https://plus.codes/8FHJVFRR+3W >> the LOCATION will be 8FHJVFRR+3W) [ref https://plus.codes/]


In this file you can edit SERVER_API and CHANNEL_INDEX to be able to choose through which channel to send the report (in meshtastic the channel primary is 0 and the secondary are from 1 to 7)

nano ./send_meshtastic_once.py

chmod +x && ./stylesheets.sh


You can make the service autonomous at Raspberry startup by creating a service

sudo cp ~/ecowitt-meshtastic/ecowitt.service /etc/systemd/system/ecowitt.service
sudo systemctl daemon-reload
sudo systemctl enable ecowitt.service
sudo systemctl start ecowitt.service


To automate the process of sending reports to the Meshtastic system, you need to add a configuration line to the cron system

0 */6 * * * /usr/bin/python3 /home/pi/ecowitt-meshtastic/send_meshtastic_once.py >> /home/pi/ecowitt-meshtastic/cron.log 2>&1

crontab -e


Ok! Now you can have a new dashboard web for your EcoWitt weather station and an automatized system to send a simple report on Meshtastic system!