import sys

for name in ['pymaya.core']:
    loaded_package_modules = [key for key, value in sys.modules.items() if name in str(value)]
    for key in loaded_package_modules:
            print('unloading...', key)
            del sys.modules[key]