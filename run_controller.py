#!/usr/bin/env python3
"""OS-Ken 4.x removed osken-manager; use the public AppManager API."""
import os
os.environ['OSKEN_HUB_TYPE'] = 'eventlet'
os.environ['EVENTLET_NO_GREENDNS'] = 'yes'
import eventlet
eventlet.monkey_patch()
import logging
from os_ken import cfg
from os_ken.base import app_manager
from os_ken.controller import controller as of_controller  # registers OF options

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    cfg.CONF(args=[], project='jackfruit')
    cfg.CONF.set_override('ofp_listen_host', '127.0.0.1')
    cfg.CONF.set_override('ofp_tcp_listen_port', 6653)
    try:
        app_manager.AppManager.run_apps(['controller'])
    except KeyboardInterrupt:
        pass
