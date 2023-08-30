import pymel.internal
import sys
path = 'G:/DOCUMENTS/JOB/@PERSO/Tools/PyMaya'
if path not in sys.path:
    sys.path.insert(0, path)

import maya.cmds as cmds
from maya.api import OpenMaya as om2

import unload
import pymaya.core.general as pm
import pymaya.core.api as api
import pymaya.core.utilities as utils

from pymaya.core.api import DataType as dt


node = pm.createNode('transform', name='chatte', _isDag=True)

mod = api.DGModifier()

mfnCmpd1 = node.createAttr('compoundA', attrType=pm.AttrType.COMPOUND, _modifier=mod)
mfnCmpd2 = node.createAttr('compoundB', attrType=pm.AttrType.COMPOUND, _modifier=mod)

float1 = node.createAttr('singleFloatValue', 'fv', attrType=pm.AttrType.NUMERIC, dataType=dt.FLOAT, keyable=True, min=0, parent=mfnCmpd1, _modifier=mod)
float3 = node.createAttr('tripleFloatValue', 'fv3', attrType=pm.AttrType.NUMERIC, dataType=dt.FLOAT3, keyable=True, min=(-1, -1, -1), max=(1, 1, 1), parent=mfnCmpd1, _modifier=mod)

boolean = node.createAttr('trueOrFalse', 'tof', attrType=pm.AttrType.NUMERIC, dataType=dt.BOOL, keyable=True, parent=mfnCmpd2, _modifier=mod)
path = node.createAttr('imagePath', 'imgP', attrType=pm.AttrType.STRING, defaultValue='D:\\', asFilename=True, parent=mfnCmpd2, _modifier=mod)
message = node.createAttr('messageAttr', 'mattr', attrType=pm.AttrType.MESSAGE, parent=mfnCmpd2, _modifier=mod)


node.addMfnAttribute(mfnCmpd1, _modifier=mod)
node.addMfnAttribute(mfnCmpd2, _modifier=mod)

angle = node.createAttr('angle', 'angle', attrType=pm.AttrType.UNIT, dataType=dt.ANGLE, keyable=True, min=dt.toAngle(-45), max=dt.toAngle(45), parent=mfnCmpd1, _modifier=mod)
color = node.createAttr('backgroundColor', 'bgCol', attrType=pm.AttrType.NUMERIC, dataType=dt.COLOR, keyable=True, parent=mfnCmpd2, _modifier=mod)


mod.doIt()

pm.select(node)