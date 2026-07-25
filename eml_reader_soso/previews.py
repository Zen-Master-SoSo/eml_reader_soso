#  eml_reader_soso/eml_reader_soso/previews.py
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
Implements previews using system xdg-open and temporary files.

Uses multithreading in order to wait for the system to respond after opening a
file using xdg-open.
"""
from os import write, unlink
from tempfile import mkstemp
from subprocess import Popen, PIPE, TimeoutExpired
from pathlib import Path
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QThreadPool, QRunnable
from qt_extras import DevilBox


class Previews(QThreadPool):
	"""
	Thread pool which manages Previews, which open attachments in a separate thread.
	"""

	__instance = None
	temporary_files = {}

	@classmethod
	def preview(cls, attachment):
		if cls.__instance is None:
			cls.__instance = Previews()
		cls.__instance._preview(attachment)

	@classmethod
	def cleanup_tempfiles(cls):
		if cls.__instance:
			for filename in cls.__instance.temporary_files.values():
				unlink(filename)

	def _preview(self, attachment):
		name_path = Path(attachment.Name)
		if name_path not in self.temporary_files:
			fd, filename = mkstemp(prefix = 'eml-', suffix = name_path.suffix)
			write(fd, attachment.Contents)
			self.temporary_files[name_path] = filename
		previewer = Previewer(self.temporary_files[name_path])
		previewer.signals.sig_error.connect(self.slot_error)
		self.start(previewer)

	@pyqtSlot(str)
	def slot_error(self, message):
		DevilBox(message)


class PreviewSignals(QObject):
	"""
	Contains signals used by Previewer QRunnable, (which may not contain signals)
	"""

	sig_error = pyqtSignal(str)


class Previewer(QRunnable):
	"""
	QRunnable which starts in a separate thread from the main thread, which shows a
	preview of an attachment using xdg-open and a temporary file.
	"""

	def __init__(self, filename):
		super().__init__()
		self.filename = filename
		self.signals = PreviewSignals()

	@pyqtSlot()
	def run(self):
		with Popen(["xdg-open", self.filename],
			stdout = PIPE, stderr = PIPE, text = True) as process:
			try:
				_, stderr = process.communicate(timeout = 5)
			except TimeoutExpired:
				return
			if process.returncode:
				self.signals.sig_error.emit(stderr)


#  end eml_reader_soso/eml_reader_soso/previews.py
