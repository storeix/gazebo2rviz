#!/usr/bin/env python

# TODO
# - delete marker if object vanishes from gazebo

import os
import xml.etree.ElementTree as ET
import re

import rospy
import tf
from PyKDL import Frame, Rotation, Vector
from geometry_msgs.msg import Pose
import tf_conversions.posemath as pm
from gazebo_msgs.msg import ModelStates
from visualization_msgs.msg import Marker

from gazebo2rviz.model_names import *


lastUpdateTime = None
updatePeriod = 5
markerPub = None
modelDict = {} # modelName -> [(tfName1, meshPose1, meshPath1), ...]
modelsPath = os.path.expanduser('~/.gazebo/models/')


def poseRPYList2Pose(poseRPYList):
  poseValues = [float(val) for val in poseRPYList]
  pose = Frame(Rotation.RPY(poseValues[3], poseValues[4], poseValues[5]),
               Vector(poseValues[0], poseValues[1], poseValues[2]))
  poseMsg = pm.toMsg(pose)
  #print(poseMsg)
  return poseMsg


def loadModelFromSDF(modelName, modelNamePrefix = '', modelTfName = ''):
  rospy.loginfo('Loading model: modelName=%s modelNamePrefix=%s modelTfName=%s' % (modelName, modelNamePrefix, modelTfName))
  if not modelTfName:
    modelTfName = modelName
  model = []
  modelTree = ET.parse(modelsPath + os.sep + modelName + os.sep + 'model.sdf')
  for linkTag in modelTree.iter('link'):
    rawLinkName = linkTag.attrib['name']
    if isBaseLinkName(modelName, rawLinkName):
      linkName = modelTfName
    else:
      linkName = modelTfName + joinString + rawLinkName
    for visualTag in linkTag.iter('visual'):
      meshPose = Pose()
      for poseTag in visualTag.iter('pose'):
        meshPoseElements = poseTag.text.split()
        meshPose = poseRPYList2Pose(meshPoseElements)
      for meshTag in visualTag.iter('mesh'):
        for uriTag in meshTag.findall('uri'):
          meshPath = uriTag.text.replace('model://', 'file://' + modelsPath)
          tfName = modelNamePrefix + linkName
          modelPart = (tfName, meshPose, meshPath)
          rospy.loginfo('Found: tfName=%s meshPath=%s' % (tfName, meshPath))
          model.append(modelPart)

  for includeTag in modelTree.iter('include'):
    uriTag = includeTag.findall('uri')[0]
    includedModelName = uriTag.text.replace('model://', '')
    sdfPath = uriTag.text.replace('model://', 'file://' + modelsPath)
    nameTagList = includeTag.findall('name')
    if nameTagList:
      includedTfName = nameTagList[0].text
    else:
      includedTfName = includedModelName
    prefix = modelNamePrefix + modelTfName + joinString
    model.extend(loadModelFromSDF(includedModelName, prefix, includedTfName))

  return model


def on_model_states_msg(modelStatesMsg):
  global lastUpdateTime
  sinceLastUpdateDuration = rospy.get_rostime() - lastUpdateTime
  if sinceLastUpdateDuration.to_sec() < updatePeriod:
    return
  lastUpdateTime = rospy.get_rostime()

  protoMarkerMsg = Marker()
  protoMarkerMsg.header.stamp = rospy.get_rostime()
  protoMarkerMsg.frame_locked = True
  protoMarkerMsg.id = 0
  protoMarkerMsg.type = Marker.MESH_RESOURCE
  protoMarkerMsg.action = Marker.ADD
  protoMarkerMsg.mesh_use_embedded_materials = True
  protoMarkerMsg.color.a = 0.0
  protoMarkerMsg.color.r = 0.0
  protoMarkerMsg.color.g = 0.0
  protoMarkerMsg.color.b = 0.0
  protoMarkerMsg.scale.x = 1.0
  protoMarkerMsg.scale.y = 1.0
  protoMarkerMsg.scale.z = 1.0

  for (index, name) in enumerate(modelStatesMsg.name):
    print('%d: name=%s\n' % (index, name))
    if not name in modelDict:
      modelName = re.sub('_[0-9]*$', '', name)
      modelDict[name] = loadModelFromSDF(modelName, '', name)

    for modelPart in modelDict[name]:
      tfName, meshPose, meshPath = modelPart
      markerMsg = protoMarkerMsg
      markerMsg.header.frame_id = tfName
      markerMsg.ns = tfName
      markerMsg.mesh_resource = meshPath
      markerMsg.pose = meshPose
      print('Publishing:\n' + str(markerMsg))
      markerPub.publish(markerMsg)


def main():
  rospy.init_node('gazebo2marker')

  global submodelsToBeIgnored
  submodelsToBeIgnored = rospy.get_param('~ignore_submodels_of', '').split(';')
  rospy.loginfo('Ignoring submodels of: ' + str(submodelsToBeIgnored))

  global lastUpdateTime
  lastUpdateTime = rospy.get_rostime()
  modelStatesSub = rospy.Subscriber('gazebo/model_states', ModelStates, on_model_states_msg)

  global markerPub
  markerPub = rospy.Publisher('/visualization_marker', Marker)

  rospy.loginfo('Spinning')
  rospy.spin()

if __name__ == '__main__':
  main()
