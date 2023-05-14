import maya.cmds as cmds
from maya.api import OpenMaya as om2

import unload

import pymaya.core.general as pm
import pymaya.core.api as api
import pymaya.core.utilities as utils


class UserTransform(pm.Transform):
    NODE_TYPE = 'UserTransform'

    @classmethod
    def _isVirtual(cls, obj):
        fn = om2.MFnDependencyNode(obj)
        if fn.hasAttribute('node_type'):
            plug = fn.findPlug('node_type', False)
            if plug.asString() == cls.NODE_TYPE:
                return True
        return False

    @classmethod
    def _preCreateVirtual(cls, name):
        kwargs = {'name': name}

        return kwargs, {}

    @classmethod
    def _createVirtual(cls, **kwargs):
        name = kwargs['name']
        name = cmds.createNode('transform', name=name)
        return name

    @classmethod
    def _postCreateVirtual(cls, name, **kwargs):
        sel =  om2.MSelectionList()
        sel.add(name)
        mobj = sel.getDependNode(0)
        fn = om2.MFnDependencyNode(mobj)

        attr = pm.AttrCreator('node_type', attrType=pm.AttrCreator.STRING, defaultValue=cls.NODE_TYPE)
        fn.addAttribute(attr.object())


class UserTransformSub(UserTransform):
    NODE_TYPE = 'UserTransformSub'

pm.UserSubclassManager.register(UserTransform)
pm.UserSubclassManager.register(UserTransformSub)