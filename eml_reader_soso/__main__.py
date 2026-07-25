#  eml_reader_soso/eml_reader_soso/__main__.py
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
A relatively lightweight .eml file viewer based on PyQt.
"""
import sys, logging
from os import environ
from argparse import ArgumentParser
from pathlib import Path
from shutil import copy2
from functools import lru_cache
from base64 import b64encode
from PyQt5 import uic
from PyQt5.Qt import QTextCursor, QTextDocument, QDateTime
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QSize, QDir, QMimeDatabase
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
	QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
	QLabel, QPushButton, QShortcut, QHBoxLayout, QLayout, QSizePolicy, QAction)
from PyQt5.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter
from lxml.html import fromstring, tostring
try:
	from EMLMailReader import MailReader
except ModuleNotFoundError:
	# Note: this is a hack that I use to get around the fact that my current
	# favorite linux distribution does not provide python past version 3.9, and the
	# emlmailreader package only works with Python >= 3.12.
	# See ../EMLMailReader/README.md
	sys.path.append(str(Path(__file__).parent.parent))
	from EMLMailReader import MailReader
from qt_extras import ShutUpQT, exceptions_hook
from qt_extras.list_layout import VListLayout, ColumnListLayout, HORIZONTAL_FLOW
from qt_extras.autofit import elide
from xdg_soso import is_xdg
from . import EmlReaderSetup
from .previews import Previews


SHOW_ATTACHMENTS_BY_DEFAULT = False
DATE_FORMAT = 'MMMM d, yyyy, h:mm a'
MAX_IMAGE_WIDTH = 640
BYTE_SIZES	= [
	(pow(2, 50), 'Pb'),
	(pow(2, 40), 'Tb'),
	(pow(2, 30), 'G'),
	(pow(2, 20), 'M'),
	(pow(2, 10), 'k'),
	(1, '')
]

def byte_size(n):
	"""
	Returns a (str) human-readable byte size (e.g. "50kb")
	"""
	for factor, suffix in BYTE_SIZES:
		if n >= factor: break
	return str(int(n / factor)) + suffix


class MainWindow(QMainWindow):
	"""
	Displays a single email at a time.
	"""

	def __init__(self):
		super().__init__()
		sys.excepthook = exceptions_hook
		self.mail_reader = MailReader()
		self.filepath = None
		self.message = None
		self.attachments = None
		self.filepaths = None
		self.last_filepath_index = None
		with ShutUpQT():
			uic.loadUi(str(Path(__file__).parent / 'main_window.ui'), self)
		self.setWindowIcon(QIcon.fromTheme('mail-mark-read'))
		shortcut = QShortcut(QKeySequence('ESC'), self)
		shortcut.activated.connect(self.close)
		for frame in [ self.frm_to, self.frm_from, self.frm_cc ]:
			lo = VListLayout()
			lo.setContentsMargins(0,0,0,0)
			lo.setSpacing(0)
			lo.setSizeConstraint(QLayout.SetNoConstraint)
			frame.setLayout(lo)
		lo = ColumnListLayout(flow = HORIZONTAL_FLOW)
		lo.setContentsMargins(2,2,2,2)
		lo.setSpacing(0)
		lo.setSizeConstraint(QLayout.SetNoConstraint)
		elide(self.lbl_subject)
		self.browser.document().setDefaultStyleSheet("""
