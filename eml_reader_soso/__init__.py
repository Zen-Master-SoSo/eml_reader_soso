#  eml_reader_soso/eml_reader_soso/__init__.py
#
#  Copyright 2026 Leon Dionne <ldionne@dridesign.sh.cn>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
"""
A relatively lightweight graphical .eml file reader based on PyQt
"""
from xdg_soso import XDGSetup, XDGMime


__version__ = "0.0.0"


class EmlReaderSetup(XDGSetup):

	def __init__(self):
		super().__init__('eml_reader_soso', 'EML Reader SoSo')
		self._comment = eml_reader_soso.__doc__
		self._generic_icon = 'mail-mark-unread'
		self._categories = ['Utilities', 'Email']
		self._keywords = ['Email', 'Viewer']
		self.append_mime_type(XDGMime('message/rfc822'))


#  end eml_reader_soso/eml_reader_soso/__init__.py
