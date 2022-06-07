from functools import partial
import inspect

from maya.api import OpenMaya as om2
import maya.cmds as cmds

from pymaya.py2x3 import _enum, xrange, add_metaclass
import pymaya.core.api as api
import pymaya.core.utilities as utils
from abc import ABCMeta, abstractmethod


@add_metaclass(ABCMeta)
class PyObjectBuilder(object):
    """
    Abstract PyObject Builder
    """

    @classmethod
    @abstractmethod
    def create(cls, *args, **kwargs):
        """
        possible inputs:
        string > pass intoApiObject then back into PyObject
        tuple (MDagPath, MObject) > Component
        MDagPath > DagNode
        MObject > DependNode
        MPlug > Attribute
        """
        pass

    @classmethod
    @utils.timeit(name='FromString', log=True, verbose=False)
    def _fromString(cls, *args, **kwargs):
        """
        Attempts to convert a string into and api object 
        """
        if not len(args):
            return None

        return api.toApiObject(args[0])

    @classmethod
    @utils.timeit(name='ProcessInput', log=True, verbose=False)
    def _processInput(cls, *args, **kwargs):
        if not len(args) and not len(kwargs):
            raise ValueError('create method needs at least one keyword or non-keyword argument')

        if len(args):
            obj = args[0]
            out = {}
            if isinstance(obj, (unicode, str)):
                obj = cls._fromString(obj)
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
        else:
            return kwargs


# --- OBSOLETE --- #
class AttributeBuilder(PyObjectBuilder):

    @classmethod
    def create(cls, *args, **kwargs):
        super(AttributeBuilder, cls).create(*args, **kwargs)
        apiDict = cls._processInput(*args, **kwargs)
        return Attribute(**apiDict)


class ComponentBuilder(PyObjectBuilder):

    @classmethod
    def create(cls, *args, **kwargs):
        super(ComponentBuilder, cls).create(*args, **kwargs)
        apiDict = cls._processInput(*args, **kwargs)
        return Component(**apiDict)


class DependNodeBuilder(PyObjectBuilder):

    @classmethod
    def create(cls, *args, **kwargs):
        super(DependNodeBuilder, cls).create(*args, **kwargs)
        apiDict = cls._processInput(*args, **kwargs)

        if 'MDagPath' in apiDict:
            dag = apiDict['MDagPath']
            if dag.hasFn(om2.MFn.kTransform):
                return Transform(**apiDict)
            elif dag.hasFn(om2.MFn.kMesh):
                return Mesh(**apiDict)
            elif dag.hasFn(om2.MFn.kNurbsCurve):
                return NurbsCurve(**apiDict)
            elif dag.hasFn(om2.MFn.kNurbsSurface):
                return NurbsSurface(**apiDict)
            elif dag.hasFn(om2.MFn.kLattice):
                return LatticeShape(**apiDict)
            else:
                return DagNode(**apiDict)
        elif 'MObjectHandle' in apiDict:
            return DependNode(**apiDict)

    @classmethod
    @utils.timeit(name='ProcessInputNode', log=True, verbose=False)
    def _processInput(cls, *args, **kwargs):
        if not len(args) and not len(kwargs):
            raise ValueError('create method needs at least one keyword or non-keyword argument')

        if len(args):
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
                raise ValueError('DependNodeBuilder.create *args only accepts string, MObject or MObjectHandle')

            if obj.hasFn(om2.MFn.kDagNode):
                out['MDagPath'] = om2.MDagPath.getAPathTo(obj)
            return out
        else:
            if 'MDagPath' not in kwargs:
                obj = kwargs['MObjectHandle'].object()
                if obj.hasFn(om2.MFn.kDagNode):
                    kwargs['MDagPath'] = om2.MDagPath.getAPathTo(obj)
            return kwargs
# ---------------- #


class PyObjectFactory(object):
    DEPENDNODE = om2.MFn.kDependencyNode
    DAGNODE = om2.MFn.kDagNode
    ATTRIBUTE = om2.MFn.kAttribute
    COMPONENT = om2.MFn.kComponent

    def __new__(cls, *args, **kwargs):
        """
        Creates a PyObject instance that corresponds to the type of the object passed
        
        :param args: The object that will be translated as a PyObject (Optional)
        :type args: str, MDagPath, MObject, MObjectHandle, MPlug, tuple(MDagPath, MObject)
        
        :keyword MDagPath: an MDagPath to an object to be translated (Optional)
        :type MDagPath: MDagPath
        :keyword MObject: an MObject that represents the object to be translated (Optional)
        :type MObject: MObject
        :keyword MObjectHandle: an MObjectHandle that represents the object to be translated (Optional)
        :type MObjectHandle: MObjectHandle
        :return: The PyObject subclass that represent the given object
        :rtype: PyObject
        """
        assert len(args) <= 1, 'PyObjectFactory does not take more than 1 non-keyword parameter'

        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, (str, unicode)):
                return PyObjectFactory(api.toApiObject(arg), **kwargs)
            else:
                dic = {}
                if isinstance(arg, (tuple, list)):
                    assert len(arg) == 2, 'PyObjectFactory : Invalid tuple length'
                    assert isinstance(arg[0], om2.MDagPath) and isinstance(arg[1], (om2.MObject, om2.MObjectHandle)), \
                        'PyObjectFactory : Invalid tuple composition'

                    for obj in arg:
                        dic[obj.__class__.__name__] = obj
                else:
                    assert isinstance(arg, (om2.MDagPath, om2.MObjectHandle, om2.MObject, om2.MPlug)), \
                        'Invalid param type {}'.format(type(arg))

                    dic[arg.__class__.__name__] = arg
                dic.update(kwargs)
                return PyObjectFactory(**dic)
        else:
            assert any(k in ('MDagPath', 'MObject', 'MObjectHandle', 'MPlug') for k in kwargs), \
                'PyObjectFactory keyword parameter needs at least one of : (MDagPath, MObject, MObjectHandle, MPlug)'

            objectType = kwargs.pop('objectType', None)
            if 'MPlug' in kwargs:
                refObj = kwargs['MPlug'].attribute()
                mobj = refObj
            elif 'MObjectHandle' in kwargs:
                refObj = kwargs['MObjectHandle'].object()
                mobj = refObj
            else:
                mobj = kwargs.pop('MObject', None)
                if mobj is not None:
                    refObj = mobj
                    if 'MDagPath' not in kwargs and refObj.hasFn(om2.MFn.kDagNode):
                        kwargs['MDagPath'] = om2.MDagPath.getAPathTo(refObj)
                else:
                    refObj = kwargs['MDagPath']
                    mobj = refObj.node()

            if 'MObjectHandle' not in kwargs:
                kwargs['MObjectHandle'] = om2.MObjectHandle(mobj)

            _class = cls.classFromApiObject(refObj, typeScope=objectType)
            assert 'MObjectHandle' in kwargs, 'DEBUG : MObjectHandle missing from kwargs ' \
                                              '\nclass:<{}>\nkwargs:{}'.format(_class, kwargs)

            return _class(**kwargs)

    @classmethod
    def fromMSelectionList(cls, sel, filter=None):
        it = om2.MItSelectionList(sel)
        result = []
        if filter is not None:
            it.setFilter(filter)
        while not it.isDone():
            iType = it.itemType()
            if iType == it.kDNselectionItem:
                mobj = it.getDependNode()
                # _class = cls.classFromApiObject(mobj, cls.DEPENDNODE)
                # kwargs = {'MObjectHandle': om2.MObjectHandle(mobj)}
                instance = cls(MObjectHandle=om2.MObjectHandle(mobj), objectType=cls.DEPENDNODE)
                result.append(instance)
            elif iType == it.kDagSelectionItem:
                if it.hasComponents():
                    mdag, mobj = it.getComponent()
                    # _class = cls.classFromApiObject(mobj, cls.COMPONENT)
                    # kwargs = {'MDagPath': mdag, 'MObjectHandle': om2.MObjectHandle(mobj)}
                    instance = cls(MDagPath=mdag, MObjectHandle=om2.MObjectHandle(mobj), objectType=cls.COMPONENT)
                    result.append(instance)
                else:
                    mdag = it.getDagPath()
                    # _class = cls.classFromApiObject(mdag, cls.DAGNODE)
                    # kwargs = {'MDagPath': mdag}
                    instance = cls(MDagPath=mdag, MObjectHandle=om2.MObjectHandle(mdag.node()), objectType=cls.DAGNODE)
                    result.append(instance)
            elif iType == it.kPlugSelectionItem:
                mobj = it.getPlug()
                # _class = cls.classFromApiObject(mobj, cls.ATTRIBUTE)
                # kwargs = {'MObjectHandle': om2.MObjectHandle(mobj)}
                instance = cls(MObjectHandle=om2.MObjectHandle(mobj), objectType=cls.ATTRIBUTE)
                result.append(instance)
            else:
                raise TypeError('Couldn\'t find PyObject class for {}'.format(it.getStrings()))
            # result.append(_class(**kwargs))
            it.next()
        return result

    @classmethod
    def _dgTypes(cls):
        return {om2.MFn.kDependencyNode: DependNode,
                om2.MFn.kSet: ObjectSet}

    @classmethod
    def _dagTypes(cls):
        return {om2.MFn.kDagNode: DagNode,
                om2.MFn.kTransform: Transform,
                om2.MFn.kJoint: Joint,
                om2.MFn.kMesh: Mesh,
                om2.MFn.kNurbsCurve: NurbsCurve,
                om2.MFn.kNurbsSurface: NurbsSurface,
                om2.MFn.kLattice: LatticeShape}

    @classmethod
    def _compTypes(cls):
        return {om2.MFn.kMeshVertComponent: MeshVertex,
                om2.MFn.kMeshEdgeComponent: MeshEdge,
                om2.MFn.kMeshPolygonComponent: MeshFace,
                om2.MFn.kCurveCVComponent: NurbsCurveCV,
                om2.MFn.kSurfaceCVComponent: NurbsSurfaceCV,
                om2.MFn.kLatticeComponent: LatticePoint}

    @classmethod
    def _plugTypes(cls):
        return {om2.MFn.kNumericAttribute: NumericAttribute,
                om2.MFn.kUnitAttribute: UnitAttribute,
                om2.MFn.kCompoundAttribute: CompoundAttribute}

    @classmethod
    def _getPlugType(cls, apiObj):
        pTypes = cls._plugTypes()
        if apiObj.apiType == om2.MFn.kCompoundAttribute:
            return CompoundAttribute

        for t, c in pTypes.items():
            if apiObj.hasFn(t):
                return c
        else:
            return Attribute

    @classmethod
    def _allTypes(cls):
        allTypes = cls._dgTypes()
        allTypes.update(cls._dagTypes())
        allTypes.update(cls._compTypes())
        return allTypes

    @classmethod
    def _defaultClasses(cls):
        return {cls.DEPENDNODE: DependNode,
                cls.DAGNODE: DagNode,
                cls.COMPONENT: Component,
                cls.ATTRIBUTE: Attribute}

    @classmethod
    def classFromMFn(cls, mfn, typeScope=None):
        assert typeScope in (cls.DAGNODE, cls.DEPENDNODE, cls.COMPONENT, cls.ATTRIBUTE)

        if typeScope is None:
            dic = cls._allTypes()
        elif typeScope == cls.DEPENDNODE:
            dic = cls._dgTypes()
        elif typeScope == cls.DAGNODE:
            dic = cls._dagTypes()
        elif typeScope == cls.ATTRIBUTE:
            dic = cls._plugTypes()
        elif typeScope == cls.COMPONENT:
            dic = cls._compTypes()
        else:
            raise ValueError('Unrecognized typeScope {}'.format(typeScope))

        _class = dic.get(mfn, None)

        return _class

    @classmethod
    def classFromApiObject(cls, apiObj, typeScope=None):
        assert isinstance(apiObj, (om2.MDagPath, om2.MObject))
        assert typeScope in (None, cls.DAGNODE, cls.DEPENDNODE, cls.COMPONENT, cls.ATTRIBUTE)

        if typeScope is None:
            if apiObj.hasFn(om2.MFn.kAttribute):
                typeScope = cls.ATTRIBUTE
            elif apiObj.hasFn(om2.MFn.kComponent):
                typeScope = cls.COMPONENT
            elif apiObj.hasFn(om2.MFn.kDagNode):
                typeScope = cls.DAGNODE
            elif apiObj.hasFn(om2.MFn.kDependencyNode):
                typeScope = cls.DEPENDNODE
            else:
                raise TypeError('Unrecognized api type : {}'.format(apiObj.apiType))

        if typeScope == cls.ATTRIBUTE:
            _class = cls._getPlugType(apiObj)
        else:
            _class = cls.classFromMFn(apiObj.apiType(), typeScope=typeScope)

        if _class is None:
            _class = cls._defaultClasses()[typeScope]
        return _class