QImage {
	width: 200;
	height: auto;
}
		""")
		self.frm_attachments.setLayout(lo)
		self.frm_attachments.layout().reflow(width = self.frm_attachments.width())
		self.frm_attachments.setVisible(False)
		self.b_show_attachments.clicked.connect(self.frm_attachments.setVisible)
		self.action_open.triggered.connect(self._slot_open)
		self.action_save_as.triggered.connect(self._slot_save_as)
		self.action_save_attachments.triggered.connect(self._slot_save_attachments)
		self.action_print.triggered.connect(self._slot_print)
		self.action_print_preview.triggered.connect(self._slot_print_preview)
		self.action_quit.triggered.connect(self.close)
		self.action_previous.triggered.connect(self._slot_previous)
		self.action_next.triggered.connect(self._slot_next)
		self.action_select_all.triggered.connect(self.browser.selectAll)
		self.action_copy.triggered.connect(self.browser.copy)

	# pylint: disable-next = invalid-name
	def closeEvent(self, _):
		Previews.cleanup_tempfiles()

	# pylint: disable-next = invalid-name
	def resizeEvent(self, _):
		self.frm_attachments.layout().reflow(width = self.frm_attachments.width())

	def _get_message(self):
		"""
		First step in getting a message; gets the message from the "_msgcache" function.
		The "_msgcache" function is a last-recently-used cache. The function arguments
		act as the key to the content that is cached. Passing the "mtime" of the
		requested .eml file ensures that if an email is changed the program was
		started, the cached copy of that .eml file is invalidated.
		"""
		return self._msgcache(self.filepath, self.filepath.stat().st_mtime)

	@lru_cache
	def _msgcache(self, filepath, mtime):
		"""
		Returns a new message from the given filepath, or cached, but only if the
		modification time of the file hasn't changed.
		"""
		with ShutUpQT():
			return self.mail_reader.get_email(filepath)

	def open(self, filename):
		self.setWindowTitle(str(self.filepath))
		self.lbl_date.setText('')
		self.lbl_subject.setText('')
		self.lbl_subject.setToolTip('')
		self.b_show_attachments.setText('')
		self.browser.clear()
		for frame in [ self.frm_to, self.frm_from, self.frm_cc, self.frm_attachments ]:
			frame.layout().clear()
		self.frm_attachments.layout().clear()
		self.b_show_attachments.setChecked(False)
		self.b_show_attachments.setEnabled(False)
		self.filepath = Path(filename)
		if self.filepath.exists():
			self.filepaths = sorted(list(path
				for path in self.filepath.parent.iterdir()
				if path.suffix == '.eml'))
			self.last_filepath_index = len(self.filepaths) - 1
			self.action_previous.setEnabled(bool(self.last_filepath_index))
			self.action_next.setEnabled(bool(self.last_filepath_index))
			self.setCursor(Qt.WaitCursor)
			self.message = self._get_message()
			QTimer.singleShot(1, self._show_email)
		else:
			QMessageBox.critical(self, 'File not found',
				f'Could not find the specified file: "{filename}"')

	def _show_email(self):
		self.date_object = QDateTime.fromString(self.message.Date, Qt.RFC2822Date)
		date_string = self.date_object.toString(DATE_FORMAT)
		self.lbl_date.setText(date_string)
		self.lbl_subject.setText(self.message.Subject)
		self.lbl_subject.setToolTip(self.message.Subject)
		from_address = AddressWidget(self.frm_from, self.message.From)
		self.frm_from.layout().append(from_address)
		self.setWindowTitle(
			f'"{self.message.Subject}" from {from_address.display_name}, {date_string}')
		for address in self.message.To.export_as_list():
			self.frm_to.layout().append(
				AddressWidget(self.frm_to, address))
		for address in self.message.Cc.export_as_list():
			self.frm_cc.layout().append(
				AddressWidget(self.frm_cc, address))
		self.attachments = self.message.Attachments.export_as_list()
		cnt = len(self.attachments)
		lbl = 'attachment' if cnt == 1 else 'attachments'
		self.b_show_attachments.setText(f'({cnt} {lbl})')
		has_attachments = cnt > 0
		self.b_show_attachments.setChecked(SHOW_ATTACHMENTS_BY_DEFAULT and has_attachments)
		self.b_show_attachments.setEnabled(has_attachments)
		self.action_save_attachments.setEnabled(has_attachments)
		for attachment in self.attachments:
			widget = AttachmentWidget(self.frm_attachments, attachment)
			widget.sig_save_request.connect(self._slot_save_attachment_request)
			self.frm_attachments.layout().append(widget)
		self.frm_attachments.layout().reflow(width = self.frm_attachments.width())
		self.frm_attachments.setVisible(SHOW_ATTACHMENTS_BY_DEFAULT and has_attachments)
		doc = fromstring(self.message.Body)
		try:
			for style in doc.head.findall('style'):
				style.drop_tree()
		except IndexError:
			pass
		for img in doc.iter(tag = 'img'):
			src = img.get('src')
			width = img.get('width')
			height = img.get('height')
			if width and height:
				width = int(width)
				height = int(height)
				ratio = height / width
				width = min(MAX_IMAGE_WIDTH, width)
				height = int(width * ratio)
			else:
				ratio = None
			img.clear()
			if src.startswith('cid:'):
				if att := self._attachment_by_cid(src[4:]):
					mime_type = att.ContentType.MediaType
					img.set('src', f'data:{mime_type};base64,' + \
						b64encode(att.Contents).decode())
				else:
					img.set('src', src)
			else:
				img.set('src', src)
			if ratio:
				img.set('width', str(width))
				img.set('height', str(height))
		self.browser.setHtml(tostring(doc, encoding = 'unicode'))
		for action in [
			self.action_select_all,
			self.action_copy,
			self.action_save_as,
			self.action_save_attachments,
			self.action_print,
			self.action_print_preview
		]:
			action.setEnabled(True)
		self.browser.setFocus()
		self.unsetCursor()

	def _attachment_by_cid(self, cid):
		for att in self.attachments:
			if att.ContentID == cid:
				return att
		return None

	@pyqtSlot()
	def _slot_open(self):
		filename, _ = QFileDialog.getOpenFileName(self,
			"Open .eml file",
			str(self.filepath.parent) if self.filepath else QDir.currentPath(),
			"Emails (*.eml)")
		if filename:
			self.open(filename)

	@pyqtSlot()
	def _slot_save_as(self):
		filename, _ = QFileDialog.getSaveFileName(
			self, 'Save a copy of this email as ...',
			str(self.filepath), "Email (*.eml)")
		if filename:
			copy2(self.filepath, filename)
			self.filepath = Path(filename)

	@pyqtSlot()
	def _slot_save_attachments(self):
		dirname = QFileDialog.getExistingDirectory(
			self, 'Directory to save attachments to ...',
			str(self.filepath.parent))
		if dirname:
			dirpath = Path(dirname)
			for attachment in self.attachments:
				save_path = dirpath / attachment.Name
				if save_path.exists():
					ret = QMessageBox(QMessageBox.Question, 'Confirm overwrite',
						f'"{save_path}" exists. Overwrite?',
						QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, self
					).exec()
					if ret == QMessageBox.Cancel:
						return
					if ret == QMessageBox.No:
						continue
				with open(save_path, 'bw') as fob:
					fob.write(attachment.Contents)

	@pyqtSlot(QWidget)
	def _slot_save_attachment_request(self, widget):
		dirname = QFileDialog.getExistingDirectory(
			self, f'Directory to save "{widget.attachment.Name}" ...',
			str(self.filepath.parent))
		if dirname:
			dirpath = Path(dirname)
			save_path = dirpath / widget.attachment.Name
			if save_path.exists():
				ret = QMessageBox(QMessageBox.Question, 'Confirm overwrite',
					f'"{save_path}" exists. Overwrite?',
					QMessageBox.Yes | QMessageBox.No, self
				).exec()
				if ret == QMessageBox.No:
					return
			with open(save_path, 'bw') as fob:
				fob.write(widget.attachment.Contents)

	def _prep_print_document(self):

		sep = ',&nbsp; '

		def header_addresses(address_collection):
			return sep.join([header_address(add)
				for add in address_collection.export_as_list()])

		def header_address(address):
			return f'<nobr>{address.DisplayName} ({address.Email})</nobr>'

		def header_attachments(attachment_collection):
			return sep.join([header_attachment(att)
				for att in attachment_collection.export_as_list()])

		def header_attachment(attachment):
			size = byte_size(len(attachment.Contents))
			return f'<nobr>{attachment.Name} ({size})</nobr>'

		def header_row(label, content):
			return f'<tr><td class="strong">{label}:</td><td>{content}</td></tr>'

		html = []
		html.append("""
