from abc import ABCMeta, abstractmethod

from pymaya.py2x3 import _enum, xrange, add_metaclass
from maya.api import OpenMaya as om2
import pymaya.core.utilities as utils
import pymaya.apiundo as apiundo


@utils.timeit(name='ToApiObject', log=True, verbose=False)
def toApiObject(nodeName):
    if nodeName is None:
        return None

    if not utils.uniqueObjExists(nodeName):
        raise NameError('{} does not exist or is not unique'.format(nodeName))

    sel = om2.MSelectionList()
    sel.add(nodeName)

    if '.' in nodeName:     # In that case we either have a Plug or a Component
        try:
            plug = sel.getPlug(0)
            return plug
        except TypeError:
            try:
                comp = sel.getComponent(0)
                return comp
            except RuntimeError:
                return None
    else:       # Figure out if it's a DAG or DG
        try:
            dag = sel.getDagPath(0)
            return dag
        except TypeError:
            obj = sel.getDependNode(0)
            return obj


def apiUndo(func):
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            apiundo.commit(undo=result.undoIt, redo=result.doIt)
        return result
    return wrapped


@add_metaclass(ABCMeta)
class AbstractModifier(object):

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.doIt()

    @abstractmethod
    def doIt(self):
        pass

    @abstractmethod
    def undoIt(self):
        pass


class ProxyModifier(AbstractModifier):
    def __init__(self, doFunc, doArgs=None, doKwargs=None, undoFunc=None, undoArgs=None, undoKwargs=None):
        self._doIt = doFunc
        if undoFunc is None:
            self._undoIt = self._doIt
        else:
            self._undoIt = undoFunc

        if doArgs is None:
            self._doArgs = ()
        else:
            self._doArgs = doArgs

        if undoArgs is None:
            self._undoArgs = ()
        else:
            self._undoArgs = undoArgs

        if doKwargs is None:
            self._doKwargs = {}
        else:
            self._doKwargs = doKwargs

        if undoKwargs is None:
            self._undoKwargs = {}
        else:
            self._undoKwargs = undoKwargs

    def doIt(self):
        return self._doIt(*self._doArgs, **self._doKwargs)

    def undoIt(self):
        return self._undoIt(*self._undoArgs, **self._undoKwargs)


class DGModifier(AbstractModifier):
    MModifier = om2.MDGModifier

    def __init__(self):
        self.modifier = self.MModifier()

    def __getattr__(self, item):
        method = getattr(self.modifier, item)
        return method

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.doIt()

    def setPlugValue(self, plug, value, datatype=None):
        # if value is an MFnData object, pass it directly and stop there
        if isinstance(value, om2.MObject):
            self.modifier.newPlugValue(plug, value)
            return

        if datatype is None:
            datatype = DataType.fromMObject(plug.attribute())

        # Handle Compounds
        if plug.isCompound:
            numChildren = plug.numChildren()
            if len(value) >= numChildren:
                for x in xrange(numChildren):
                    self.setPlugValue(plug.child(x), value[x])
            else:
                raise ValueError('Compound Plug : value length does not match the amount of children')

        if datatype == DataType.FLOAT:
            self.modifier.newPlugValueFloat(plug, value)
        elif datatype in (DataType.INT, DataType.ENUM):
            self.modifier.newPlugValueInt(plug, value)
        elif datatype == DataType.BOOL:
            self.modifier.newPlugValueBool(plug, value)
        elif datatype == DataType.ANGLE:
            if not isinstance(value, om2.MAngle):
                value = DataType.toAngle(value)
            self.modifier.newPlugValueMAngle(plug, value)
        elif datatype == DataType.DISTANCE:
            if not isinstance(value, om2.MDistance):
                value = DataType.toDistance(value)
            self.modifier.newPlugValueMDistance(plug, value)
        elif datatype == DataType.STRING:
            if not isinstance(value, str):
                value = DataType.toString(value)
            self.modifier.newPlugValueString(plug, value)
        elif datatype == DataType.MATRIX:
            if not isinstance(value, (om2.MMatrix, om2.MTransformationMatrix)):
                value = DataType.toMatrix(value)
            self.newPlugValueMatrix(plug, value)
        elif datatype == DataType.TIME:
            if not isinstance(value, om2.MTime):
                value = DataType.toTime(value)
            self.modifier.newPlugValueMTime(value)

    def newPlugValueMatrix(self, plug, value):
        data = om2.MFnMatrixData()
        mobj = data.create(value)
        self.modifier.newPlugValue(plug, mobj)

    def createNode(self, nodeType, name=None):
        mobj = self.modifier.createNode(nodeType)
        if name is not None:
            self.modifier.renameNode(mobj, name)
        return mobj

    def doIt(self):
        return self.modifier.doIt()

    def undoIt(self):
        return self.modifier.undoIt()

    def connect(self, sPlug, dPlug, force=False, nextAvailable=False):
        src = dPlug.source()
        if not src.isNull and sPlug == src:
            return

        if dPlug.isLocked:
            raise AttributeError('Destination Plug {} is locked'.format(dPlug))

        if nextAvailable and dPlug.isArray:
            idx = dPlug.evaluateNumElements()
            dPlug = dPlug.elementByLogicalIndex(idx)

        if force:
            self.disconnect(dPlug)
        self.modifier.connect(sPlug, dPlug)

    def disconnect(self, *args):
        if len(args) == 1:
            dPlug = args[0]
            sPlug = dPlug.source()
        elif len(args) > 1:
            dPlug = args[1]
            sPlug = args[0]
        else:
            raise ValueError('disconnect needs at least one parameter, got 0')

        if sPlug.isNull:
            return

        self.modifier.disconnect(sPlug, dPlug)


