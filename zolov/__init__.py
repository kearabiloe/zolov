"""Promises, promises, promises."""
from __future__ import absolute_import, unicode_literals

import re

from collections import namedtuple

from .abstract import Voucher, Backend, Operator, Modems, test_mtn


__version__ = '0.0.1'
__author__ = 'Kearabiloe'
__contact__ = 'kearabiloe.ledwaba@gmail.com'
__homepage__ = 'http://github.com/kearabiloe/zolov'
__docformat__ = 'restructuredtext'

# -eof meta-

version_info_t = namedtuple('version_info_t', (
    'major', 'minor', 'micro', 'releaselevel', 'serial',
))
# bump version can only search for {current_version}
# so we have to parse the version here.
_temp = re.match(
    r'(\d+)\.(\d+).(\d+)(.+)?', __version__).groups()
VERSION = version_info = version_info_t(
    int(_temp[0]), int(_temp[1]), int(_temp[2]), _temp[3] or '', '')
del(_temp)
del(re)

__all__ = [
    'Voucher', 'Backend', 'Operator', 'Modems', 'test_mtn'
]