<style>

body {
	font-weight: 100;
}

table.eml-soso-header-table {
	width: 100%;
	margin: 0;
	font-size: 10pt;
	line-height: 9pt;
}

table.eml-soso-header-table td {
	border: none;
	padding: 0 2px;
	margin: 0;
	vertical-align: top;
}

table.eml-soso-header-table td.strong {
	font-weight: 500;
}

</style>

<table class="eml-soso-header-table"><tbody>
""")
		for tup in [
			('From', header_address(self.message.From)),
			('Date', self.date_object.toString(DATE_FORMAT)),
			('To', header_addresses(self.message.To))
		]:
			html.append(header_row(*tup))
		if self.message.Cc.length():
			html.append(header_row('Cc', header_addresses(self.message.Cc)))
		html.append(header_row('Subject', self.message.Subject))
		if self.message.Attachments.length():
			html.append('</tbody></table><table class="eml-soso-header-table"><tbody>')
			html.append(header_row('Attachments',
				header_attachments(self.message.Attachments)))
		html.append('</tbody></table><p>&nbsp;</p>')
		self.print_document = self.browser.document().clone()
		cursor = QTextCursor(self.print_document)
		cursor.movePosition(QTextCursor.Start)
		cursor.insertHtml('\n'.join(html))

	@pyqtSlot()
	def _slot_print_preview(self):
		self._prep_print_document()
		preview_dialog = QPrintPreviewDialog(self)
		preview_dialog.paintRequested.connect(self._slot_preview_paint_requested)
		if preview_dialog.exec():
			printer = preview_dialog.printer()
			self.print_document.print(printer)

	@pyqtSlot(QPrinter)
	def _slot_preview_paint_requested(self, printer):
		self.print_document.print(printer)

	@pyqtSlot()
	def _slot_print(self):
		self._prep_print_document()
		printer_dialog = QPrintDialog(self)
		if printer_dialog.exec():
			printer = printer_dialog.printer()
			self.print_document.print(printer)

	@pyqtSlot()
	def _slot_previous(self):
		index = self.filepaths.index(self.filepath)
		self.open(self.filepaths[-1] \
			if index == 0 \
			else self.filepaths[index - 1])

	@pyqtSlot()
	def _slot_next(self):
		index = self.filepaths.index(self.filepath)
		self.open(self.filepaths[0] \
			if index == self.last_filepath_index \
			else self.filepaths[index + 1])


class AddressWidget(QLabel):
	"""
	QLabel which displays an email address as a copy-able link.
	"""

	def __init__(self, parent, address_object):
		super().__init__(parent)
		self.address_object = address_object
		self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
		self.setTextFormat(Qt.RichText)
		self.setTextInteractionFlags(Qt.TextBrowserInteraction)
		self.display_name = self.address_object.DisplayName
		self.setText(f'<a href="{self.address_object.Email}">{self.display_name}</a>')
		self.setToolTip(self.address_object.Email)


class AttachmentWidget(QWidget):
	"""
	QWidget which displays a single attachment.
	"""

	mimetype_database = None
	sig_save_request = pyqtSignal(QWidget)

	def __init__(self, parent, attachment):
		super().__init__(parent)
		self.attachment = attachment
		self.setStyleSheet("""
			QLabel:hover, QMenu::item:disabled {
				color: #000080;
			}
		""")
		lo = QHBoxLayout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(4)
		button = QPushButton(self)
		button.setIcon(self._icon(self.attachment))
		button.setIconSize(QSize(16, 16))
		button.setFixedSize(QSize(20, 20))
		lo.addWidget(button)
		label = QLabel(self.attachment.Name, self)
		label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
		lo.addWidget(label)
		self.setLayout(lo)
		button.clicked.connect(self._slot_preview)
		action = QAction(self.attachment.Name, self)
		action.setEnabled(False)
		self.addAction(action)
		action = QAction(self)
		action.setSeparator(True)
		self.addAction(action)
		action = QAction('Save as ...', self)
		action.triggered.connect(self._slot_save)
		self.addAction(action)
		action = QAction('Preview', self)
		action.triggered.connect(self._slot_preview)
		self.addAction(action)
		self.setContextMenuPolicy(Qt.ActionsContextMenu)

	# pylint: disable-next = invalid-name
	def mouseDoubleClickEvent(self, _):
		self._slot_preview()

	@pyqtSlot()
	def _slot_save(self):
		self.sig_save_request.emit(self)

	@pyqtSlot()
	def _slot_preview(self):
		Previews.preview(self.attachment)

	@classmethod
	def _icon(cls, attachment):
		if cls.mimetype_database is None:
			cls.mimetype_database = QMimeDatabase()
		q_mime_type = cls.mimetype_database.mimeTypeForData(attachment.Contents)
		icon_name = q_mime_type.iconName() or q_mime_type.genericIconName()
		return QIcon.fromTheme(icon_name)


def main():
	parser = ArgumentParser()
	parser.add_argument('Filename', type = str, nargs = '?',
		help='File name(s) or directory name(s)')
	if is_xdg():
		parser.add_argument("--install", "-i", action = "store_true",
			help = "Install icons and file associations for your desktop.")
		parser.add_argument("--uninstall", "-u", action = "store_true",
			help = "Remove icons and file associations.")
	parser.add_argument("--verbose", "-v", action = "store_true",
		help = "Show more detailed debug information.")
	parser.epilog = __doc__
	options = parser.parse_args()
	logging.basicConfig(
		level = logging.DEBUG if options.verbose else logging.ERROR,
		format = '[%(pathname)24s:%(lineno)-4d] %(levelname)-8s %(message)s'
	)

	if options.install:
		EmlReaderSetup().install()
	elif options.uninstall:
		EmlReaderSetup().uninstall()
	else:
		#-----------------------------------------------------------------------
		# Annoyance fix per:
		# https://stackoverflow.com/questions/986964/qt-session-management-error
		try:
			del environ['SESSION_MANAGER']
		except KeyError:
			pass
		#-----------------------------------------------------------------------
		app = QApplication([])
		window = MainWindow()
		if options.Filename:
			window.open(options.Filename)
		window.show()
		app.exec()


if __name__ == '__main__':
	sys.exit(main() or 0)


#  end eml_reader_soso/eml_reader_soso/__main__.py