class AttrCreator(object):
    """
    Factory Class that builds attribute by using subclasses of MFnAttribute. 

    The object returned must then be addedto the proper nodes.
    DO NOT ATTEMPT TO ADD ONE ATTRIBUTE TO MULTIPLE NODES

    ::CREATION PARAMETER::
    :param longName: full name of the attribute
    :type longName: str
    :param shortName: short name of the attribute (same as longName if undefined)
    :type shortName: str
    :param attrType: type of the attribute
    :type attrType: AttrCreator constant
    :param dataType: the data type for numeric and unit attributes
    :type dataType: DataType constant
    :param defaultValue: default value
    :type defaultValue: value, tuple

    ::POST TREATMENT PARAMETERS::
    :param keyable: is this attribute keyable ?
    :type keyable: bool
    :param min: minimum value
    :type min: value, tuple
    :param max: maximum value
    :type max: value, tuple
    :param softMin: minimum value
    :type softMin: value, tuple
    :param softMax: maximum value
    :type softMax: value, tuple
    :param multi: is this attribute an array ?
    :type multi: bool
    :param indexMatters: in case of multi attributes, does the index matter ?
    :type indexMatters: bool
    :param enumNames: names for enum attributes ('blue:green:red', 'one=1:twenty=20:hundred=100')
    :type enumNames: str
    :param asFilename: in case of string attributes, indicates whether it should be displayed as a filepath in the UI
    :type asFilename: bool

    :return: the attribute created
    :rtype: MFnAttribute
    """
    INVALID = 0
    COMPOUND = 1
    ENUM = 2
    GENERIC = 3
    MATRIX = 4
    MESSAGE = 5
    STRING = 6
    NUMERIC = 7
    UNIT = 8

    def __new__(cls, *args, **kwargs):
        if len(args):
            kwargs['longName'] = args[0]
            if len(args) == 2:
                kwargs['shortName'] = args[1]
        assert 'longName' in kwargs, 'Must provide a longName'

        if 'shortName' not in kwargs:
            kwargs['shortName'] = kwargs['longName']

        attrType = kwargs.pop('attrType', cls._attrTypefromData(kwargs.get('dataType')))
        assert attrType, 'Invalid Attribute Type'

        # CREATE
        # Fetch the creation parameters, and execute the create method, or createColor/createPoint if needed
        mfn = cls._MFnDict().get(attrType, None)()
        createParams = cls.getCreateParams(attrType, **kwargs)
        dataType = kwargs.get('dataType')
        if attrType == cls.NUMERIC and dataType in (api.DataType.COLOR, api.DataType.POINT):
            if dataType == api.DataType.COLOR:
                mfn.createColor(*createParams)
            else:
                mfn.createPoint(*createParams)
        else:
            mfn.create(*createParams)

        # POST CREATE
        # ---- Default Attributes
        mfn.array = kwargs.get('multi', False)
        mfn.keyable = kwargs.get('keyable', False)
        mfn.readable = kwargs.get('readable', True)

        if mfn.array:
            mfn.indexMatters = kwargs.get('indexMatters', False)

        if attrType == cls.ENUM:
            # If the attribute is an ENUM, we need to process the enumNames attribute and add fields one by one
            # Then we set the default value to whatever was provided, or to the min value of the enum if none was given
            assert 'enumNames' in kwargs, 'Enum attributes needs the enumNames parameter'
            enumNames = kwargs['enumNames']
            n = 0
            for field in enumNames.split(':'):
                if '=' in field:
                    split = field.split('=')
                    name = split[0]
                    n = int(split[1])
                else:
                    name = field
                mfn.addField(name, n)
                n += 1
            if 'defaultValue' in kwargs:
                dv = kwargs['defaultValue']
            else:
                dv = mfn.getMin()

            if isinstance(dv, int):
                mfn.default = dv
            else:
                # If not INT, assume it's a STRING
                mfn.setDefaultByName(dv)

        if attrType in (cls.UNIT, cls.NUMERIC):
            min = kwargs.get('min')
            max = kwargs.get('max')
            softMin = kwargs.get('softMin')
            softMax = kwargs.get('softMax')
            if min is not None:
                mfn.setMin(min)
            if max is not None:
                mfn.setMax(max)
            if softMin is not None:
                mfn.setSoftMin(softMin)
            if softMax is not None:
                mfn.setSoftMin(softMax)

        if attrType == cls.STRING and kwargs.get('asFilename', False):
            mfn.usedAsFilename = True

        return mfn

    @classmethod
    def _MFnDict(cls):
        return {cls.COMPOUND: om2.MFnCompoundAttribute,
                cls.ENUM: om2.MFnEnumAttribute,
                cls.GENERIC: om2.MFnGenericAttribute,
                cls.MATRIX: om2.MFnMatrixAttribute,
                cls.MESSAGE: om2.MFnMessageAttribute,
                cls.STRING: om2.MFnTypedAttribute,
                cls.NUMERIC: om2.MFnNumericAttribute,
                cls.UNIT: om2.MFnUnitAttribute}

    @classmethod
    def _attrTypefromData(cls, dataType):
        dt = api.DataType
        if dataType in dt.getNumericTypes():
            return cls.NUMERIC
        elif dataType in dt.getUnitTypes():
            return cls.UNIT
        elif dataType == dt.ENUM:
            return cls.ENUM
        elif dataType == dt.MATRIX:
            return cls.MATRIX
        elif dataType == dt.MESSAGE:
            return cls.MESSAGE
        elif dataType == dt.STRING:
            return cls.STRING
        else:
            return cls.INVALID

    @classmethod
    def getCreateParams(cls, attrType, **kwargs):
        params = [kwargs['longName'], kwargs['shortName']]
        dataType = kwargs.get('dataType', None)

        if attrType in (cls.UNIT, cls.NUMERIC) and dataType not in (api.DataType.COLOR, api.DataType.POINT):
            mdata = api.DataType.asMAttrDataConstant(dataType)
            params.append(mdata)

        if attrType in (cls.UNIT, cls.NUMERIC) and dataType not in (api.DataType.COLOR, api.DataType.POINT):
            params.append(kwargs.get('defaultValue', 0.0))

        if attrType == cls.STRING:
            params.append(om2.MFnData.kString)
            if 'defaultValue' in kwargs:
                dv = om2.MFnStringData()
                params.append(dv.create(kwargs['defaultValue']))
        return params

    @classmethod
    def typeFromString(cls, value):
        value = value.upper()
        if hasattr(cls, value):
            return getattr(cls, value)


def _processAttrInput(attr):
    if isinstance(attr, (unicode, str)):
        mplug = api.toApiObject(attr)
    elif isinstance(attr, Attribute):
        mplug = attr.apimplug()
    else:
        raise ValueError('attr must be either of type string or Attribute. got {} instead'.format(type(attr)))
    return mplug


class UserSubclassManager(object):
    _parentDict = {}
    _vClasses = []

    @classmethod
    def register(cls, vClass):
        parentCls = None
        for pCls in inspect.getmro(vClass):
            if pCls.__module__ == __name__:
                parentCls = pCls
                break
        assert parentCls, 'Virtual class must be a subclass of a PyObject'

        if parentCls not in cls._parentDict:
            cls._parentDict[parentCls] = []

        if vClass not in cls._parentDict[parentCls]:
            cls._parentDict[parentCls].append(vClass)

        if vClass not in cls._vClasses:
            cls._vClasses.append(vClass)

    @classmethod
    def getFromParentClass(cls, parentCls):
        return cls._parentDict.get(parentCls, [])

    @classmethod
    def isRegistered(cls, vClass):
        return vClass in cls._vClasses


# - STANDARD COMMANDS
@api.apiUndo
def setAttr(attr, *args, **kwargs):
    """
    Sets the value of an attribute. 
    
    If no value is passed in "args", then the cmds.setAttr command is called, thus making its flags available.
    You can choose to pass your own DGModifier-like object to set the value. If you do so, the doIt() method won't be 
    called and the modifier won't be added to the undo list, that is up to you. 
    
    :param args: The attribute to set the value on, followed by the value(s). (the attribute can be provided either as
    an Attribute or a String)
    :param _modifier: an optional DGModifier-like object that will be used to set the attribute.
    :param _datatype: you can provide the api.DataType of the attribute yourself, for better performances
    :param kwargs: any of the cmds.setAttr flags are valid
    :return: the new modifier if none was provided. Otherwise, None
    """
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
    """
    Returns the value of an attribute. 
    
    If any flags are passed into kwargs, this will call cmds.getAttr instead
    
    :param attr: The attribute
    :type attr: Attribute, String
    :param time: the time at which you can to get the attribute
    :type time: om2.MDGContext
    :param asString: whether you want to get the field name of an enum attribute, or its value
    :type asString: bool
    :param _datatype: you can provide the type of the attribute yourself, for better performances
    :type _datatype: api.DataType
    :param kwargs: Any of cmds.getAttr flags are valid
    :return: 
    """
    plug = _processAttrInput(attr)
    time = kwargs.pop('time', om2.MDGContext.kNormal)
    asStr = kwargs.pop('asString', False)
    datatype = kwargs.pop('_datatype', None)
    asApi = kwargs.pop('asApi', False)
    if not len(kwargs):
        if datatype is None:
            datatype = api.DataType.fromMObject(plug.attribute())

        if plug.isArray and plug.attribute().hasFn(om2.MFn.kTypedAttribute) and not plug.isDynamic:
            plug = plug.elementByLogicalIndex(0)
            return api.getPlugValue(plug, attrType=datatype, asString=asStr, context=time)

        elif plug.isArray:
            result = []
            indices = plug.getExistingArrayAttributeIndices()
            it = utils.Iterator(indices)

            while not it.isDone():
                idx = it.currentItem()
                p = plug.elementByLogicalIndex(idx)
                value = api.getPlugValue(p, attrType=datatype, asString=asStr, context=time)
                if not asApi and datatype == api.DataType.MESSAGE and value is not None:
                    value = PyObjectFactory(value)
                if value is not None:
                    result.append(value)
                it.next()
            return result
        else:
            return api.getPlugValue(plug, attrType=datatype, asString=asStr, context=time)
    else:
        if isinstance(attr, Attribute):
            attr = attr.name(fullDagPath=True)
        return cmds.getAttr(attr, **kwargs)


@api.apiUndo
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


@api.apiUndo
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


def createNode(nodeType, name=None, parent=om2.MObject.kNullObj, _modifier=None, _isDag=None):
    """
    Creates a new node of the given type.
    
    You can choose to pass your own DGModifier or DagModifier king of object to set the value. If you do so, the doIt() 
    method won't be called and the modifier won't be added to the undo list, that is up to you. Also, if you provide a
    modifier yourself, it's up to you to make sure you are providing the right one (Dag or DG) depending on the provided
    nodeType.
    
    :param nodeType: the type of the node to be created
    :type nodeType: string, om2.MTypeId
    :param name: optional name for the new node. if None is provided, the nodeType will be used with an int increment
    :type name: string
    :param parent: optional parent of the new node. If None, it will be parented to the World if applicable, or under a
    new transform, and this transform will be returned instead
    :param _modifier: You can choose to pass your own DGModifier-like object to set the value. If you do so, the doIt()
    method won't be called and the modifier won't be added to the undo list, that is up to you. 
    :param _isDag: optional flag to tell if the nodeType is a Dag or DG, and skip the checking step. 
    :return: The node newly created
    :rtype: PyObject
    """
    kwargs = {'name': name}
    if _modifier is None:
        doIt = True
        if _isDag is None:
            if 'dagNode' in cmds.nodeType(nodeType, inherited=True, isTypeName=True):
                mod = api.DagModifier()
                kwargs['parent'] = parent
            else:
                mod = api.DGModifier()
        elif _isDag:
            mod = api.DagModifier()
        else:
            mod = api.DGModifier()

    else:
        mod = _modifier
        doIt = False
    obj = mod.createNode(nodeType, **kwargs)
    if doIt:
        mod.doIt()
        api.apiundo.commit(undo=mod.undoIt, redo=mod.doIt)
    return PyObjectFactory(obj)


