"""NVDA global plugin to play specific sounds for Windows notifications which
match specific text.
This plugin reads a file called notificationSounds.conf in your NVDA
configuration directory; e.g. %appdata%\nvda\notificationSounds.conf.
Each line should contain a regular expression, followed by a tab, followed by
the full path to a .wav file to play if a notification contains the expression.
An optional third, tab-separated field may contain the space-separated flags
"st" (plain string) and "ci" (case insensitive).
For example:

doorbell pressed	C:\\sounds\\doorbell.wav	st ci
"""

import os
import re

import globalPluginHandler
import globalVars
import gui
import gui.settingsDialogs
import NVDAObjects.behaviors
import nvwave
import wx
from gui import guiHelper


configPath = None


def _getConfigEntries():
	try:
		with open(configPath, "r", encoding="utf-8") as configFile:
			for line in configFile:
				fields = line.rstrip("\r\n").split("\t", 2)
				if len(fields) < 2:
					continue
				text, wavPath = fields[:2]
				flags = fields[2].split() if len(fields) == 3 else []
				yield text, wavPath, "st" in flags, "ci" not in flags
	except OSError:
		return


class NotificationSoundDialog(wx.Dialog):
	def __init__(self, parent, title, rule=None):
		super().__init__(parent, title=title)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.textCtrl = sHelper.addLabeledControl(_("When notification &contains:"), wx.TextCtrl)
		self.matchType = sHelper.addItem(
			wx.RadioBox(
				self,
				label=_("Match type"),
				choices=(_("&Plain text"), _("&Regular expression")),
				style=wx.RA_SPECIFY_ROWS,
			),
		)
		self.caseSensitiveCheckBox = sHelper.addItem(wx.CheckBox(self, label=_("C&ase sensitive")))
		self.soundCtrl = sHelper.addLabeledControl(_("&Sound:"), wx.TextCtrl)
		sHelper.addItem(
			wx.Button(self, label=_('Choose &file...')),
		).Bind(wx.EVT_BUTTON, self.onChooseSound)
		sHelper.addDialogDismissButtons(wx.OK | wx.CANCEL, separated=True)
		self.SetSizer(sHelper.sizer)
		sHelper.sizer.Fit(self)
		self.CentreOnParent()
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		if rule:
			text, wavPath, plainText, caseSensitive = rule
			self.textCtrl.SetValue(text)
			self.matchType.SetSelection(0 if plainText else 1)
			self.caseSensitiveCheckBox.SetValue(caseSensitive)
			self.soundCtrl.SetValue(wavPath)
		else:
			self.matchType.SetSelection(0)
			self.caseSensitiveCheckBox.SetValue(True)
		self.textCtrl.SetFocus()

	def onChooseSound(self, evt):
		soundPath = self.soundCtrl.GetValue()
		dialog = wx.FileDialog(
			self,
			message=_("Choose a sound"),
			defaultDir=os.path.dirname(soundPath),
			defaultFile=os.path.basename(soundPath),
			wildcard=_("WAV files (*.wav)|*.wav"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() == wx.ID_OK:
				self.soundCtrl.SetValue(dialog.GetPath())
		finally:
			dialog.Destroy()

	def onOk(self, evt):
		text = self.textCtrl.GetValue()
		wavPath = self.soundCtrl.GetValue()
		if not text or not wavPath:
			gui.messageBox(
				_("Notification text and a sound file are required."),
				_("Notification sound"),
				wx.OK | wx.ICON_WARNING,
				self,
			)
			return
		if self.matchType.GetSelection() == 1:
			try:
				re.compile(text)
			except re.error as error:
				gui.messageBox(
					_("The regular expression is invalid: {error}").format(error=error),
					_("Notification sound"),
					wx.OK | wx.ICON_WARNING,
					self,
				)
				self.textCtrl.SetFocus()
				return
		evt.Skip()

	def getRule(self):
		return (
			self.textCtrl.GetValue(),
			self.soundCtrl.GetValue(),
			self.matchType.GetSelection() == 0,
			bool(self.caseSensitiveCheckBox.GetValue()),
		)


class NotificationSoundsSettingsPanel(gui.settingsDialogs.SettingsPanel):
	title = _("Notification sounds")

	def makeSettings(self, sizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		self.rules = list(_getConfigEntries())
		self.rulesList = sHelper.addLabeledControl(
			_("&Notification sounds"),
			wx.ListCtrl,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
		)
		self.rulesList.AppendColumn(_("Text"), width=200)
		self.rulesList.AppendColumn(_("Sound"), width=250)
		self.rulesList.AppendColumn(_("Options"), width=180)
		self.rulesList.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onEdit)
		self._refreshRulesList()
		bHelper = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(self, label=_("&Add")).Bind(wx.EVT_BUTTON, self.onAdd)
		bHelper.addButton(self, label=_("&Edit")).Bind(wx.EVT_BUTTON, self.onEdit)
		bHelper.addButton(self, label=_("&Remove")).Bind(wx.EVT_BUTTON, self.onRemove)
		sHelper.addItem(bHelper, flag=wx.EXPAND)

	def postInit(self):
		self.rulesList.SetFocus()

	def _formatOptions(self, rule):
		plainText = rule[2]
		caseSensitive = rule[3]
		return _("{matchType}, {caseType}").format(
			matchType=_("plain text") if plainText else _("regular expression"),
			caseType=_("case sensitive") if caseSensitive else _("case insensitive"),
		)

	def _refreshRulesList(self, selectedIndex=None):
		self.rulesList.DeleteAllItems()
		for rule in self.rules:
			self.rulesList.Append((rule[0], rule[1], self._formatOptions(rule)))
		if selectedIndex is not None:
			self.rulesList.Select(selectedIndex)
			self.rulesList.Focus(selectedIndex)

	def onAdd(self, evt):
		dialog = NotificationSoundDialog(self, _("Add notification sound"))
		try:
			if dialog.ShowModal() == wx.ID_OK:
				self.rules.append(dialog.getRule())
				self._refreshRulesList(len(self.rules) - 1)
		finally:
			dialog.Destroy()

	def onEdit(self, evt):
		index = self.rulesList.GetFirstSelected()
		if index < 0:
			return
		dialog = NotificationSoundDialog(self, _("Edit notification sound"), self.rules[index])
		try:
			if dialog.ShowModal() == wx.ID_OK:
				self.rules[index] = dialog.getRule()
				self._refreshRulesList(index)
		finally:
			dialog.Destroy()

	def onRemove(self, evt):
		index = self.rulesList.GetFirstSelected()
		if index < 0:
			return
		del self.rules[index]
		self._refreshRulesList(min(index, len(self.rules) - 1) if self.rules else None)

	def onSave(self):
		with open(configPath, "w", encoding="utf-8") as configFile:
			for text, wavPath, plainText, caseSensitive in self.rules:
				flags = []
				if plainText:
					flags.append("st")
				if not caseSensitive:
					flags.append("ci")
				line = "\t".join((text, wavPath))
				if flags:
					line += "\t" + " ".join(flags)
				configFile.write(line + "\n")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		global configPath
		super().__init__()
		configPath = os.path.join(globalVars.appArgs.configPath, "notificationSounds.conf")
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(NotificationSoundsSettingsPanel)

	def terminate(self):
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NotificationSoundsSettingsPanel)

	def _getConfig(self):
		for regexpToSearch, wavPath, plainText, caseSensitive in _getConfigEntries():
			if plainText:
				regexpToSearch = re.escape(regexpToSearch)
			reFlags = 0 if caseSensitive else re.IGNORECASE
			try:
				yield re.compile(regexpToSearch, reFlags), wavPath
			except re.error:
				continue

	def event_UIA_window_windowOpen(self, obj, nextHandler):
		try:
			if not isinstance(obj, NVDAObjects.behaviors.Notification):
				return
			for regexpToSearch, wavPath in self._getConfig():
				if regexpToSearch.search(obj.name):
					nvwave.playWaveFile(wavPath)
					break
		except OSError:
			pass
		finally:
			nextHandler()
