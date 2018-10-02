from jinja2 import Environment
import os

def os_get(key):
    return os.environ.get(key)

Environment.filters['os_get']=os_get