class DagModifier(DGModifier):
    MModifier = om2.MDagModifier

    def createNode(self, nodeType, name=None, parent=om2.MObject.kNullObj):
        mobj = self.modifier.createNode(nodeType, parent=parent)
        if name is not None:
            self.modifier.renameNode(mobj, name)
        return mobj


class MultiModifier(AbstractModifier):
    def __init__(self, *args):
        self.modifiers = list(args)

    def append(self, modifier):
        self.modifiers.append(modifier)

    def extend(self, iterable):
        self.modifiers.extend(iterable)

    def getIterator(self):
        return utils.Iterator(self.modifiers)

    def doIt(self):
        it = self.getIterator()
        while not it.isDone():
            it.currentItem().doIt()
            it.next()

    def undoIt(self):
        it = self.getIterator()
        while not it.isDone():
            it.currentItem().undoIt()
            it.next()


class DataType(_enum):
    INVALID = 0
    DISTANCE = 1
    ANGLE = 2
    BOOL = 3
    FLOAT = 4
    INT = 5
    FLOAT2 = 6
    FLOAT3 = 7
    FLOAT4 = 8
    INT2 = 9
    INT3 = 10
    STRING = 11
    MATRIX = 12
    ENUM = 13
    TIME = 14
    MESSAGE = 15
    POINT = 16
    COLOR = 17

    @classmethod
    def fromMObject(cls, MObject):
        apiType = MObject.apiType()
        if apiType in [om2.MFn.kDoubleLinearAttribute, om2.MFn.kFloatLinearAttribute]:
            return cls.DISTANCE

        elif apiType in [om2.MFn.kDoubleAngleAttribute, om2.MFn.kFloatAngleAttribute]:
            return cls.ANGLE

        elif apiType == om2.MFn.kNumericAttribute:
            return cls.fromNumericAttr(om2.MFnNumericAttribute(MObject))

        elif apiType in [om2.MFn.kAttribute2Double, om2.MFn.kAttribute2Float]:
            return cls.FLOAT2

        elif apiType in [om2.MFn.kAttribute3Double, om2.MFn.kAttribute3Float]:
            return cls.FLOAT3

        elif apiType == om2.MFn.kAttribute4Double:
            return cls.FLOAT4

        elif apiType in [om2.MFn.kAttribute2Int, om2.MFn.kAttribute2Short]:
            return cls.INT2

        elif apiType in [om2.MFn.kAttribute3Int, om2.MFn.kAttribute3Short]:
            return cls.INT3

        elif apiType == om2.MFn.kTypedAttribute:
            return cls.fromTypedAttr(om2.MFnTypedAttribute(MObject))

        elif apiType == om2.MFn.kMatrixAttribute:
            return cls.MATRIX

        elif apiType == om2.MFn.kEnumAttribute:
            return cls.ENUM

        elif apiType == om2.MFn.kTimeAttribute:
            return cls.TIME

        elif apiType == om2.MFn.kMessageAttribute:
            return cls.MESSAGE

    @classmethod
    def fromNumericAttr(cls, numAttr):
        apiType = numAttr.numericType()
        if apiType == om2.MFnNumericData.kBoolean:
            return cls.BOOL
        elif apiType in [om2.MFnNumericData.kShort, om2.MFnNumericData.kInt, om2.MFnNumericData.kLong, om2.MFnNumericData.kByte]:
            return cls.INT
        elif apiType in [om2.MFnNumericData.kFloat, om2.MFnNumericData.kDouble, om2.MFnNumericData.kAddr]:
            return cls.FLOAT
        else:
            raise TypeError('Type {} not supported'.format(numAttr.object().apiTypeStr))

    @classmethod
    def fromTypedAttr(cls, typAttr):
        apiType = typAttr.attrType()
        if apiType == om2.MFnData.kString:
            return cls.STRING
        elif apiType == om2.MFnData.kMatrix:
            return cls.MATRIX
        else:
            raise TypeError('Type {} not supported'.format(typAttr.object().apiTypeStr))

    @classmethod
    def toDistance(cls, value, unit=om2.MDistance.uiUnit()):
        result = om2.MDistance(value, unit)
        return result

    @classmethod
    def toAngle(cls, value, unit=om2.MAngle.uiUnit()):
        result = om2.MAngle(value, unit)
        return result

    @classmethod
    def toEuler(cls, value, order=om2.MEulerRotation.kXYZ):
        assert len(value) == 3, 'Value must be a sequence of 3 floats'
        comp = [cls.toAngle(v).asRadians() for v in value]
        comp.append(order)
        return om2.MEulerRotation(*comp)

    @classmethod
    def toTime(cls, value, unit=om2.MTime.uiUnit()):
        result = om2.MTime(value, unit)
        return result

    @classmethod
    def toMatrix(cls, value):
        if isinstance(value, (list, tuple)):
            if len(value) == 4 and all([isinstance(x, (list, tuple)) for x in value]):
                value = [item for sublist in value for item in sublist]     # flatten list of list
            elif len(value) == 16:
                return om2.MMatrix(value)
            else:
                raise ValueError('{} does not represent a matrix'.format(value))
        else:
            raise ValueError('{} does not represent a matrix'.format(value))

    @classmethod
    def toString(cls, value):
        result = str(value)
        return result

    @classmethod
    def toPoint(cls, value):
        if isinstance(value, om2.MPoint):
            return value
        else:
            return om2.MPoint(value)

    @classmethod
    def toVector(cls, value):
        if isinstance(value, om2.MVector):
            return value
        else:
            return om2.MVector(value)

    @classmethod
    def getNumericTypes(cls):
        return cls.FLOAT, cls.FLOAT2, cls.FLOAT3, cls.FLOAT4, \
               cls.INT, cls.INT2, cls.INT3, \
               cls.BOOL

    @classmethod
    def getUnitTypes(cls):
        return cls.DISTANCE, cls.ANGLE, cls.TIME

    @classmethod
    def _mAttrDataConstantDict(cls):
        return {cls.DISTANCE: om2.MFnUnitAttribute.kDistance,
                cls.ANGLE: om2.MFnUnitAttribute.kAngle,
                cls.TIME: om2.MFnUnitAttribute.kTime,
                cls.BOOL: om2.MFnNumericData.kBoolean,
                cls.FLOAT: om2.MFnNumericData.kFloat,
                cls.FLOAT2: om2.MFnNumericData.k2Float,
                cls.FLOAT3: om2.MFnNumericData.k3Float,
                cls.FLOAT4: om2.MFnNumericData.k4Double,
                cls.INT: om2.MFnNumericData.kInt,
                cls.INT2: om2.MFnNumericData.k2Int,
                cls.INT3: om2.MFnNumericData.k3Int}

    @classmethod
    def asMAttrDataConstant(cls, constant):
        dic = cls._mAttrDataConstantDict()
        result = dic.get(constant)
        return result


