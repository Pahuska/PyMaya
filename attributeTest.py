import maya.cmds as cmds
from maya.api import OpenMaya as om2

import unload
import pymaya.core.general as pm
import pymaya.core.api as api
import pymaya.core.utilities as utils

from pymaya.core.api import DataType as dt


node = pm.createNode('transform', name='chatte', _isDag=True)

mod = api.DGModifier()

mfnCmpd1 = node.createAttr('compoundA', attrType=pm.AttrCreator.COMPOUND, _modifier=mod)
mfnCmpd2 = node.createAttr('compoundB', attrType=pm.AttrCreator.COMPOUND, _modifier=mod)

float1 = node.createAttr('singleFloatValue', 'fv', attrType=pm.AttrCreator.NUMERIC, dataType=dt.FLOAT, keyable=True, min=0, parent=mfnCmpd1, _modifier=mod)
float3 = node.createAttr('tripleFloatValue', 'fv3', attrType=pm.AttrCreator.NUMERIC, dataType=dt.POINT, keyable=True, min=(-1, -1, -1), max=(1, 1, 1), parent=mfnCmpd1, _modifier=mod)

boolean = node.createAttr('trueOrFalse', 'tof', attrType=pm.AttrCreator.NUMERIC, dataType=dt.BOOL, keyable=True, parent=mfnCmpd2, _modifier=mod)
path = node.createAttr('imagePath', 'imgP', attrType=pm.AttrCreator.STRING, defaultValue='D:\\', asFilename=True, parent=mfnCmpd2, _modifier=mod)


node.addMfnAttribute(mfnCmpd1, _modifier=mod)
node.addMfnAttribute(mfnCmpd2, _modifier=mod)

angle = node.createAttr('angle', 'angle', attrType=pm.AttrCreator.UNIT, dataType=dt.ANGLE, keyable=True, min=dt.toAngle(-45), max=dt.toAngle(45), parent=mfnCmpd1, _modifier=mod)
color = node.createAttr('backgroundColor', 'bgCol', attrType=pm.AttrCreator.NUMERIC, dataType=dt.COLOR, keyable=True, parent=mfnCmpd2, _modifier=mod)


mod.doIt()

pm.select(node)