import xml.etree.ElementTree as ET
from decouple import config
import os

UPLOAD_FOLDER = config('UPLOAD_FOLDER' )