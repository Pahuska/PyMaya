from types import StringTypes
from abc import ABCMeta, abstractmethod

from maya.api import OpenMaya as om2
import pymaya.core.utilities as utils
import pymaya.apiundo as apiundo

# Python V2 / V3 Compatibility
if utils.pyVersion == 2:
    _enum = object
else:
    from enum import Enum
    _enum = Enum
    xrange = range

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
        except RuntimeError:
            obj = sel.getDependNode(0)
            return obj


class ApiUndo(object):
    """
    Decorator to handle undoing & redoing API operations.
    The function it decorates must return either an object with undoIt & doIt methods, or None
    """
    def __init__(self, func):
        self._func = func

    def __call__(self, *args, **kwargs):
        result = self._func(*args, **kwargs)

        if result is not None:
            apiundo.commit(undo=result.undoIt, redo=result.doIt)
        return result


class AbstractModifier(object):
    __metaclass__ = ABCMeta

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.doIt()

    @abstractmethod
    def doIt(self):
        pass

    @abstractmethod
    def undoIt(self):
        pass


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
            if len(value) == numChildren:
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
            if not isinstance(value, (str, unicode)):
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


class DagModifier(object):
    MModifier = om2.MDagModifier


class DataType(_enum):
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
            print plug, attrType, value
        return om2.MVector(value)

    elif attrType == DataType.MATRIX:
        return om2.MMatrix(plug.asMObject(context))