#!/usr/bin/env python3
import json
import random
import unittest
import time
import capnp

import cereal.messaging as messaging
from cereal.services import service_list
from openpilot.common.params import Params
from openpilot.common.transformations.coordinates import ecef2geodetic

from openpilot.selfdrive.manager.process_config import managed_processes


class TestLocationdProc(unittest.TestCase):
  LLD_MSGS = ['gnssMeasurements', 'cameraOdometry', 'carState', 'liveCalibration',
              'accelerometer', 'gyroscope', 'magnetometer']

  def setUp(self):
    random.seed(123489234)

    self.pm = messaging.PubMaster(self.LLD_MSGS)

    self.params = Params()
    self.params.put_bool("UbloxAvailable", True)
    managed_processes['locationd'].prepare()
    managed_processes['locationd'].start()

  def tearDown(self):
    managed_processes['locationd'].stop()

  def get_msg(self, name, t):
    try:
      msg = messaging.new_message(name)
    except capnp.lib.capnp.KjException:
      msg = messaging.new_message(name, 0)
    if name == "gnssMeasurements":
      msg.gnssMeasurements.measTime = t
      msg.gnssMeasurements.positionECEF.value = [self.x , self.y, self.z]
      msg.gnssMeasurements.positionECEF.std = [0,0,0]
      msg.gnssMeasurements.positionECEF.valid = True
      msg.gnssMeasurements.velocityECEF.value = []
      msg.gnssMeasurements.velocityECEF.std = [0,0,0]
      msg.gnssMeasurements.velocityECEF.valid = True
    elif name == 'cameraOdometry':
      msg.cameraOdometry.rot = [0.0, 0.0, 0.0]
      msg.cameraOdometry.rotStd = [0.0, 0.0, 0.0]
      msg.cameraOdometry.trans = [0.0, 0.0, 0.0]
      msg.cameraOdometry.transStd = [0.0, 0.0, 0.0]
    msg.logMonoTime = t
    return msg

  def test_params_gps(self):
    self.params.remove('LastGPSPosition')

    self.x = -2710700 + (random.random() * 1e5)
    self.y = -4280600 + (random.random() * 1e5)
    self.z = 3850300 + (random.random() * 1e5)
    self.lat, self.lon, self.alt = ecef2geodetic([self.x, self.y, self.z])

    # get fake messages at the correct frequency, listed in services.py
    msgs = []
    for sec in range(65):
      for name in self.LLD_MSGS:
        for j in range(int(service_list[name].frequency)):
          msgs.append(self.get_msg(name, int((sec + j / service_list[name].frequency) * 1e9)))

    for msg in sorted(msgs, key=lambda x: x.logMonoTime):
      self.pm.send(msg.which(), msg)
      if msg.which() == "cameraOdometry":
        self.pm.wait_for_readers_to_update(msg.which(), 0.1)
    time.sleep(1)  # wait for async params write

    lastGPS = json.loads(self.params.get('LastGPSPosition'))
    self.assertAlmostEqual(lastGPS['latitude'], self.lat, places=3)
    self.assertAlmostEqual(lastGPS['longitude'], self.lon, places=3)
    self.assertAlmostEqual(lastGPS['altitude'], self.alt, places=3)


if __name__ == "__main__":
  unittest.main()
