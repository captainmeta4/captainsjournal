from jinja2 import environment
import os

def os_get(key):
    return os.environ.get(key)

environment.filters['os_get']=os_get