def getPlugValue(plug, attrType=None, asString=False, context=om2.MDGContext.kNormal):
    if not isinstance(plug, om2.MPlug):
        raise TypeError('plug argument must be an MPlug, got {} instead'.format(type(plug)))
    if attrType is None:
        attrType = DataType.fromMObject(plug.attribute())

    if attrType == DataType.DISTANCE:
        d = plug.asMDistance(context)
        return d.asUnits(d.uiUnit())

    elif attrType == DataType.ANGLE:
        a = plug.asMAngle(context)
        return a.asUnits(a.uiUnit())

    elif attrType == DataType.FLOAT:
        return plug.asFloat(context)

    elif attrType == DataType.BOOL:
        return plug.asBool(context)

    elif attrType == DataType.INT:
        return plug.asInt(context)

    elif attrType == DataType.ENUM:
        if asString:
            e = om2.MFnEnumAttribute(plug.attribute())
            return e.fieldName(plug.asInt(context))
        else:
            return plug.asInt(context)

    elif attrType == DataType.STRING:
        return plug.asString(context)

    elif attrType == DataType.TIME:
        t = plug.asMTime(context)
        return t.asUnits(t.uiUnit())

    elif attrType in (DataType.FLOAT2, DataType.FLOAT3, DataType.FLOAT4, DataType.INT2, DataType.INT3):
        value = [getPlugValue(plug.child(x), context=context) for x in xrange(plug.numChildren())]
        if attrType in (DataType.FLOAT3, DataType.INT3):
            return om2.MVector(value)
        return value

    elif attrType == DataType.MATRIX:       # FIXME: Matrix Doesn't work ! Gotta pass through a MFnMatrixData
        mobj = plug.asMObject(context)
        matrix = om2.MFnMatrixData(mobj).matrix()
        return om2.MMatrix(matrix)

    elif attrType == DataType.MESSAGE:
        if plug.isDestination:
            return plug.source().node()
        else:
            return None
    else:
        raise TypeError('Unsupported plug type')


def sliceItemToMIntArray(item, array=None, inclusive=False):
    if array is None:
        array = om2.MIntArray()

    if not isinstance(item, tuple):
        item = [item]
    for i in item:
        if isinstance(i, int):
            array.append(i)
        elif isinstance(i, slice):
            start = slice.start
            stop = slice.stop
            step = 1
            if i.step is not None:
                step = i.step
            stop = i.stop
            if inclusive:
                stop += 1
            for x in xrange(i.start, stop, step):
                array.append(x)
    return array