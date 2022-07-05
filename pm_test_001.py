import pymaya.core.general as pm
import pymaya.core.api as api
import pymaya.core.utilities as utils
#import pymaya.apiundo as apiundo

from maya.api import OpenMaya as om2

reload(pm)
reload(api)
reload(utils)

# PERF TESTING
'''
import time

st = time.time()
for x in range(10000):
    mplug.setFloat(x)
end = time.time()
print 'API :', end - st


st = time.time()
for x in range(10000):
    cmds.setAttr('pSphere1.translateX', x)
end = time.time()
print 'CMDS :', end - st

st = time.time()
for x in range(10000):
    _scene.pSphere1.translateX.set(x)
end = time.time()
print 'PYMEL :', end - st
'''