@api.apiUndo
def select(objects=None, add=False, deselect=False, toggle=False, clear=False):
    """
    Puts the given objects in the active selection list.
    
    :param objects: one or more objects to select
    :type objects: MObject, MDagPath, MPlug, tuple of (MDagPath, MObject), PyObject, String, List, Tuple, MSelectionList
    :param add: add the objects to the active list
    :param deselect: remove the objects from the active list
    :param toggle: adds the objects to the active list if they aren't in, or remove them if they are
    :param clear: remove all objects from the active list
    :return: Modifier used to the undoability
    :rtype: api.ProxyModifier
    """
    # If no objects are provided and clear is True, then we set the current selection to an empty list
    currentSel = om2.MGlobal.getActiveSelectionList()
    oldSel = om2.MSelectionList()
    oldSel.copy(currentSel)

    if objects is None and clear:
        emptyList = om2.MSelectionList()
        om2.MGlobal.setActiveSelectionList(emptyList)
        modifier = api.ProxyModifier(doFunc=om2.MGlobal.setActiveSelectionList, doArgs=[emptyList], undoArgs=[oldSel])
        return modifier

    # Make sure the object provided is an iterable, then convert it to a MSelectionList
    if not isinstance(objects, (list, tuple, om2.MSelectionList)):
        objects = [objects]

    if not isinstance(objects, om2.MSelectionList):
        it = utils.Iterator(objects)
        sel = om2.MSelectionList()
        while not it.isDone():
            item = it.currentItem()
            if isinstance(item, PyObject):
                sel.add(item._getSelectableObject())
            else:
                sel.add(item)
            it.next()
    else:
        sel = objects

    # Merge selection lists according to the specified method
    if add:
        currentSel.merge(sel, om2.MSelectionList.kMergeNormal)
    elif deselect:
        currentSel.merge(sel, om2.MSelectionList.kRemoveFromList)
    elif toggle:
        currentSel.merge(sel, om2.MSelectionList.kXORWithList)
    else:
        currentSel = sel

    modifier = api.ProxyModifier(doFunc=om2.MGlobal.setActiveSelectionList, doArgs=[currentSel], undoArgs=[oldSel])
    om2.MGlobal.setActiveSelectionList(currentSel)
    return modifier


@api.apiUndo
def parent(*args, **kwargs):
    """
    Parents nodes to the last node provided
    
    You can choose to pass your own DGModifier-like object to set the value. If you do so, the doIt() method won't be 
    called and the modifier won't be added to the undo list, that is up to you. 
    
    :param args: the nodes you wish to parent
    :param world: If True, all the nodes will be moved under the world
    :param relative: If True, the nodes will maintain their local transform
    :param _modifier: an optional DagModifier-like object that will be used to set the attribute.
    
    :return: 
    """
    world = kwargs.get('world', False)
    relative = kwargs.get('relative', False)
    _modifier = kwargs.get('_modifier', None)

    if _modifier is None:
        doIt = True
        modifier = api.DagModifier()
    else:
        doIt = False
        modifier = _modifier

    if world or len(args) == 1:
        objects = args
        pObj = om2.MObject.kNullObj
    else:
        objects = args[:-1]
        parent = args[-1]

        if not isinstance(parent, (PyObject, om2.MObject)):
            parent = PyObjectFactory(parent)
            pObj = parent.apimobject()
        elif isinstance(parent, PyObject):
            pObj = parent.apimobject()
        else:
            pObj = parent

    it = utils.Iterator(objects)
    while not it.isDone():
        obj = it.currentItem()
        if isinstance(obj, PyObject):
            pyObj = obj
        else:
            pyObj = PyObjectFactory(obj)
        obj = obj.apimobject()
        modifier.reparentNode(obj, pObj)
        if not relative:
            mtx = pyObj.getMatrix(space=om2.MSpace.kWorld)
            pyPObj = PyObjectFactory(pObj)
            pim = pyPObj.worldInverseMatrix.get()
            transform(pyObj, matrix=mtx * pim, _modifier=modifier, objectSpace=True)
        it.next()

    if doIt:
        modifier.doIt()

    return modifier


def selected():
    sel = om2.MGlobal.getActiveSelectionList()
    return PyObjectFactory.fromMSelectionList(sel)


@api.apiUndo
def transform(node, translate=None, rotate=None, scale=None, shear=None, matrix=None, relative=False, worldSpace=False, objectSpace=False, _modifier=None):
    if not isinstance(node, Transform):
        node = PyObjectFactory(node)
    assert isinstance(node, Transform), 'Node must be a transform'
    assert any([worldSpace, objectSpace]), 'One of worldSpace or objectSpace has to be True'

    mfn = node.apimfn()

    # -----  Determines the space choosen by the user and get the corresponding matrix
    space = om2.MSpace.kObject if objectSpace else om2.MSpace.kWorld
    currentMtx = node.getMatrix(space=space)

    if matrix is not None:
        if relative:
            matrix = currentMtx * matrix
        if space == om2.MSpace.kWorld:
            pim = node.parentInverseMatrix.get()
            matrix *= pim
        matrix = om2.MTransformationMatrix(matrix)
        translation = matrix.translation(om2.MSpace.kTransform) - mfn.rotatePivotTranslation(om2.MSpace.kTransform) - om2.MVector(mfn.rotatePivot(om2.MSpace.kTransform))
        return transform(node, translate=translation,
                         rotate=matrix.rotation(),
                         scale=matrix.scale(om2.MSpace.kTransform),
                         shear=matrix.shear(om2.MSpace.kTransform),
                         relative=False,
                         objectSpace=True,
                         _modifier=_modifier)

    if _modifier is None:
        modifier = api.DagModifier()
        doIt = True
    else:
        modifier = _modifier
        doIt = False

    axes = ['X', 'Y', 'Z']

    # ----- Apply the translate and rotate provided onto the current transformation matrix
    transformation = om2.MTransformationMatrix(currentMtx)

    if translate is not None:
        vector = om2.MVector(translate)
        if relative:
            transformation.translateBy(vector, om2.MSpace.kTransform)
        else:
            transformation.setTranslation(vector, om2.MSpace.kTransform)

    if rotate is not None:
        order = mfn.rotation().order
        if isinstance(rotate, om2.MEulerRotation):
            rotate.reorderIt(order)
        else:
            rotate = om2.MEulerRotation([api.DataType.toAngle(r).asRadians() for r in rotate], order=order)

        if isinstance(node, Joint):
            rotate *= node.getJointOrientation().invertIt()

        if relative:
            transformation.rotateBy(rotate, om2.MSpace.kTransform)
        else:
            transformation.setRotation(rotate)

    # ----- If we are in working in worldSpace, we must convert it back to object space before setting the attributes
    if space == om2.MSpace.kWorld:
        pim = node.parentInverseMatrix.get()
        transformation = om2.MTransformationMatrix(transformation.asMatrix() * pim)
    # ------ Now we can finally set the attribute values.
    if translate is not None:
        translate = transformation.translation(om2.MSpace.kTransform)
        for x, a in enumerate(axes):
            plug = mfn.findPlug('translate{}'.format(a), False)
            if plug.isFreeToChange() == om2.MPlug.kFreeToChange:
                modifier.setPlugValue(plug, translate[x], datatype=api.DataType.DISTANCE)

    if rotate is not None:
        rotate = transformation.rotation()
        for x, a in enumerate(axes):
            plug = mfn.findPlug('rotate{}'.format(a), False)
            value = api.DataType.toAngle(rotate[x], unit=om2.MAngle.kRadians)
            if plug.isFreeToChange() == om2.MPlug.kFreeToChange:
                modifier.setPlugValue(plug, value, datatype=api.DataType.ANGLE)

    if scale is not None:
        for x, a in enumerate(axes):
            plug = mfn.findPlug('scale{}'.format(a), False)
            if plug.isFreeToChange() == om2.MPlug.kFreeToChange:
                if relative:
                    value = plug.asFloat() * scale[x]
                else:
                    value = scale[x]
                modifier.setPlugValue(plug, value, datatype=api.DataType.FLOAT)

    if shear is not None:
        for x, a in enumerate(['XY', 'XZ', 'YZ']):
            plug = mfn.findPlug('shear{}'.format(a), False)
            if plug.isFreeToChange() == om2.MPlug.kFreeToChange:
                if relative:
                    value = plug.asFloat() * shear[x]
                else:
                    value = shear[x]
                modifier.setPlugValue(plug, value, datatype=api.DataType.FLOAT)

    if doIt:
        modifier.doIt()

    return modifier


# RECYCLE DECORATORS : provide the ability to reuse some api object like MFn & MIt to avoid recreating them
def recycle_mfn(func):
    def wrapped(*args, **kwargs):
        inst = args[0]
        mfn = kwargs.get('mfn', None)
        if mfn is None:
            kwargs['mfn'] = inst.apimfn()
        result = func(*args, **kwargs)
        return result
    return wrapped


def recycle_mplug(func):
    def wrapped(*args, **kwargs):
        inst = args[0]
        mfn = kwargs.get('mplug', None)
        if mfn is None:
            kwargs['mplug'] = inst.apimplug()
        result = func(*args, **kwargs)
        return result
    return wrapped


def recycle_mit(func):
    """
    decorator that allows to reuse an MItMeshVertex object to avoid recreating it unnecessarily
    """
    def wrapped(*args, **kwargs):
        inst = args[0]
        it = kwargs.get('it', None)
        if it is None:
            # item = inst.apimfn().element(kwargs.pop('item', 0))
            item = inst._extractElement(kwargs.pop('item', 0))
            kwargs['it'] = inst.apimitId(item)
        result = func(*args, **kwargs)
        return result
    return wrapped


# TODO : Add MFn constant as a class variable for each class, so that we can use them for filter MSelectionList
@add_metaclass(ABCMeta)
class PyObject(object):
    _mfnClass = om2.MFnBase
    _mfnConstant = om2.MFn.kInvalid

    def __new__(cls, *args, **kwargs):
        # If None of 'MDagPath', 'MObject', 'MObjectHandle' or 'MPlug' are present in kwargs
        # and if cls is registered as a user class in the UserSubclassManager, then attempt to create a new object
        if not any(k in ('MDagPath', 'MObject', 'MObjectHandle', 'MPlug') for k in kwargs):
            if not UserSubclassManager.isRegistered(cls):
                raise RuntimeError('{} is not a registered User Subclass'.format(cls))
            kwargs, postKwargs = cls._preCreateVirtual(*args, **kwargs)
            newNode = cls._createVirtual(**kwargs)
            cls._postCreateVirtual(newNode, **postKwargs)
            kwargs = cls.getBuildDataFromName(newNode)
            instance = super(PyObject, cls).__new__(cls, **kwargs)
            instance.__apiInput__ = kwargs
        else:
            mobject = kwargs['MObjectHandle'].object()
            userCls = UserSubclassManager.getFromParentClass(cls)
            for uCls in userCls:
                if uCls._isVirtual(mobject):
                    instance = super(PyObject, cls).__new__(uCls, *args, **kwargs)
                    instance.__apiInput__ = kwargs
                    break
            else:
                instance = super(PyObject, cls).__new__(cls, *args, **kwargs)
                instance.__apiInput__ = kwargs
        return instance

    @abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    def __repr__(self):
        return '{} <{}>'.format(self.name(), self.__class__.__name__)

    def __str__(self):
        return self.name()

    @abstractmethod
    def apimfn(self):
        pass

    def apimobject(self):
        return self.__apiInput__['MObjectHandle'].object()

    @abstractmethod
    def name(self, fullDagPath=False):
        pass

    def _getSelectableObject(self):
        """
        Returns an object that can be added to an MSelectionList
        
        :rtype: MObject
        """
        return self.apimobject()


