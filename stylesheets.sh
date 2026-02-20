#!/bin/sh
cd ~/ecowitt-meshtastic
mkdir -p vendor/bootstrap vendor/chartjs vendor/fontawesome/css vendor/fontawesome/webfonts

curl -L -o vendor/bootstrap/bootstrap.min.css https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
curl -L -o vendor/bootstrap/bootstrap.bundle.min.js https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js

curl -L -o vendor/chartjs/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js

curl -L -o vendor/fontawesome/css/all.min.css https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css
curl -L -o vendor/fontawesome/webfonts/fa-solid-900.woff2 https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-solid-900.woff2
curl -L -o vendor/fontawesome/webfonts/fa-regular-400.woff2 https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-regular-400.woff2
curl -L -o vendor/fontawesome/webfonts/fa-brands-400.woff2 https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/fa-brands-400.woff2