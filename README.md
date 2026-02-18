EcoWitt local web dashboard with meshtastic push service over protobuf

These two scripts will create a small local web server for displaying minimal information from your EcoWitt weather station.
The data will be retrieved directly from the station's push notifications and made available for sending as a 4-line text message over the meshtastic network via a channel configured within the script.
To function correctly, you will need to configure the custom section of the weather station software by entering the Raspberry Pi's IP address, the "/ecowitt" path for sending data, the server port (8080), and the upload time.
The web server will be available at http://Raspberry_IP:8080/

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

nano ./python/server.py

for LOCATION using pluscode system copying the 2nd part of url (ex: https://plus.codes/8FHJVFRR+3W >> the LOCATION will be 8FHJVFRR+3W) [ref https://plus.codes/]

in this file you can edit WEB_PORT, MQTT_PORT, MQTT_TOPIC, MQTT_BROKER


nano ./send_meshtastic_once.py

in this file you can edit SERVER_API and CHANNEL_INDEX to be able to choose through which channel to send the report (in meshtastic the channel primary is 0 and the secondary are from 1 to 7)