# - ATTRIBUTES
class Attribute(PyObject):
    _mfnClass = om2.MFnAttribute
    _mfnConstant = om2.MFn.kAttribute

    def __init__(self, *args, **kwargs):
        """
        :param MPlug: om.MPlug

        # Optional #
        :param node: DependNode         # If you can pass this here directly, it won't have to look for it later
        """
        super(Attribute, self).__init__(*args, **kwargs)
        self._node = kwargs.get('node', None)
        self._parent = kwargs.get('parent', None)
        self._attrType = None

    def __getitem__(self, item):
        return Attribute(MPlug=self.apimplug().elementByLogicalIndex(item), node=self._node)

    def __getattr__(self, item):
        attr = self._buildAttr(item)
        if attr is not None:
            setattr(self, item, attr)
            return attr
        else:
            raise AttributeError('Cannot find attribute {} on {}'.format(item, self.name()))

    # API RELATED METHODS
    def apimfn(self):
        return self._mfnClass(self.apimobject())

    def apimobject(self):
        return self.__apiInput__['MObjectHandle'].object()

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
        if self._attrType is None:
            self._attrType = api.DataType.fromMObject(self.apimobject())
        return self._attrType

    @classmethod
    def getBuildDataFromName(cls, name):
        sel = om2.MSelectionList()
        sel.add(name)

        try:
            mplug = sel.getPlug(0)
        except TypeError:
            raise TypeError('{} is not a valid attribute'.format(name))

        return {'MObjectHandle': om2.MObjectHandle(mplug.attribute()), 'MPlug': mplug}

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False, includeNode=True, alias=False, fullAttrPath=False, longNames=True):
        plugName = self.apimplug().partialName(includeNodeName=includeNode, useAlias=alias,
                                               useFullAttributePath=fullAttrPath, useLongNames=longNames)
        return plugName

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

    def _buildAttr(self, name):
        node = self.node()
        nodemfn = node.apimfn()
        mplug = nodemfn.findPlug(name, False)
        apimplug = self.apimplug()
        if mplug is None:
            return None
        mplug = apimplug.child(mplug.attribute())
        attr = Attribute(MPlug=mplug, node=node, parent=self)
        return attr

    def attr(self, name):
        return getattr(self, name)

    def parent(self):
        if self._parent is not None:
            return self._parent
        mplug = self.apimplug()
        parentPlug = mplug.parent()
        return Attribute(MPlug=parentPlug, node=self.node())

    def rename(self, name, shortName=False):
        mfn = self.apimfn()
        if shortName:
            mfn.shortName = name
        else:
            mfn.name = name

    @recycle_mplug
    def isFreeToChange(self, **kwargs):
        mplug = kwargs['mplug']
        ftc = mplug.isFreeToChange()
        if ftc == om2.MPlug.kFreeToChange:
            return 1
        elif ftc == om2.MPlug.kNotFreeToChange:
            return 0
        else: # ftc == om2.MPlug.kChildrenNotFreeToChange
            return -1

    # Set & Get attribute parameters
    @recycle_mplug
    def isKeyable(self, **kwargs):
        mplug = kwargs['mplug']
        return mplug.isKeyable

    @recycle_mplug
    def _setKeyable(self, value, **kwargs):
        mplug = kwargs['mplug']
        mplug.isKeyable = value
        if not value:
            mplug.isChannelBox = True
        else:
            mplug.isChannelBox = False

    @api.apiUndo
    @recycle_mplug
    def setKeyable(self, value, **kwargs):
        mplug = kwargs['mplug']
        oldValue = self.isKeyable(mplug=mplug)
        modifier = api.ProxyModifier(doFunc=self._setKeyable, doKwargs={'value':value, 'mplug':mplug},
                                undoKwargs={'value': oldValue, 'mplug': mplug})
        modifier.doIt()
        return modifier

    @recycle_mplug
    def isDisplayable(self, **kwargs):
        mplug = kwargs['mplug']
        return mplug.isChannelBox

    @recycle_mplug
    def _setDisplayable(self, value, **kwargs):
        mplug = kwargs['mplug']
        mplug.isChannelBox = value

    @api.apiUndo
    @recycle_mplug
    def setDisplayable(self, value, **kwargs):
        mplug = kwargs['mplug']
        oldValue = self.isDisplayable(mplug=mplug)
        modifier = api.ProxyModifier(doFunc=self._setDisplayable, doKwargs={'value': value, 'mplug': mplug},
                                     undoKwargs={'value': oldValue, 'mplug': mplug})
        modifier.doIt()
        return modifier

    @recycle_mplug
    def isDynamic(self, **kwargs):
        mplug = kwargs['mplug']
        return mplug.isDynamic

    # Inputs and Outputs
    @recycle_mplug
    def isSource(self, **kwargs):
        mplug = kwargs['mplug']
        return mplug.isSource

    @recycle_mplug
    def isDestination(self, **kwargs):
        mplug = kwargs['mplug']
        return mplug.isDestination

    @recycle_mplug
    def source(self, skipConversion=True, asApi=False, **kwargs):
        mplug = kwargs['mplug']

        if mplug.isArray:
            result = []
            indices = mplug.getExistingArrayAttributeIndices()
            it = utils.Iterator(indices)

            while not it.isDone():
                idx = it.currentItem()
                p = mplug.elementByLogicalIndex(idx)
                if p.isDestination:
                    if skipConversion:
                        src = p.source()
                    else:
                        src = p.sourceWithConversion()

                    if asApi:
                        result.append(src)
                    else:
                        result.append(PyObjectFactory(src))

                it.next()
            return result
        else:
            if not mplug.isDestination:
                return None

            if skipConversion:
                src = mplug.source()
            else:
                src = mplug.sourceWithConversion()

            if asApi:
                return src
            else:
                return PyObjectFactory(src)

    @recycle_mplug
    def destinations(self, skipConversion=True, asApi=False, **kwargs):
        mplug = kwargs['mplug']

        def plugArrayToAttribute(array):
            result = []
            it = utils.Iterator(array)
            while not it.isDone():
                p = it.currentItem()
                result.append(PyObjectFactory(p))
                it.next()
            return result

        if mplug.isArray:
            result = []
            indices = mplug.getExistingArrayAttributeIndices()
            it = utils.Iterator(indices)

            while not it.isDone():
                idx = it.currentItem()
                p = mplug.elementByLogicalIndex(idx)
                if p.isSource:
                    if skipConversion:
                        pArray = p.destinations()
                    else:
                        pArray = p.destinationsWithConversion()

                    if asApi:
                        result.append(pArray)
                    else:
                        result.append(plugArrayToAttribute(pArray))

                it.next()
            return result
        else:
            if not mplug.isSource:
                return None

            if skipConversion:
                pArray = mplug.destinations()
            else:
                pArray = mplug.destinationsWithConversion()

            if asApi:
                return pArray
            else:
                return plugArrayToAttribute(pArray)


class NumericAttribute(Attribute):
    _mfnClass = om2.MFnNumericAttribute
    _mfnConstant = om2.MFn.kNumericAttribute

    def __init__(self, *args, **kwargs):
        super(NumericAttribute, self).__init__(*args, **kwargs)

    @recycle_mfn
    def hasMin(self, **kwargs):
        mfn = kwargs['mfn']
        return mfn.hasMin()

    @recycle_mfn
    def hasMax(self, **kwargs):
        mfn = kwargs['mfn']
        return mfn.hasMax()

    @recycle_mfn
    def setMin(self, value, **kwargs):
        mfn = kwargs['mfn']
        mfn.setMin(value)
        return mfn

    @recycle_mfn
    def setMax(self, value, **kwargs):
        mfn = kwargs['mfn']
        mfn.setMax(value)
        return mfn


class UnitAttribute(NumericAttribute):
    _mfnClass = om2.MFnUnitAttribute
    _mfnConstant = om2.MFn.kUnitAttribute

    def __init__(self, *args, **kwargs):
        super(UnitAttribute, self).__init__(*args, **kwargs)


class CompoundAttribute(Attribute):
    _mfnClass = om2.MFnCompoundAttribute
    _mfnConstant = om2.MFn.kCompoundAttribute

    def __init__(self, *args, **kwargs):
        super(CompoundAttribute, self).__init__(*args, **kwargs)

    def __len__(self):
        return self.numChildren()

    @recycle_mfn
    def child(self, x, **kwargs):
        mfn = kwargs['mfn']
        return mfn.child(x)

    @recycle_mfn
    def addChild(self, attr, **kwargs):
        mfn = kwargs['mfn']
        if isinstance(attr, Attribute):
            attr = attr.apimobject()
        assert isinstance(attr, om2.MObject), 'first parameter must be of type MObject or Attribute'
        mfn.addChild(mfn)

    @recycle_mfn
    def removeChild(self, attr, **kwargs):
        mfn = kwargs['mfn']
        if isinstance(attr, Attribute):
            attr = attr.apimobject()
        assert isinstance(attr, om2.MObject), 'first parameter must be of type MObject or Attribute'
        mfn.removeChild(mfn)

    @recycle_mfn
    def numChildren(self, **kwargs):
        mfn = kwargs['mfn']
        return mfn.numChildren()


# - NODES
class DependNode(PyObject):
    _mfnClass = om2.MFnDependencyNode
    _mfnConstant = om2.MFn.kDependencyNode

    def __init__(self, *args, **kwargs):
        super(DependNode, self).__init__(*args, **kwargs)

    def __getattr__(self, item):
        attr = self._buildAttr(item)
        if attr is not None:
            setattr(self, item, attr)
            return attr
        else:
            raise AttributeError('Cannot find attribute {} on {}'.format(item, self.name()))

    # API RELATED METHODS

    def apimfn(self):
        return self._mfnClass(self.apimobject())

    @classmethod
    def getBuildDataFromName(cls, name):
        mobj = api.toApiObject(name)
        if not isinstance(mobj, om2.MObject):
            raise TypeError('{} is not a Depend node'.format(name))

        return {'MObjectHandle': om2.MObjectHandle(mobj)}

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False):
        return self.apimfn().name()

    def hasAttr(self, name):
        return self.apimfn().hasAttribute(name)

    def _buildAttr(self, name):
        apimfn = self.apimfn()
        if apimfn.hasAttribute(name):
            attr = PyObjectFactory(MPlug=apimfn.findPlug(name, False), node=self, objectType=PyObjectFactory.ATTRIBUTE)
            #attr = Attribute(MPlug=apimfn.findPlug(name, False), node=self)
            return attr
        else:
            return None

    def attr(self, name):
        return getattr(self, name)

    def createAttr(self, *args, **kwargs):
        """
        Create a new attribute on this node. See AttrCreator for parameters 
        :param _modifier: an optional DGModifier for this operation. If one is provided, doIt won't be called
        :return: The attribute created
        :rtype: Attribute
        """
        modifier = kwargs.pop('_modifier', None)
        parent = kwargs.pop('parent', None)
        if modifier is None:
            modifier = api.DGModifier()
            doIt = True
        else:
            doIt = False

        attr = AttrCreator(*args, **kwargs)
        names = (attr.name, attr.shortName)
        for n in names:
            if self.hasAttr(n) or hasattr(self, n):
                raise NameError('name {} already used'.format(n))

        if isinstance(attr, om2.MFnCompoundAttribute):
            if not attr.numChildren():
                obj = attr.object()
                return CompoundAttribute(MPlug=om2.MPlug(obj), MObjectHandle=om2.MObjectHandle(obj), node=self)

        if parent is not None:
            if isinstance(parent, om2.MObject):
                mfn = om2.MFnCompoundAttribute(parent)
            elif isinstance(parent, CompoundAttribute):
                mfn = parent.apimfn()
            elif isinstance(parent, (str, unicode)):
                if self.hasAttr(parent):
                    parent = self.attr(parent)
                    mfn = parent.apimfn()
            else:
                raise TypeError('Accepted types for "parent" are MObject, CompoundAttribute, string')

            mfn.addChild(attr)
            obj = attr.object()
            return PyObjectFactory(MPlug=om2.MPlug(obj), MObjectHandle=om2.MObjectHandle(obj),
                                   objectType=PyObjectFactory.ATTRIBUTE)

        modifier.addAttribute(attr.object())

        if doIt:
            modifier.doIt()
            api.apiundo.commit(undo=modifier.undoIt, redo=modifier.doIt)

        return self.attr(attr.name)

    @classmethod
    def _create(cls, nodeType, name=None):
        """
        Create a new dependency node of the given type. If no name is specified, it will be based on the nodeType [NOT UNDOABLE]
        
        :param nodeType: 
        :param name: 
        :return: 
        """
        mfn = cls._mfnClass()
        obj = mfn.create(nodeType, name)
        return PyObjectFactory(MObject=obj)

    def _delete(self):
        om2.MGlobal.deleteNode(self.apimobject())

    @classmethod
    def create(cls, nodeType, name=None, _modifier=None):
        # If an MModifier is provided, it'll be up to the user to do the doIt call and apiUndo commit
        if _modifier is not None:
            mod = _modifier
            doIt = False
        else:
            mod = api.DGModifier()
            doIt = True

        obj = mod.createNode(nodeType=nodeType, name=name)
        api.apiundo.commit(undo=mod.undoIt, redo=mod.doIt)
        if doIt:
            mod.doIt()
            return PyObjectFactory(obj)
        else:
            return obj


