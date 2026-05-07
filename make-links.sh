#!/bin/bash
#Make darktable symbolic links
sudo ln -s /opt/darktable/share/applications/org.darktable.darktable.desktop /usr/local/share/applications/org.darktable.darktable.desktop
sudo ln -s /opt/darktable/share/icons/hicolor/scalable/apps/darktable.svg /usr/share/pixmaps/darktable.svg
sudo ln -s /opt/darktable/bin/darktable /usr/local/bin/darktable
sudo ln -s /opt/darktable/bin/darktable-cli /usr/local/bin/darktable-cli
sudo ln -s /opt/darktable/bin/darktable-cltest /usr/local/bin/darktable-cltest
sudo ln -s /opt/darktable/bin/darktable-cmstest /usr/local/bin/darktable-cmstest
sudo ln -s /opt/darktable/bin/darktable-rs-identify /usr/local/bin/darktable-rs-identify
