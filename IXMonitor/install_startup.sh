# Installation file to make the Camera Robot start on boot.
# This will add the ixmonitor start on boot to SystemD on Stretch

sudo cp ixmonitor.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/ixmonitor.service
sudo systemctl daemon-reload
sudo systemctl enable ixmonitor.service