class DagNode(DependNode):
    _mfnClass = om2.MFnDagNode
    _mfnConstant = om2.MFn.kDagNode

    def __init__(self, *args, **kwargs):
        super(DagNode, self).__init__(*args, **kwargs)

    # API RELATED METHODS
    def apimfn(self):
        return self._mfnClass(self.apidagpath())

    def apidagpath(self):
        return self.__apiInput__['MDagPath']

    @classmethod
    def getBuildDataFromName(cls, name):
        dag = api.toApiObject(name)
        if not isinstance(dag, om2.MDagPath):
            raise TypeError('{} is not a DAG node'.format(name))

        return {'MDagPath':dag, 'MObjectHandle':om2.MObjectHandle(dag.node())}

    # OTHER DEFAULT METHODS
    def name(self, fullDagPath=False):
        if fullDagPath:
            return self.apimfn().fullPathName()
        return self.apimfn().name()

    def _getSelectableObject(self):
        """
        Returns an object that can be added to an MSelectionList

        :rtype: MDagPath
        """
        return self.apidagpath()

    @classmethod
    def _create(cls, nodeType, name=None, parent=om2.MObject.kNullObj):
        """
        Create a new dependency node of the given type. If no name is specified, it will be based on the nodeType [NOT UNDOABLE]

        :param nodeType: 
        :param name: 
        :return: 
        """
        mfn = cls._mfnClass()
        if isinstance(parent, PyObject):
            parent = parent.apimobject()

        obj = mfn.create(nodeType, name, parent=parent)
        return PyObjectFactory(MObject=obj)

    @classmethod
    def create(cls, nodeType, name=None, parent=om2.MObject.kNullObj, _modifier=None):
        # If an MModifier is provided, it'll be up to the user to do the doIt call and apiUndo commit
        if _modifier is not None:
            mod = _modifier
            doIt = False
        else:
            mod = api.DagModifier()
            doIt = True

        if isinstance(parent, PyObject):
            parent = parent.apimobject()

        obj = mod.createNode(nodeType=nodeType, name=name, parent=parent)
        if doIt:
            mod.doIt()
            api.apiundo.commit(undo=mod.undoIt, redo=mod.doIt)
            return PyObjectFactory(obj)
        else:
            return obj


