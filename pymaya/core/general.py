from maya.api import OpenMaya as om2
import maya.cmds as cmds

import pymaya.core.api as api
import pymaya.core.utilities as utils
from abc import ABCMeta, abstractmethod


class PyObjectBuilder(object):
    """
    Abstract PyObject Builder
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def create(self, *args, **kwargs):
        """
        possible inputs:
        string > pass intoApiObject then back into PyObject
        tuple (MDagPath, MObject) > Component
        MDagPath > DagNode
        MObject > DependNode
        MPlug > Attribute
        """
        pass

    @utils.timeit(name='FromString', log=True, verbose=False)
    def _fromString(self, *args, **kwargs):
        """
        Attempts to convert a string into and api object 
        """
        if not len(args):
            return None

        return api.toApiObject(args[0])

    @utils.timeit(name='ProcessInput', log=True, verbose=False)
    def _processInput(self, *args, **kwargs):
        if not len(args):
            raise ValueError('create method needs at least one argument')

        obj = args[0]
        out = {}
        if isinstance(obj, (unicode, str)):
            obj = self._fromString(obj)
            if obj is None:
                raise ValueError('Unable to find API object for {}'.format(args[0]))

        if isinstance(obj, om2.MObject):
            out['MObjectHandle'] = om2.MObjectHandle(obj)
        elif isinstance(obj, om2.MObjectHandle):
            out['MObjectHandle'] = obj
        elif isinstance(obj, om2.MPlug):
            out['MPlug'] = obj
        elif isinstance(obj, om2.MDagPath):
            out['MDagPath'] = obj
        elif isinstance(obj, tuple):
            if isinstance(obj[0], om2.MDagPath) and (obj[1], om2.MObject):
                out['MDagPath'] = obj[0]
                out['MObjectHandle'] = om2.MObjectHandle(obj[1])
            else:
                raise ValueError('Unrecognized tuple composition')
        else:
            raise ValueError('Unrecognized input {} of type {}'.format(obj, type(obj)))

        return out


class AttributeBuilder(PyObjectBuilder):

    def create(self, *args, **kwargs):
        super(AttributeBuilder, self).create(*args, **kwargs)
        apiDict = self._processInput(*args, **kwargs)
        return Attribute(**apiDict)


class ComponentBuilder(PyObjectBuilder):

    def create(self, *args, **kwargs):
        super(ComponentBuilder, self).create(*args, **kwargs)
        apiDict = self._processInput(*args, **kwargs)
        return Component(**apiDict)


class DependNodeBuilder(PyObjectBuilder):

    def create(self, *args, **kwargs):
        super(DependNodeBuilder, self).create(*args, **kwargs)
        apiDict = self._processInput(*args, **kwargs)

        if 'MDagPath' in apiDict:
            return DagNode(**apiDict)
        elif 'MObjectHandle' in apiDict:
            return DependNode(**apiDict)

    @utils.timeit(name='ProcessInputNode', log=True, verbose=False)
    def _processInput(self, *args, **kwargs):
        if not len(args):
            raise ValueError('create method needs at least one argument')

        obj = args[0]
        out = {}
        if isinstance(obj, (unicode, str)):
            try:
                sel = om2.MSelectionList()
                sel.add(obj)
            except RuntimeError:
                raise ValueError('Unable to find API object for {}'.format(args[0]))
            else:
                obj = sel.getDependNode(0)

        if isinstance(obj, om2.MObject):
            out['MObjectHandle'] = om2.MObjectHandle(obj)
        elif isinstance(obj, om2.MObjectHandle):
            out['MObjectHandle'] = obj
        else:
            raise ValueError('DependNodeBuilder.create only accepts string, MObject or MObjectHandle')

        if obj.hasFn(om2.MFn.kDagNode):
            out['MDagPath'] = om2.MDagPath.getAPathTo(obj)
        return out


def _processAttrInput(attr):
    if isinstance(attr, (unicode, str)):
        mplug = api.toApiObject(attr)
    elif isinstance(attr, Attribute):
        mplug = attr.apimplug()
    else:
        raise ValueError('attr must be either of type string or Attribute. got {} instead'.format(type(attr)))
    return mplug


@api.ApiUndo
def setAttr(attr, *args, **kwargs):
    # If an MModifier is provided, it'll be up to the user to do the doIt call and apiUndo commit
    if '_modifier' in kwargs:
        modifier = kwargs.pop('_modifier')
        doIt = False
    else:
        modifier = api.DGModifier()
        doIt = True

    # If a DataType is provided, we won't have to look for it
    datatype = kwargs.pop('_datatype', None)

    # If no args is specified, just pass kwargs to the setAttr command
    if not len(args):
        if isinstance(attr, Attribute):
            attr = attr.name(fullDagPath=True)
        cmds.setAttr(attr, **kwargs)
        return None
    # if there's a single arg, use it as the value, else use the whole list as the value
    elif len(args) == 1:
        value = args[0]
    else:
        value = args

    # Get the MPlug for the given attribute
    mplug = _processAttrInput(attr)

    # Process Value
    if datatype is None:
        datatype = api.DataType.fromMObject(mplug.attribute())

    # Set the Value
    modifier.setPlugValue(mplug, value, datatype=datatype)
    if doIt:
        modifier.doIt()
        return modifier
    else:
        return None


def getAttr(attr, **kwargs):
    plug = _processAttrInput(attr)
    time = kwargs.pop('time', om2.MDGContext.kNormal)
    asStr = kwargs.pop('asString', False)
    datatype = kwargs.pop('_datatype', None)
    if not len(kwargs):
        return api.getPlugValue(plug, attrType=datatype, asString=asStr, context=time)

@api.ApiUndo
def connectAttr(sAttr, dAttr, force=False, nextAvailable=False, **kwargs):
    if '_modifier' in kwargs:
        modifier = kwargs.pop('_modifier')
        doIt = False
    else:
        modifier = api.DGModifier()
        doIt = True

    sPlug = _processAttrInput(sAttr)
    dPlug = _processAttrInput(dAttr)
    modifier.connect(sPlug=sPlug, dPlug=dPlug, force=force, nextAvailable=nextAvailable)

    if doIt:
        modifier.doIt()
        return modifier
    else:
        return None


@api.ApiUndo
def disconnectAttr(*args, **kwargs):
    if '_modifier' in kwargs:
        modifier = kwargs.pop('_modifier')
        doIt = False
    else:
        modifier = api.DGModifier()
        doIt = True

    plugs = [_processAttrInput(attr) for attr in args]

    modifier.disconnect(*plugs)

    if doIt:
        modifier.doIt()
        return modifier
    else:
        return None
    

class PyObject(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, *args, **kwargs):
        self.__apiInput__ = kwargs

    @abstractmethod
    def apimfn(self):
        pass

    @abstractmethod
    def apimobject(self):
        pass

    @abstractmethod
    def name(self, fullDagPath=False):
        pass


class Attribute(PyObject):

    def __init__(self, *args, **kwargs):
        """
        :param MPlug: om.MPlug
        
        # Optional #
        :param node: DependNode         # If you can pass this here directly, it won't have to look for it later
        """
        super(Attribute, self).__init__(*args, **kwargs)
        self._node = kwargs.get('node', None)
        self._attrType = None

    def __getitem__(self, item):
        return Attribute(MPlug=self.apimplug().elementByLogicalIndex(item), node=self._node)

    # API RELATED METHODS
    def apimfn(self):
        return om2.MFnAttribute(self.apimobject())

    def apimobject(self):
        return self.apimplug().attribute()

    def apimplug(self):
        return self.__apiInput__['MPlug']

    def apidagpath(self):
        """
        get dag path from node
        """
        node = self.node()
        if isinstance(node, DagNode):
            return self.node().apidagpath()

    def attrType(self):
        if self._attrType:
            self._attrType = api.DataType.fromMObject(self.apimobject())
        return self._attrType

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False, includeNode=True, alias=False, fullAttrPath=False, longNames=True):
        plugName = self.apimplug().partialName(includeNodeName=includeNode, useAlias=alias,
                                               useFullAttributePath=fullAttrPath, useLongNames=longNames)
        if not includeNode:
            return plugName

        node = self.node()
        return '{}.{}'.format(node.name(fullDagPath=fullDagPath), plugName)

    def node(self):
        if self._node is None:
            builder = DependNodeBuilder()
            self._node = builder.create(self.apimplug().node())
        return self._node

    def set(self, *args, **kwargs):
        if '_datatype' not in kwargs:
            kwargs['_datatype'] = self._attrType
        return setAttr(self, *args, **kwargs)

    def get(self, **kwargs):
        if '_datatype' not in kwargs:
            kwargs['_datatype'] = self._attrType
        return getAttr(self, **kwargs)



class Component(PyObject):

    def __init__(self, *args, **kwargs):
        super(Component, self).__init__(*args, **kwargs)


class DependNode(PyObject):
    attributeBuilder = AttributeBuilder()
    componentBuilder = ComponentBuilder()

    def __init__(self, *args, **kwargs):
        super(DependNode, self).__init__(*args, **kwargs)

    def __getattr__(self, item):
        if self.apimfn().hasAttribute(item):
            attr = Attribute(MPlug=self.apimfn().findPlug(item, False), node=self)
            setattr(self, item, attr)
            return attr
        else:
            raise AttributeError('Cannot find attribute {} on {}'.format(item, self.name()))

    # API RELATED METHODS
    def apimobject(self):
        return self.__apiInput__['MObjectHandle'].object()

    def apimfn(self):
        return om2.MFnDependencyNode(self.apimobject())

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False):
        return self.apimfn().name()


class DagNode(DependNode):
    def __init__(self, *args, **kwargs):
        super(DagNode, self).__init__(*args, **kwargs)

    # API RELATED METHODS
    def apimfn(self):
        return om2.MFnDagNode(self.apidagpath())

    def apimobject(self):
        if 'MObjectHandle' in self.__apiInput__:
            return self.__apiInput__['MObjectHandle'].object()
        else:
            return om2.MObject(self.apidagpath())

    def apidagpath(self):
        return self.__apiInput__['MDagPath']

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False):
        if fullDagPath:
            return self.apimfn().fullPathName()
        return self.apimfn().name()