class Transform(DagNode):
    _mfnClass = om2.MFnTransform
    _mfnConstant = om2.MFn.kTransform

    def __init__(self, *args, **kwargs):
        super(Transform, self).__init__(*args, **kwargs)

    def __getattr__(self, item):
        attr = self._buildAttr(item)
        if attr is not None:
            return attr
        else:
            raise AttributeError('Could not find attribute {} on {}'.format(item, self.name()))

    def numShape(self):
        dag = self.apidagpath()
        return dag.numberOfShapesDirectlyBelow()

    def getShape(self, n=0):
        dag = self.apidagpath()
        # Check if this transform has any shape
        if not self.numShape():
            raise TypeError('{} has no Shape'.format(self.name()))

        # Copy this transform's DagPath and extend it to Shape[n]
        dag = om2.MDagPath(dag)
        dag.extendToShape(n)

        # Get and MObjectHandle for this DagPath
        sel = om2.MSelectionList()
        sel.add(dag)
        objHandle = om2.MObjectHandle(sel.getDependNode(0))
        return DependNodeBuilder.create(MObjectHandle=objHandle, MDagPath=dag)

    def _buildAttr(self, name, checkShape=True):
        attr = super(DagNode, self)._buildAttr(name=name)
        if attr is None and checkShape and self.numShape():
            return getattr(self.getShape(), name)
        else:
            return attr

    @classmethod
    def _create(cls, name=None, parent=om2.MObject.kNullObj):
        """
        Create a new dependency node of the given type. If no name is specified, it will be based on the nodeType [NOT UNDOABLE]

        :param nodeType: 
        :param name: 
        :return: 
        """
        mfn = cls._mfnClass()
        if isinstance(parent, PyObject):
            parent = parent.apimobject()

        obj = mfn.create(name, parent=parent)
        return PyObjectFactory(MObject=obj)

    @classmethod
    def create(cls, name=None, parent=om2.MObject.kNullObj, _modifier=None):
        # If an MModifier is provided, it'll be up to the user to do the doIt call and apiUndo commit
        if _modifier is not None:
            mod = _modifier
            doIt = False
        else:
            mod = api.DagModifier()
            doIt = True

        if isinstance(parent, PyObject):
            parent = parent.apimobject()

        obj = mod.createNode('transform', name=name, parent=parent)
        if doIt:
            mod.doIt()
            api.apiundo.commit(undo=mod.undoIt, redo=mod.doIt)
            return PyObjectFactory(obj)
        else:
            return obj

    @recycle_mfn
    def _setMatrix(self, matrix, space=om2.MSpace.kObject, **kwargs):
        mfn = kwargs['mfn']
        if not isinstance(matrix, om2.MTransformationMatrix):
            matrix = om2.MTransformationMatrix(matrix)

        if space == om2.MSpace.kWorld:
            pim = self.parentInverseMatrix.get()
            m = matrix.asMatrix()
            matrix = om2.MTransformationMatrix(m * pim)

        mfn.setTransformation(matrix)

    @api.apiUndo
    @recycle_mfn
    def setMatrix(self, matrix, space=om2.MSpace.kObject):
        doKwargs = {'matrix': matrix, 'space': space}
        undoKwargs = {'matrix':self.getMatrix(space=space), 'space': space}
        modifier = api.ProxyModifier(doFunc=self._setMatrix, doKwargs=doKwargs, undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    def getMatrix(self, space=om2.MSpace.kObject):
        if space == om2.MSpace.kObject:
            return self.matrix.get()
        elif space == om2.MSpace.kWorld:
            return self.worldMatrix.get()
        else:
            raise ValueError('Invalid MSpace constant. Accepted spaces are kObject or kWorld')

    @recycle_mfn
    def getRotation(self, space=om2.MSpace.kTransform, asQuaternion=False, **kwargs):
        mfn = kwargs.get('mfn')
        return mfn.rotation(space, asQuaternion=asQuaternion)


class Joint(Transform):
    _mfnConstant = om2.MFn.kJoint

    def __init__(self, *args, **kwargs):
        super(Joint, self).__init__(*args, **kwargs)

    def getJointOrientation(self, asQuaternion=False):
        euler = api.DataType.toEuler(self.jointOrient.get())
        if asQuaternion:
            return euler.asQuaternion()
        else:
            return euler

    def zeroRotate(self):
        """
        Zero out the rotate attributes by moving the values to jointOrient.
        
        :return: None 
        """
        jo = self.jointOrient
        ro = self.rotate
        if jo.isFreeToChange() and ro.isFreeToChange():
            jEuler = self.getJointOrientation()
            rEuler = self.getRotation()
            euler = rEuler * jEuler
            euler.reorderIt(jEuler.order)
            jo.set([om2.MAngle.internalToUI(v) for v in euler.asVector()])
            ro.set(0, 0, 0)
        else:
            raise RuntimeError('Cannot zero out rotate because of locked attributes or incomming connections')

    def zeroJointOrient(self):
        """
        Zero out the jointOrient attributes by moving the values to rotate.

        :return: None 
        """

        jo = self.jointOrient
        ro = self.rotate
        if jo.isFreeToChange() and ro.isFreeToChange():
            jEuler = self.getJointOrientation()
            rEuler = self.getRotation()
            euler = rEuler * jEuler
            ro.set([om2.MAngle.internalToUI(v) for v in euler.asVector()])
            jo.set(0, 0, 0)
        else:
            raise RuntimeError('Cannot zero out jointOrient because of locked attributes or incomming connections')


class ObjectSet(DependNode):
    _mfnClass = om2.MFnSet
    _mfnConstant = om2.MFn.kSet

    def __init__(self, *args, **kwargs):
        super(ObjectSet, self).__init__(*args, **kwargs)

    def addMember(self, member):
        """
        Adds an object to this set
        
        :param member: the object
        :type member: str, PyObject, MDagPath, MObject, tuple(MDagPath, MObject)
        :return: None
        """
        member = self._processObject(member)
        self.apimfn().addMember(member)

    def addMembers(self, members):
        """
        Adds multiple objects to this set
        
        :param members: A list of objects
        :type members: MSelectionList, List of compatible objects (see addMember)
        :return: the MSelectionList that was added
        :rtype: MSelectionList
        """
        if not isinstance(members, om2.MSelectionList):
            members = self._processList(members)
        self.apimfn().addMembers(members)
        return members

    def getMembers(self, flatten=False, asApi=False):
        """
        get the members of this set
        
        :param flatten: if this is True, the members of any set inside this set will be returned too
        :type flatten: bool
        :param asApi: if this is True, the method will return an MSelectionList, if False, a list of PyObjects
        :type asApi: bool
        :return: The objects that belongs to this set
        :rtype: MSelectionList or list(PyObject,)
        """
        members = self.apimfn().getMembers(flatten=flatten)
        if asApi:
            return members
        else:
            return PyObjectFactory.fromMSelectionList(members)

    def removeMember(self, member):
        """
        Remove an object from this set
        
        :param member: the object
        :type member: str, PyObject, MDagPath, MObject, tuple(MDagPath, MObject)
        :return: None
        """
        member = self._processObject(member)
        self.apimfn().removeMember(member)

    def removeMembers(self, members):
        """
        Removes multiple objects from this set
        
        :param members: A list of objects
        :type members: MSelectionList, List of compatible objects (see addMember)
        :return: the MSelectionList that was removed
        :rtype: MSelectionList
        """
        if not isinstance(members, om2.MSelectionList):
            members = self._processList(members)
        self.apimfn().addMembers(members)
        return members

    def isMember(self, member):
        """
        Returns True if the object belongs to this set
        
        :param member: the object to test
        :type member: str, PyObject, MDagPath, MObject, tuple(MDagPath, MObject)
        :return: Whether the object belongs to this set or not
        :rtype: bool
        """
        member = self._processObject(member)
        return self.apimfn().isMember(member)

    def clear(self):
        """
        Removes all objects from this set
        
        :return: None
        """
        self.apimfn().clear()

    def _processObject(self, obj):
        if isinstance(obj, (str, unicode)):
            return self._processObject(api.toApiObject(obj))
        elif isinstance(obj, PyObject):
            return obj._getSelectableObject()
        elif isinstance(obj, tuple):
            if len(obj) != 2:
                raise ValueError('Tuples must have strictly 2 elements')
            if isinstance(obj[0], om2.MDagPath) and isinstance(obj[1], om2.MObject):
                return obj
            else:
                raise ValueError('Tuples must contain one MDagPath & one MObject')
        elif isinstance(obj, om2.MDagPath):
            return obj.node()
        elif isinstance(obj, (om2.MObject, om2.MPlug)):
            return obj
        else:
            raise TypeError('Incompatible object type : {}'.format(type(obj)))

    def _processList(self, lst):
        it = utils.Iterator(lst)
        result = om2.MSelectionList()
        while not it.isDone():
            obj = it.currentItem()
            obj = self._processObject(obj)
            result.add(obj)
            it.next()
        return result


# - GEOMETRY SHAPES
class GeometryShape(DagNode):
    def __init__(self, *args, **kwargs):
        super(GeometryShape, self).__init__(*args, **kwargs)


# TODO: see how to handle parameter components (and if we really need to...)
class ParameterFactory(object):
    def __init__(self, idCount, maxParam, mfn, geoShape):
        '''
        Factory class that builds parameters

        :param idCount: The dimension of the component
        :type idCount: int (1 or 2)
        :param maxParam: The maximum parameter value(s)
        :type maxParam: float or tuple of 2 floats
        :param mfn: MFn constant that determines the type of component
        :param geoShape: GeometryShape instance
        '''
        self.idCount = idCount
        if not isinstance(maxParam, (tuple, list)):
            self.max = [maxParam]
        else:
            self.max = maxParam
        self.mfn = mfn
        self.paramArray = []
        self.geoShape = geoShape

    def __len__(self):
        return self.max

    def __getitem__(self, item):
        # Make sure we haven't reached the max amount of indices
        if len(self.paramArray) >= self.idCount:
            raise RuntimeError('Cannot slice more than {} times'.format(self.idCount))

        currentId = len(self.paramArray)
        maxParam = self.max[currentId]
        if item > maxParam:
            raise ValueError('Parameter {} is out of bounds({})'.format(item, maxParam))
        self.paramArray.append(item)

        if len(self.paramArray) == self.idCount:
            return self.build()
        return self

    def _component(self):
        if self.idCount == 1:
            return
        else:
            return

    def build(self):
        pass


class Mesh(GeometryShape):
    _mfnClass = om2.MFnMesh
    _mfnConstant = om2.MFn.kMesh

    def __init__(self, *args, **kwargs):
        super(Mesh, self).__init__(*args, **kwargs)

    @classmethod
    def _create(cls, *args, **kwargs):
        """
        Create a new Mesh. [NOT UNDOABLE]

        see MFnMesh.create for a list of valid parameters
        :return: 
        """
        parent = kwargs.get('parent', om2.MObject.kNullObj)
        if isinstance(parent, PyObject):
            kwargs['parent'] = parent.apimobject()

        mfn = cls._mfnClass()
        obj = mfn.create(*args, **kwargs)
        return PyObjectFactory(MObject=obj)

    @classmethod
    def create(cls, *args, **kwargs):
        """
        WIP : Convenient access to _create while the undoability remains unimplemented
         
        :return: The mesh newly created
        :rtype:
        """
        return cls._create(*args, **kwargs)

    @property
    def vtx(self):
        mfn = self.apimfn()
        return ComponentFactory(idCount=1, maxLength=mfn.numVertices, mfn=om2.MFn.kMeshVertComponent, geoShape=self)

    @property
    def f(self):
        mfn = self.apimfn()
        return ComponentFactory(idCount=1, maxLength=mfn.numPolygons, mfn=om2.MFn.kMeshPolygonComponent, geoShape=self)

    @property
    def e(self):
        mfn = self.apimfn()
        return ComponentFactory(idCount=1, maxLength=mfn.numEdges, mfn=om2.MFn.kMeshEdgeComponent, geoShape=self)

    # Vertex methods
    @recycle_mfn
    def getPoint(self, index, **kwargs):
        """
        Get the position of a vertex
        
        :param index: Index of the vertex to get the position from 
        :param space: The space of the position to get, defaults to kObject
        
        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh
        
        :return: the position of the vertex in the given space
        :rtype: MPoint
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        return mfn.getPoint(index, space=space)

    @recycle_mfn
    def _setPoint(self, point, index, **kwargs):
        """
        Set the position of a vertex [NOT UNDOABLE]
        
        :param point: New position of the vertex
        :type point: MPoint
        :param index: Index of the vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh

        :return: the MFn used for this operation
        :rtype: MFnMesh
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        mfn.setPoint(index, point, space=space)
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoint(self, point, index, **kwargs):
        """
        Set the position of a vertex [UNDOABLE]

        :param point: New position of the vertex
        :type point: MPoint
        :param index: Index of the vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh

        :return: The ProxyModifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoint = self.getPoint(index=index, space=space, mfn=mfn)
        doKwargs = {'point': point, 'index': index, 'space': space, 'mfn': mfn}
        undoKwargs = {'point': oldPoint, 'index': index, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoint, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    @recycle_mfn
    def getPoints(self, **kwargs):
        """
        Get the position of all vertices on this mesh
 
        :param space: The space of the position to get, defaults to kObject

        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh

        :return: an array containing the positions of all the vertices
        :rtype: MPointArray
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        return mfn.getPoints(space=space)

    @recycle_mfn
    def _setPoints(self, points, **kwargs):
        """
        Set the position of all vertices [NOT UNDOABLE]

        :param points: Sequence of new positions for all vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh

        :return: the MFn used for this operation
        :rtype: MFnMesh
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        mfn.setPoints(points, space=space)
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoints(self, points, **kwargs):
        """
        Set the position of all vertices [UNDOABLE]

        :param points: Sequence of new positions for all vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnMesh object, defaults to None
        :type mfn: MFnMesh

        :return: The ProxyModifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoints = self.getPoints(space=space, mfn=mfn)
        doKwargs = {'points': points, 'space': space, 'mfn': mfn}
        undoKwargs = {'points': oldPoints, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoints, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    @property
    def numVertices(self):
        mfn = self.apimfn()
        return mfn.numVertices

    @property
    def numEdges(self):
        mfn = self.apimfn()
        return mfn.numEdges

    @property
    def numFaces(self):
        mfn = self.apimfn()
        return mfn.numPolygons

    @property
    def numUVSets(self):
        mfn = self.apimfn()
        return mfn.numUVSets


class NurbsCurve(GeometryShape):
    _mfnClass = om2.MFnNurbsCurve
    _mfnConstant = om2.MFn.kNurbsCurve

    def __init__(self, *args, **kwargs):
        super(NurbsCurve, self).__init__(*args, **kwargs)

    @classmethod
    def _create(cls, *args, **kwargs):
        """
        Create a new Mesh. [NOT UNDOABLE]

        see MFnMesh.create for a list of valid parameters
        :return: 
        """
        parent = kwargs.get('parent', om2.MObject.kNullObj)
        if isinstance(parent, PyObject):
            kwargs['parent'] = parent.apimobject()

        mfn = cls._mfnClass()
        obj = mfn.create(*args, **kwargs)
        return PyObjectFactory(MObject=obj)

    @classmethod
    def create(cls, *args, **kwargs):
        """
        WIP : Convenient access to _create while the undoability remains unimplemented

        :return: The mesh newly created
        :rtype:
        """
        return cls._create(*args, **kwargs)

    @property
    def cv(self):
        return ComponentFactory(idCount=1, maxLength=self.numCVs, mfn=om2.MFn.kCurveCVComponent, geoShape=self)

    @recycle_mfn
    def updateCurve(self, **kwargs):
        mfn = kwargs.get('mfn')
        mfn.updateCurve()
        return mfn

    # Points related Methods
    @recycle_mfn
    def getPoint(self, index, **kwargs):
        """
        Get the position of a Control Vertex

        :param index: Index of the control vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the position of the vertex in the given space
        :rtype: MPoint
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        return mfn.cvPosition(index, space=space)

    @recycle_mfn
    def _setPoint(self, point, index, **kwargs):
        """
        Set the position of a Control Vertex [NOT UNDOABLE]

        :param point: New position of the CV
        :type point: MPoint
        :param index: Index of the control vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the MFn used for this operation
        :rtype: MFnNurbsCurve
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        mfn.setCVPosition(index, point, space=space)
        mfn.updateCurve()
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoint(self, point, index, **kwargs):
        """
        Set the position of a Control Vertex [UNDOABLE]

        :param point: New position of the CV
        :type point: MPoint
        :param index: Index of the control vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the modifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoint = self.getPoint(index=index, space=space, mfn=mfn)
        doKwargs = {'point': point, 'index': index, 'space': space, 'mfn': mfn}
        undoKwargs = {'point': oldPoint, 'index': index, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoint, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    @recycle_mfn
    def getPoints(self, **kwargs):
        """
        Get the position of all control vertices on this mesh

        :param space: The space of the position to get, defaults to kObject

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: an array containing the positions of all the control vertices
        :rtype: MPointArray
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        return mfn.cvPositions(space=space)

    @recycle_mfn
    def _setPoints(self, points, **kwargs):
        """
        Set the position of all control vertices [NOT UNDOABLE]

        :param points: Sequence of new positions for all control vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the MFn used for this operation
        :rtype: MFnNurbsCurve
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        mfn.setCVPositions(points, space=space)
        mfn.updateCurve()
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoints(self, points, **kwargs):
        """
        Set the position of all control vertices [UNDOABLE]

        :param points: Sequence of new positions for all control vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: The ProxyModifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoints = self.getPoints(space=space, mfn=mfn)
        doKwargs = {'points': points, 'space': space, 'mfn': mfn}
        undoKwargs = {'points': oldPoints, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoints, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    # Param related Methods
    def getParamAtPoint(self, point, tolerance=0.001, space=om2.MSpace.kObject):
        """
        Gets the curve parameter that corresponds to the point
        :param point: the point on the curve
        :type point: MPoint or something that can be converted to one
        
        :param tolerance: max distance between the point and the curve
        :type tolerance: float
        
        :param space: space in which the point is provided
        :type space: MSpace.kObject, mSpace.kWorld
        
        :return: the U parameter on the curve
        """
        mfn = self.apimfn()
        point = api.DataType.toPoint(point)
        return mfn.getParamAtPoint(point, tolerance=tolerance, space=space)

    def getPointAtParam(self, param, space=om2.MSpace.kObject):
        """
        Gets the curve parameter that corresponds to the point
        :param param: the U parameter to get the point from
        :type param: float

        :param space: space in which the point is provided
        :type space: MSpace.kObject, mSpace.kWorld

        :return: the point at param, in the given space
        :rtype: MPoint
        """
        mfn = self.apimfn()
        return mfn.getPointAtParam(param, space=space)

    def findParamFromLength(self, length):
        """
        Returns the parameter at the given length on the curve
        :param length: distance along the curve
        :type length: float
        :return: parameter value at the given length
        :rtype: float
        """
        mfn = self.apimfn()
        return mfn.findParamFromLengh(length)

    def findLengthFromParam(self, param):
        """
        Returns the distance to a given parameter on the curve
        :param param: float
        :return: distance at given curve parameter
        :rtype: float
        """
        mfn = self.apimfn()
        return mfn.findLengthFromParam(param)

    # Properties
    @property
    def form(self):
        mfn = self.apimfn()
        return mfn.form

    @property
    def isOpen(self):
        if self.form == self._mfnClass.kOpen:
            return True

    @property
    def isClosed(self):
        if self.form == self._mfnClass.kClosed:
            return True

    @property
    def isPeriodic(self):
        if self.form == self._mfnClass.kPeriodic:
            return True

    @property
    def numCVs(self):
        mfn = self.apimfn()
        return mfn.numCVs

    @property
    def numKnots(self):
        mfn = self.apimfn()
        return mfn.numKnots

    @property
    def numSpans(self):
        mfn = self.apimfn()
        return mfn.numSpans

    @property
    def knotDomain(self):
        mfn = self.apimfn()
        return mfn.knotDomain


class NurbsSurface(GeometryShape):
    _mfnClass = om2.MFnNurbsSurface
    _mfnConstant = om2.MFn.kNurbsSurface

    def __init__(self, *args, **kwargs):
        super(NurbsSurface, self).__init__(*args, **kwargs)

    @classmethod
    def _create(cls, *args, **kwargs):
        """
        Create a new Mesh. [NOT UNDOABLE]

        see MFnMesh.create for a list of valid parameters
        :return: 
        """
        parent = kwargs.get('parent', om2.MObject.kNullObj)
        if isinstance(parent, PyObject):
            kwargs['parent'] = parent.apimobject()

        mfn = cls._mfnClass()
        obj = mfn.create(*args, **kwargs)
        return PyObjectFactory(MObject=obj)

    @classmethod
    def create(cls, *args, **kwargs):
        """
        WIP : Convenient access to _create while the undoability remains unimplemented

        :return: The mesh newly created
        :rtype:
        """
        return cls._create(*args, **kwargs)

    @property
    def cv(self):
        return ComponentFactory(idCount=2, maxLength=self.numCVsInUV, mfn=om2.MFn.kSurfaceCVComponent, geoShape=self)

    @recycle_mfn
    def updateCurve(self, **kwargs):
        mfn = kwargs.get('mfn')
        mfn.updateCurve()
        return mfn

    # Points related Methods
    @recycle_mfn
    def getPoint(self, index, **kwargs):
        """
        Get the position of a Control Vertex

        :param index: Index of the control vertex to get the position from
        :type index: tuple
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the position of the vertex in the given space
        :rtype: MPoint
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        u, v = index
        return mfn.cvPosition(u, v, space=space)

    @recycle_mfn
    def _setPoint(self, point, index, **kwargs):
        """
        Set the position of a Control Vertex [NOT UNDOABLE]

        :param point: New position of the CV
        :type point: MPoint
        :param index: Index of the control vertex to get the position from
        :type index: tuple
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the MFn used for this operation
        :rtype: MFnNurbsCurve
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        u, v = index
        mfn.setCVPosition(u, v, point, space=space)
        mfn.updateCurve()
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoint(self, point, index, **kwargs):
        """
        Set the position of a Control Vertex [UNDOABLE]

        :param point: New position of the CV
        :type point: MPoint
        :param index: Index of the control vertex to get the position from
        :type index: int
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the modifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoint = self.getPoint(index=index, space=space, mfn=mfn)
        doKwargs = {'point': point, 'index': index, 'space': space, 'mfn': mfn}
        undoKwargs = {'point': oldPoint, 'index': index, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoint, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    @recycle_mfn
    def getPoints(self, **kwargs):
        """
        Get the position of all control vertices on this mesh

        :param space: The space of the position to get, defaults to kObject

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: an array containing the positions of all the control vertices
        :rtype: MPointArray
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        return mfn.cvPositions(space=space)

    @recycle_mfn
    def _setPoints(self, points, **kwargs):
        """
        Set the position of all control vertices [NOT UNDOABLE]

        :param points: Sequence of new positions for all control vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: the MFn used for this operation
        :rtype: MFnNurbsCurve
        """
        mfn = kwargs.get('mfn')
        space = kwargs.get('space', om2.MSpace.kObject)
        mfn.setCVPositions(points, space=space)
        mfn.updateCurve()
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPoints(self, points, **kwargs):
        """
        Set the position of all control vertices [UNDOABLE]

        :param points: Sequence of new positions for all control vertices
        :type points: Seq of MPoint
        :param space: The space of the position to get, defaults to kObject
        :type space: MSpace.kObject, MSpace.kTransform

        :keyword mfn: optional MFnNurbsCurve object, defaults to None
        :type mfn: MFnNurbsCurve

        :return: The ProxyModifier used for this operation
        :rtype: ProxyModifier
        """
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)

        oldPoints = self.getPoints(space=space, mfn=mfn)
        doKwargs = {'points': points, 'space': space, 'mfn': mfn}
        undoKwargs = {'points': oldPoints, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPoints, doKwargs=doKwargs,
                                     undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    @property
    def numCVsInU(self):
        mfn = self.apimfn()
        return mfn.numCVsInU

    @property
    def numCVsInV(self):
        mfn = self.apimfn()
        return mfn.numCVsInV

    @property
    def numCVsInUV(self):
        mfn = self.apimfn()
        u = mfn.numCVsInU
        v = mfn.numCVsInV
        return u, v

    @property
    def numCVs(self):
        mfn = self.apimfn()
        u = mfn.numCVsInU
        v = mfn.numCVsInV
        return u*v

    @property
    def formInU(self):
        mfn = self.apimfn()
        return mfn.formInU

    @property
    def formInV(self):
        mfn = self.apimfn()
        return mfn.formInV

    @property
    def isOpenInU(self):
        if self.formInU == self._mfnClass.kOpen:
            return True

    @property
    def isOpenInV(self):
        if self.formInV == self._mfnClass.kOpen:
            return True

    @property
    def isClosedInU(self):
        if self.formInU == self._mfnClass.kClosed:
            return True

    @property
    def isClosedInV(self):
        if self.formInV == self._mfnClass.kClosed:
            return True

    @property
    def isPeriodicInU(self):
        if self.formInU == self._mfnClass.kPeriodic:
            return True

    @property
    def isPeriodicInV(self):
        if self.formInV == self._mfnClass.kPeriodic:
            return True

    @property
    def numKnotsInU(self):
        mfn = self.apimfn()
        return mfn.numKnotsInU

    @property
    def numKnotsInV(self):
        mfn = self.apimfn()
        return mfn.numKnotsInV

    @property
    def numSpansInU(self):
        mfn = self.apimfn()
        return mfn.numSpansInU

    @property
    def numSpansInV(self):
        mfn = self.apimfn()
        return mfn.numSpansInV

    @property
    def knotDomainInU(self):
        mfn = self.apimfn()
        return mfn.knotDomainInU

    @property
    def knotDomainInV(self):
        mfn = self.apimfn()
        return mfn.knotDomainInV


class LatticeShape(GeometryShape):
    _mfnClass = om2.MFnDagNode
    _mfnConstant = om2.MFn.kLattice

    def __init__(self, *args, **kwargs):
        super(LatticeShape, self).__init__(*args, **kwargs)

    @property
    def pt(self):
        return ComponentFactory(idCount=3, maxLength=self.numPointsInXYZ, mfn=om2.MFn.kLatticeComponent, geoShape=self)

    @property
    def numPointsInX(self):
        mfn = self.apimfn()
        plug = mfn.findPlug('sDivisions', False)
        return plug.asInt()

    @property
    def numPointsInY(self):
        mfn = self.apimfn()
        plug = mfn.findPlug('tDivisions', False)
        return plug.asInt()

    @property
    def numPointsInZ(self):
        mfn = self.apimfn()
        plug = mfn.findPlug('uDivisions', False)
        return plug.asInt()

    @property
    def numPointsInXYZ(self):
        mfn = self.apimfn()
        plugX = mfn.findPlug('sDivisions', False)
        plugY = mfn.findPlug('tDivisions', False)
        plugZ = mfn.findPlug('uDivisions', False)
        return plugX.asInt(), plugY.asInt(), plugZ.asInt()

    @property
    def numPoints(self):
        return utils.prodList(self.numPointsInXYZ)


# - COMPONENTS
class ComponentFactory(object):

    def __init__(self, idCount, maxLength, mfn, geoShape):
        '''
        Factory class that builds components
        
        :param idCount: The dimension of the component (Int between 1 & 3) 
        :param maxLength: The maximum amount of component (Int) 
        :param mfn: MFn constant that determines the type of component
        :param geoShape: GeometryShape instance
        '''
        self.idCount = idCount
        if not isinstance(maxLength, (tuple, list)):
            self.max = [maxLength]
        else:
            self.max = maxLength
        if len(self.max) != self.idCount:
            raise ValueError('maxLength parameter length must match the idCount')
        self.mfn = mfn
        self.geoShape = geoShape
        self.indexArray = []
        self.elements = None

    def __len__(self):
        return self.max

    def __getitem__(self, item):
        # Make sure we haven't reached the max amount of indices
        if len(self.indexArray) >= self.idCount:
            raise RuntimeError('Cannot slice more than {} times'.format(self.idCount))

        # Process item and feed it to the MIntArray
        array = om2.MIntArray()

        if not isinstance(item, (tuple, list, om2.MIntArray)):
            item = [item]

        it = utils.Iterator(item)
        itIndex = len(self.indexArray)
        while not it.isDone():
            i = it.currentItem()
            if isinstance(i, int):
                array.append(i)
            elif isinstance(i, slice):
                start = i.start
                stop = i.stop
                step = i.step

                if start is None:
                    start = 0
                if stop is None:
                    stop = self.max[itIndex] -1
                if step is None:
                    step = 1

                if step > 0:
                    stop += 1
                else:
                    stop -= 1
                for x in xrange(start, stop, step):
                    array.append(x)
            it.next()
        self.indexArray.append(array)

        # TODO: Should we put all the elements building stuff in a method instead of here ? to make it easier to read
        if len(self.indexArray) == self.idCount:
            if self.idCount == 1:
                self.elements = self.indexArray[0]
            else:
                count = utils.prodList([len(l) for l in self.indexArray])
                result = []

                def appendToResult(index, value):
                    if index >= len(result):
                        result.append([])
                    result[index].append(value)

                arrayIt = utils.Iterator(self.indexArray)
                while not arrayIt.isDone():
                    currentId = arrayIt.currentIndex()
                    idList = arrayIt.currentItem()
                    currentCount = utils.prodList([len(l) for l in self.indexArray[currentId:]])

                    i = 0
                    while i < count:
                        it = utils.Iterator(idList)
                        while not it.isDone():
                            for _ in xrange(currentCount/len(it)):
                                appendToResult(i, it.currentItem())
                                i += 1
                            it.next()
                    arrayIt.next()
                result = [tuple(seq) for seq in result]
                self.elements = result
            return self.build()
        return self

    @property
    def isValid(self):
        return len(self.indexArray) == self.idCount

    @property
    def _component(self):
        if self.idCount == 1:
            if self.mfn == om2.MFn.kMeshVertComponent:
                return MeshVertex
            elif self.mfn == om2.MFn.kMeshPolygonComponent:
                return MeshFace
            elif self.mfn == om2.MFn.kMeshEdgeComponent:
                return MeshEdge
            elif self.mfn == om2.MFn.kCurveCVComponent:
                return NurbsCurveCV
            else:
                return Component1D

        elif self.idCount == 2:
            if self.mfn == om2.MFn.kSurfaceCVComponent:
                return NurbsSurfaceCV
            else:
                return Component2D

        elif self.idCount == 3:
            if self.mfn == om2.MFn.kLatticeComponent:
                return LatticePoint
            else:
                return Component3D

        else:
            return Component

    def build(self):
        if self.isValid:
            compClass = self._component
            mfn = compClass._mfnClass(self.geoShape.apimobject())
            mfn.create(self.mfn)
            mfn.addElements(self.elements)

            comp = compClass(MDagPath=self.geoShape.apidagpath(), MObjectHandle=om2.MObjectHandle(mfn.object()),
                             node=self.geoShape)
        else:
            return None
        return comp


@add_metaclass(ABCMeta)
class Component(PyObject):
    _mfnClass = om2.MFnComponent
    _mitClass = om2.MItGeometry
    _mfnConstant = None
    _name = '.Component'

    _idCount = 1

    def __init__(self, *args, **kwargs):
        super(Component, self).__init__(*args, **kwargs)
        self._node = kwargs.get('node', None)

    def __getitem__(self, item):
        nodeMObj = self.node().apimobject()
        mfn = self._mfnClass(nodeMObj)
        mfn.create(self._mfnConstant)
        mfn.addElements(self._extractElement(item))
        comp = self.__class__(MDagPath=self.apidagpath(), MObjectHandle=om2.MObjectHandle(mfn.object()),
                              node=self.node)
        return comp

    def __len__(self):
        return self.apimfn().elementCount

    @abstractmethod
    def _extractElement(self, item):
        """
        Extracts a single element from the MFnComponent object at the given index
        :param item: The item to extract (Int) 
        :return: A Sequence that can be passed to the MFnComponent's addElements method
        """
        pass

    def apimfn(self):
        return self._mfnClass(self.apimobject())

    def apidagpath(self):
        return self.__apiInput__['MDagPath']

    def apimit(self):
        return self._mitClass(self.apidagpath(), self.apimobject())

    def apimitId(self, item):
        # it = self.apimit()
        # it.setIndex(item)
        mfn = self._mfnClass(self.node().apimobject())
        mfn.create(self._mfnConstant)
        mfn.addElements(item)
        it = self._mitClass(self.apidagpath(), mfn.object())
        return it

    @classmethod
    def getBuildDataFromName(cls, name):
        sel = om2.MSelectionList()
        sel.add(name)

        try:
            comp = sel.getComponent(0)
        except TypeError:
            raise TypeError('{} is not a valid component'.format(name))

        if comp[1] == om2.MObject.kNullObj:
            raise TypeError('{} is empty'.format(name))

        return {'MObjectHandle': om2.MObjectHandle(comp[1]), 'MDagPath': comp[0]}

    def _getSelectableObject(self):
        """
        Returns an object that can be added to an MSelectionList

        :rtype: tuple(MDagPath, MObject)
        """
        return self.apidagpath(), self.apimobject()

    def index(self, item=0):
        return self._extractElement(item=item)[0]

    def indices(self):
        return self.apimfn().getElements()

    def name(self, fullDagPath=False):
        fdp = self.apidagpath().fullPathName()
        if len(self) == 1:
            elem = self._extractElement(0)[0]
            if not isinstance(elem, (tuple, list)):
                compName = self._name + ''.join('[{}]'.format(elem))
            else:
                compName = self._name + ''.join('[{}]'.format(x) for x in elem)
        else:
            compName = self._name + 'Array'
        if fullDagPath:
            path = fdp
        else:
            path = fdp.split('|')[-1]
        return path + compName

    def node(self):
        if self._node is None:
            self._node = DependNode.create(MDagPath=self.apidagpath(), MObjectHandle=om2.MObjectHandle(self.apidagpath().node()))
        return self._node


@add_metaclass(ABCMeta)
class ComponentPoint(Component):
    """
    Abstract class that handles default point management
    """

    # Position methods
    def getPosition(self, **kwargs):
        """
        Get the position of a specific vertex

        :keyword item: the logical index of the component, defaults to 0
        :type item: int
        :keyword space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :keyword mfn: optional MFnComponent to avoid recreating one, defaults to None
        :type mfn: MFnSingleIndexedComponent

        :return: return the vertex's position in the given Space
        :rtype: MPoint
        """
        item = kwargs.get('item', 0)
        space = kwargs.get('space', om2.MSpace.kObject)

        vId = self._extractElement(item)[0]
        p = self.node().getPoint(index=vId, space=space)
        return p

    @recycle_mfn
    def _setPosition(self, *args, **kwargs):
        """
        Set the position of a specific vertex [NOT UNDOABLE]

        :param *args: New position of the point
        :type *args: MPoint, MFloatPoint, MVector, MFloatVector, seq

        :keyword relative: whether the new position is absolute or relative to the current position, defaults : False
        :type relative: bool
        :keyword item: the logical index of the component, defaults to 0
        :type item: int
        :keyword space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :keyword mfn: optional MFnComponent to avoid recreating one, defaults to None
        :type mfn: MFnSingleIndexedComponent

        :return: returns the iterator used so that it can be passed to something else
        :rtype: MItMeshVertex
        """
        self._preSetPosition(*args, **kwargs)

        item = kwargs.get('item', 0)
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)
        relative = kwargs.get('relative', False)

        if len(args) == 1:
            args = args[0]

        if relative:
            vector = api.DataType.toVector(args)
            point = self.getPosition(item=item, space=space, mfn=mfn) + vector
        else:
            point = api.DataType.toPoint(args)

        vId = mfn.element(item)
        self.node().setPoint(index=vId, point=point, space=space)

        self._postSetPosition(*args, **kwargs)
        return mfn

    @api.apiUndo
    @recycle_mfn
    def setPosition(self, *args, **kwargs):
        """
        Set the position of a specific vertex [UNDOABLE]

        :param args: MPoint or something that can be converted to one
        :type args: MPoint, MFloatPoint, MVector, MFloatVector, seq

        :keyword relative: whether the new position is absolute or relative to the current position, defaults : False
        :type relative: bool
        :keyword item: the logical index of the component, defaults to 0
        :type item: int
        :keyword space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :keyword mfn: optional MFnComponent to avoid recreating one, defaults to None
        :type mfn: MFnSingleIndexedComponent

        :return: return the ProxyModifier used for this operation
        :rtype: ProxyModifier
        """
        item = kwargs.get('item', 0)
        mfn = kwargs['mfn']
        space = kwargs.get('space', om2.MSpace.kObject)
        relative = kwargs.get('relative', False)

        oldPoint = self.getPosition(item=item, space=space, mfn=mfn)

        if len(args) == 1:
            args = args[0]

        if relative:
            vector = api.DataType.toVector(args)
            args = oldPoint + vector
        else:
            args = api.DataType.toPoint(args)

        doKwargs = {'item': item, 'space': space, 'mfn': mfn}
        undoKwargs = {'item': item, 'space': space, 'mfn': mfn}
        modifier = api.ProxyModifier(doFunc=self._setPosition, doArgs=[args], doKwargs=doKwargs,
                                     undoArgs=[oldPoint], undoKwargs=undoKwargs)
        modifier.doIt()
        return modifier

    def getPositions(self, space=om2.MSpace.kObject):
        """
        Get the position of all vertices

        :param space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :return: returns and array of the vertices positions in the given Space
        :rtype: MPointArray
        """
        it = self.apimit()
        result = om2.MPointArray()
        while not it.isDone():
            result.append(it.position(space=space))
            it.next()
        return result

    def _setPositions(self, points, space=om2.MSpace.kObject, relative=False):
        """
        Set the positions of all vertices [NOT UNDOABLE]

        :param points: a sequence of points whose length matches this instance's length
        :type points: list, tuple, MPointArray
        :param relative: whether the new position is absolute or relative to the current position, defaults : False
        :type relative: bool
        :param space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :return: None
        """
        it = self.apimit()
        self._preSetPositions(points, space=space, relative=relative, it=it)
        if it.count() != len(points):
            raise ValueError('The points array length does not match the vertex count')
        pIt = utils.Iterator(points)
        while not it.isDone():
            if relative:
                p = it.position(space=space) + api.DataType.toVector(pIt.currentItem())
            else:
                p = api.DataType.toPoint(pIt.currentItem())
            it.setPosition(p, space=space)
            it.next()
            pIt.next()
        self._postSetPositions(points, space=space, relative=relative, it=it)

    @api.apiUndo
    def setPositions(self, points, space=om2.MSpace.kObject, relative=False):
        """
        Set the positions of all vertices [UNDOABLE]

        :param points: a sequence of points whose length matches this instance's length
        :type points: list, tuple, MPointArray
        :param relative: whether the new position is absolute or relative to the current position, defaults : False
        :type relative: bool
        :param space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :return: the modifier used for this operation
        :rtype: ProxyModifier

        # This method stores the current points in an Array before setting the new value, then pass the old and new
        arrays in a ProxyModifier that will call _setPositions, making it undoable at low cost
        """

        it = self.apimit()
        oldPoints = om2.MPointArray()
        if it.count() != len(points):
            raise ValueError('The points array length does not match the vertex count')
        pIt = utils.Iterator(points)
        while not it.isDone():
            old = it.position(space=space)
            oldPoints.append(old)
            if relative:
                v = api.DataType.toVector(pIt.currentItem())
                p = old + v
            else:
                p = api.DataType.toPoint(pIt.currentItem())
            it.setPosition(p, space=space)
            it.next()
            pIt.next()

        doKwargs = {'points': points, 'space': space, 'relative': relative}
        undoKwargs = {'points': oldPoints, 'space': space}
        modifier = api.ProxyModifier(doFunc=self._setPositions, doKwargs=doKwargs, undoKwargs=undoKwargs)
        return modifier

    # Pre/Post positioning methods
    def _preSetPosition(self, *args, **kwargs):
        pass

    def _postSetPosition(self, *args, **kwargs):
        pass

    def _preSetPositions(self, *args, **kwargs):
        self._preSetPosition(*args, **kwargs)

    def _postSetPositions(self, *args, **kwargs):
        self._postSetPosition(*args, **kwargs)


class Component1D(Component):
    _mfnClass = om2.MFnSingleIndexedComponent

    _idCount = 1

    def __init__(self, *args, **kwargs):
        super(Component1D, self).__init__(*args, **kwargs)

    def _extractElement(self, item):
        elem = self.apimfn().element(item)
        return om2.MIntArray([elem])


class Component2D(Component):
    _mfnClass = om2.MFnDoubleIndexedComponent

    _idCount = 2

    def __init__(self, *args, **kwargs):
        super(Component2D, self).__init__(*args, **kwargs)

    def _extractElement(self, item):
        elem = self.apimfn().getElement(item)
        return [elem]


class Component3D(Component):
    _mfnClass = om2.MFnTripleIndexedComponent

    _idCount = 3

    def __init__(self, *args, **kwargs):
        super(Component3D, self).__init__(*args, **kwargs)

    def _extractElement(self, item):
        elem = self.apimfn().getElement(item)
        return [elem]


# ----- MESH COMPONENTS ----- #
class MeshVertex(Component1D, ComponentPoint):
    _mitClass = om2.MItMeshVertex
    _mfnConstant = om2.MFn.kMeshVertComponent
    _name = '.vtx'

    def __init__(self, *args, **kwargs):
        super(MeshVertex, self).__init__(*args, **kwargs)

    @recycle_mit
    def getConnectedEdges(self, **kwargs):
        it = kwargs['it']
        eIds = it.getConnectedEdges()
        if len(eIds):
            return self.node().e[eIds]

    @recycle_mit
    def getConnectedFaces(self, **kwargs):
        it = kwargs['it']
        fIds = it.getConnectedFaces()
        if len(fIds):
            return self.node().f[fIds]

    @recycle_mit
    def getConnectedVertices(self, **kwargs):
        it = kwargs['it']
        vIds = it.getConnectedVertices()
        if len(vIds):
            return self.node().vtx[vIds]

    @recycle_mit
    def numConnectedEdges(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedEdges()

    @recycle_mit
    def numConnectedFaces(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedFaces()

    @recycle_mit
    def numConnectedVertices(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedVertices()

    @recycle_mit
    def connectedToEdge(self, edge, **kwargs):
        it = kwargs['it']
        if isinstance(edge, MeshEdge):
            edge = edge.index()

        return it.connectedToEdge(edge)

    @recycle_mit
    def connectedToFace(self, face, **kwargs):
        it = kwargs['it']
        if isinstance(face, MeshFace):
            face = face.index()

        return it.connectedToFace(face)

    @recycle_mit
    def connectedToVertices(self, vertex, **kwargs):
        it = kwargs['it']
        if isinstance(vertex, MeshVertex):
            vertex = vertex.index()

        return it.connectedToVertices(vertex)


class MeshFace(Component1D):
    _mitClass = om2.MItMeshPolygon
    _mfnConstant = om2.MFn.kMeshPolygonComponent
    _name = '.f'

    def __init__(self, *args, **kwargs):
        super(MeshFace, self).__init__(*args, **kwargs)

    @recycle_mit
    def vertexCount(self, **kwargs):
        it = kwargs['it']
        return it.polygonVertexCount()

    @recycle_mit
    def vertexIndex(self, item, **kwargs):
        it = kwargs['it']
        return it.vertexIndex(item)

    @recycle_mit
    def getVertices(self, **kwargs):
        it = kwargs['it']
        vIds = it.getVertices()
        return self.node().vtx[vIds]

    @recycle_mit
    def getEdges(self, **kwargs):
        it = kwargs['it']
        #TODO

    @recycle_mit
    def getArea(self, space=om2.MSpace.kObject, **kwargs):
        it = kwargs['it']
        return it.getArea(space=space)

    @recycle_mit
    def getConnectedEdges(self, **kwargs):
        it = kwargs['it']
        eIds = it.getConnectedEdges()
        if len(eIds):
            return self.node().e[eIds]

    @recycle_mit
    def getConnectedFaces(self, **kwargs):
        it = kwargs['it']
        fIds = it.getConnectedFaces()
        if len(fIds):
            return self.node().f[fIds]

    @recycle_mit
    def getConnectedVertices(self, **kwargs):
        it = kwargs['it']
        vIds = it.getConnectedVertices()
        if len(vIds):
            return self.node().vtx[vIds]

    @recycle_mit
    def numConnectedEdges(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedEdges()

    @recycle_mit
    def numConnectedFaces(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedFaces()

    @recycle_mit
    def numConnectedVertices(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedVertices()

    @recycle_mit
    def connectedToEdge(self, edge, **kwargs):
        it = kwargs['it']
        if isinstance(edge, MeshEdge):
            edge = edge.index()

        return it.connectedToEdge(edge)

    @recycle_mit
    def connectedToFace(self, face, **kwargs):
        it = kwargs['it']
        if isinstance(face, MeshFace):
            face = face.index()

        return it.connectedToFace(face)

    @recycle_mit
    def connectedToVertices(self, vertex, **kwargs):
        it = kwargs['it']
        if isinstance(vertex, MeshVertex):
            vertex = vertex.index()

        return it.connectedToVertices(vertex)


class MeshEdge(Component1D):
    _mitClass = om2.MItMeshEdge
    _mfnConstant = om2.MFn.kMeshEdgeComponent
    _name = '.e'

    def __init__(self, *args ,**kwargs):
        super(MeshEdge, self).__init__(*args, **kwargs)

    @recycle_mit
    def vertexIndex(self, item, **kwargs):
        it = kwargs['it']
        return it.vertexId(item)

    @recycle_mit
    def getVertices(self, **kwargs):
        it = kwargs['it']
        vIds = (self.vertexIndex(0, it=it), self.vertexIndex(1, it=it))
        return self.node().vtx[vIds]

    @recycle_mit
    def getConnectedEdges(self, **kwargs):
        it = kwargs['it']
        eIds = it.getConnectedEdges()
        if len(eIds):
            return self.node().e[eIds]

    @recycle_mit
    def getConnectedFaces(self, **kwargs):
        it = kwargs['it']
        fIds = it.getConnectedFaces()
        if len(fIds):
            return self.node().f[fIds]

    @recycle_mit
    def numConnectedEdges(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedEdges()

    @recycle_mit
    def numConnectedFaces(self, **kwargs):
        it = kwargs['it']
        return it.numConnectedFaces()

    @recycle_mit
    def connectedToEdge(self, edge, **kwargs):
        it = kwargs['it']
        if isinstance(edge, MeshEdge):
            edge = edge.index()

        return it.connectedToEdge(edge)

    @recycle_mit
    def connectedToFace(self, face, **kwargs):
        it = kwargs['it']
        if isinstance(face, MeshFace):
            face = face.index()

        return it.connectedToFace(face)


# ----- NURBS COMPONENTS ----- #
class NurbsCurveCV(Component1D, ComponentPoint):
    _mfnConstant = om2.MFn.kCurveCVComponent
    _name = '.cv'

    def __init__(self, *args ,**kwargs):
        super(NurbsCurveCV, self).__init__(*args, **kwargs)

    def _postSetPosition(self, *args, **kwargs):
        node = self.node()
        node.updateCurve()


class NurbsSurfaceCV(Component2D, ComponentPoint):
    _mfnConstant = om2.MFn.kSurfaceCVComponent
    _name = '.cv'

    def __init__(self, *args, **kwargs):
        super(NurbsSurfaceCV, self).__init__(*args, **kwargs)

    def _postSetPosition(self, *args, **kwargs):
        node = self.node()
        node.updateSurface()


# ----- LATTICE COMPONENTS ----- #
class LatticePoint(Component3D):
    _mfnConstant = om2.MFn.kLatticeComponent
    _name = '.pt'

    def __init__(self, *args, **kwargs):
        super(LatticePoint, self).__init__(*args, **kwargs)

    # Position methods
    def getPosition(self, item=0, space=om2.MSpace.kObject):
        """
        Get the position of a specific vertex

        :keyword item: the logical index of the component, defaults to 0
        :type item: int
        :keyword space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :keyword mfn: optional MFnComponent to avoid recreating one, defaults to None
        :type mfn: MFnSingleIndexedComponent

        :return: return the vertex's position in the given Space
        :rtype: MPoint
        """
        mit = self.apimitId(self._extractElement(item))
        p = mit.position(space=space)
        return p

    def getPositions(self, space=om2.MSpace.kObject):
        """
        Get the position of all vertices

        :param space: the space in which you wish to operate, defaults to kObject
        :type space: MSpace.kObject, MSpace.kWorld

        :return: returns and array of the vertices positions in the given Space
        :rtype: MPointArray
        """
        it = self.apimit()
        return it.allPositions(space=space)