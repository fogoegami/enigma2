from Tools.Profile import profile
profile("LOAD:ElementTree")
import xml.etree.cElementTree
import os

profile("LOAD:enigma_skin")
from enigma import eSize, ePoint, eRect, gFont, eWindow, eLabel, ePixmap, eWindowStyleManager, addFont, gRGB, eWindowStyleSkinned, getDesktop
from Components.config import ConfigSubsection, ConfigText, config
from Components.Converter.Converter import Converter
from Components.Sources.Source import Source, ObsoleteSource
from Tools.Directories import resolveFilename, SCOPE_SKIN, SCOPE_FONTS, SCOPE_CURRENT_SKIN, SCOPE_CONFIG, fileExists, SCOPE_SKIN_IMAGE
from Tools.Import import my_import
from Tools.LoadPixmap import LoadPixmap
from Components.RcModel import rc_model
from Components.SystemInfo import SystemInfo

colorNames = {}
switchPixmap = {}
# Predefined fonts, typically used in built-in screens and for components like
# the movie list and so.
fonts = {
	"Body": ("Regular", 18, 22, 16),
	"ChoiceList": ("Regular", 20, 24, 18),
}

parameters = {}

def dump(x, i=0):
	print " " * i + str(x)
	try:
		for n in x.childNodes:
			dump(n, i + 1)
	except:
		None

class SkinError(Exception):
	def __init__(self, message):
		self.msg = message

	def __str__(self):
		return "{%s}: %s. Please contact the skin's author!" % (config.skin.primary_skin.value, self.msg)

dom_skins = [ ]

def addSkin(name, scope = SCOPE_CURRENT_SKIN):
	# read the skin
	filename = resolveFilename(scope, name)
	if fileExists(filename):
		mpath = os.path.dirname(filename) + "/"
		try:
			dom_skins.append((mpath, xml.etree.cElementTree.parse(filename).getroot()))
		except:
			print "[SKIN ERROR] error in %s" % filename
			return False
		else:
			return True
	return False

# get own skin_user_skinname.xml file, if exist
def skin_user_skinname():
	name = "skin_user_" + config.skin.primary_skin.value[:config.skin.primary_skin.value.rfind('/')] + ".xml"
	filename = resolveFilename(SCOPE_CONFIG, name)
	if fileExists(filename):
		return name
	return None

# we do our best to always select the "right" value
# skins are loaded in order of priority: skin with
# highest priority is loaded last, usually the user-provided
# skin.

# currently, loadSingleSkinData (colors, bordersets etc.)
# are applied one-after-each, in order of ascending priority.
# the dom_skin will keep all screens in descending priority,
# so the first screen found will be used.

# example: loadSkin("nemesis_greenline/skin.xml")
config.skin = ConfigSubsection()
DEFAULT_SKIN = SystemInfo["HasFullHDSkinSupport"] and "Adriatic-HD/skin.xml" or "PLi-FullNightHD/skin.xml"
# on SD hardware, PLi-HD will not be available
if not fileExists(resolveFilename(SCOPE_SKIN, DEFAULT_SKIN)):
	# in that case, fallback to Magic (which is an SD skin)
	DEFAULT_SKIN = "Adriatic-HD/skin.xml"
	if not fileExists(resolveFilename(SCOPE_SKIN, DEFAULT_SKIN)):
		DEFAULT_SKIN = "skin.xml"
config.skin.primary_skin = ConfigText(default=DEFAULT_SKIN)

profile("LoadSkin")
res = None
name = skin_user_skinname()
if name:
	res = addSkin(name, SCOPE_CONFIG)
if not name or not res:
	addSkin('skin_user.xml', SCOPE_CONFIG)

# some boxes lie about their dimensions
addSkin('skin_box.xml')
# add optional discrete second infobar
addSkin('skin_second_infobar.xml')

display_skin_id = 1
addSkin('skin_display.xml')
addSkin('skin_text.xml')
addSkin('skin_subtitles.xml')

try:
	if not addSkin(config.skin.primary_skin.value):
		raise SkinError, "primary skin not found"
except Exception, err:
	print "SKIN ERROR:", err
	skin = DEFAULT_SKIN
	if config.skin.primary_skin.value == skin:
		skin = 'skin.xml'
	print "defaulting to standard skin...", skin
	config.skin.primary_skin.value = skin
	addSkin(skin)
	del skin

addSkin('skin_default.xml')
profile("LoadSkinDefaultDone")

#
# Convert a string into a number. Used to convert object position and size attributes into a number
#    s is the input string.
#    e is the the parent object size to do relative calculations on parent
#    size is the size of the object size (e.g. width or height)
#    font is a font object to calculate relative to font sizes
# Note some constructs for speeding # up simple cases that are very common.
# Can do things like:  10+center-10w+4%
# To center the widget on the parent widget,
#    but move forward 10 pixels and 4% of parent width
#    and 10 character widths backward
# Multiplication, division and subexprsssions are also allowed: 3*(e-c/2)
#
# Usage:  center : center the object on parent based on parent size and object size
#         e      : take the parent size/width
#         c      : take the center point of parent size/width
#         %      : take given percentag of parent size/width
#         w      : multiply by current font width
#         h      : multiply by current font height
#
def parseCoordinate(s, e, size=0, font=None):
	s = s.strip()
	if s == "center":		# for speed, can be common case
		val = (e - size)/2
	elif s == '*':
		return None
	else:
		try:
			val = int(s)	# for speed
		except:
			if 't' in s:
				s = s.replace("center", str((e-size)/2.0))
			if 'e' in s:
				s = s.replace("e", str(e))
			if 'c' in s:
				s = s.replace("c", str(e/2.0))
			if 'w' in s:
				s = s.replace("w", "*" + str(fonts[font][3]))
			if 'h' in s:
				s = s.replace("h", "*" + str(fonts[font][2]))
			if '%' in s:
				s = s.replace("%", "*" + str(e/100.0))
			try:
				val = int(s) # for speed
			except:
				val = eval(s)
	if val < 0:
		return 0
	return int(val)  # make sure an integer value is returned


def getParentSize(object, desktop):
	size = eSize()
	if object:
		parent = object.getParent()
		# For some widgets (e.g. ScrollLabel) the skin attributes are applied to
		# a child widget, instead of to the widget itself. In that case, the parent
		# we have here is not the real parent, but it is the main widget.
		# We have to go one level higher to get the actual parent.
		# We can detect this because the 'parent' will not have a size yet
		# (the main widget's size will be calculated internally, as soon as the child
		# widget has parsed the skin attributes)
		if parent and parent.size().isEmpty():
			parent = parent.getParent()
		if parent:
			size = parent.size()
		elif desktop:
			#widget has no parent, use desktop size instead for relative coordinates
			size = desktop.size()
	return size

def parseValuePair(s, scale, object = None, desktop = None, size = None):
	x, y = s.split(',')
	parentsize = eSize()
	if object and ('c' in x or 'c' in y or 'e' in x or 'e' in y or
	               '%' in x or '%' in y):          # need parent size for ce%
		parentsize = getParentSize(object, desktop)
	xval = parseCoordinate(x, parentsize.width(), size and size.width() or 0)
	yval = parseCoordinate(y, parentsize.height(), size and size.height() or 0)
	return (xval * scale[0][0] / scale[0][1], yval * scale[1][0] / scale[1][1])

def parsePosition(s, scale, object = None, desktop = None, size = None):
	(x, y) = parseValuePair(s, scale, object, desktop, size)
	return ePoint(x, y)

def parseSize(s, scale, object = None, desktop = None):
	(x, y) = parseValuePair(s, scale, object, desktop)
	return eSize(x, y)

def parseFont(s, scale):
	try:
		f = fonts[s]
		name = f[0]
		size = f[1]
	except:
		name, size = s.split(';')
	return gFont(name, int(size) * scale[0][0] / scale[0][1])

def parseColor(s):
	if s[0] != '#':
		try:
			return colorNames[s]
		except:
			raise SkinError("color '%s' must be #aarrggbb or valid named color" % s)
	return gRGB(int(s[1:], 0x10))

def parseParameter(s):
	"""This function is responsible for parsing parameters in the skin, it can parse integers, floats, hex colors, hex integers and named colors."""
	if s[0] == '#':
		return int(s[1:], 16)
	elif s[:2] == '0x':
		return int(s, 16)
	elif '.' in s:
		return float(s)
	elif s in colorNames:
		return colorNames[s].argb()
	else:
		return int(s)

def collectAttributes(skinAttributes, node, context, skin_path_prefix=None, ignore=(), filenames=frozenset(("pixmap", "pointer", "seek_pointer", "backgroundPixmap", "selectionPixmap", "sliderPixmap", "scrollbarSliderPicture", "scrollbarbackgroundPixmap", "scrollbarBackgroundPicture"))):
	# walk all attributes
	size = None
	pos = None
	font = None
	for attrib, value in node.items():
		if attrib not in ignore:
			if attrib in filenames:
				if "pointer" in attrib:
					value = "%s%s%s" % (resolveFilename(SCOPE_CURRENT_SKIN, value.split(":")[0], path_prefix=skin_path_prefix), ":", value.split(":")[1])
				else:
					value = resolveFilename(SCOPE_CURRENT_SKIN, value, path_prefix=skin_path_prefix)
			# Bit of a hack this, really. When a window has a flag (e.g. wfNoBorder)
			# it needs to be set at least before the size is set, in order for the
			# window dimensions to be calculated correctly in all situations.
			# If wfNoBorder is applied after the size has been set, the window will fail to clear the title area.
			# Similar situation for a scrollbar in a listbox; when the scrollbar setting is applied after
			# the size, a scrollbar will not be shown until the selection moves for the first time
			if attrib == 'size':
				size = value.encode("utf-8")
			elif attrib == 'position':
				pos = value.encode("utf-8")
			elif attrib == 'font':
				font = value.encode("utf-8")
				skinAttributes.append((attrib, font))
			else:
				skinAttributes.append((attrib, value.encode("utf-8")))
	if pos is not None:
		pos, size = context.parse(pos, size, font)
		skinAttributes.append(('position', pos))
	if size is not None:
		skinAttributes.append(('size', size))

def morphRcImagePath(value):
	if rc_model.rcIsDefault() is False:
		if value == '/usr/share/enigma2/skin_default/rc.png' or value == '/usr/share/enigma2/skin_default/rcold.png':
			value = rc_model.getRcImg()
	return value

def loadPixmap(path, desktop):
	option = path.find("#")
	if option != -1:
		path = path[:option]
	ptr = LoadPixmap(morphRcImagePath(path), desktop)
	if ptr is None:
		raise SkinError("pixmap file %s not found!" % path)
	return ptr

class AttributeParser:
	def __init__(self, guiObject, desktop, scale=((1,1),(1,1))):
		self.guiObject = guiObject
		self.desktop = desktop
		self.scaleTuple = scale
	def applyOne(self, attrib, value):
		try:
			getattr(self, attrib)(value)
		except AttributeError:
			print "[Skin] Attribute not implemented:", attrib, "value:", value
		except SkinError, ex:
			print "[Skin] Error:", ex
	def applyAll(self, attrs):
		for attrib, value in attrs:
			self.applyOne(attrib, value)
	def conditional(self, value):
		pass
	def objectTypes(self, value):
		pass
	def position(self, value):
		if isinstance(value, tuple):
			self.guiObject.move(ePoint(*value))
		else:
			self.guiObject.move(parsePosition(value, self.scaleTuple, self.guiObject, self.desktop, self.guiObject.csize()))
	def size(self, value):
		if isinstance(value, tuple):
			self.guiObject.resize(eSize(*value))
		else:
			self.guiObject.resize(parseSize(value, self.scaleTuple, self.guiObject, self.desktop))
	def title(self, value):
		self.guiObject.setTitle(_(value))
	def text(self, value):
		self.guiObject.setText(_(value))
	def font(self, value):
		self.guiObject.setFont(parseFont(value, self.scaleTuple))
	def secondfont(self, value):
		self.guiObject.setSecondFont(parseFont(value, self.scaleTuple))
	def zPosition(self, value):
		self.guiObject.setZPosition(int(value))
	def itemHeight(self, value):
		self.guiObject.setItemHeight(int(value))
	def pixmap(self, value):
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setPixmap(ptr)
	def backgroundPixmap(self, value):
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setBackgroundPicture(ptr)
	def selectionPixmap(self, value):
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setSelectionPicture(ptr)
	def sliderPixmap(self, value):
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setSliderPicture(ptr)
	def scrollbarbackgroundPixmap(self, value):
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setScrollbarBackgroundPicture(ptr)
	def scrollbarSliderPicture(self, value):	# for compability same as sliderPixmap
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setSliderPicture(ptr)
	def scrollbarBackgroundPicture(self, value):	# for compability same as scrollbarbackgroundPixmap
		ptr = loadPixmap(value, self.desktop)
		self.guiObject.setScrollbarBackgroundPicture(ptr)
	def alphatest(self, value):
		self.guiObject.setAlphatest(
			{ "on": 1,
			  "off": 0,
			  "blend": 2,
			}[value])
	def scale(self, value):
		self.guiObject.setScale(1)
	def orientation(self, value): # used by eSlider
		try:
			self.guiObject.setOrientation(*
				{ "orVertical": (self.guiObject.orVertical, False),
					"orTopToBottom": (self.guiObject.orVertical, False),
					"orBottomToTop": (self.guiObject.orVertical, True),
					"orHorizontal": (self.guiObject.orHorizontal, False),
					"orLeftToRight": (self.guiObject.orHorizontal, False),
					"orRightToLeft": (self.guiObject.orHorizontal, True),
				}[value])
		except KeyError:
			print "oprientation must be either orVertical or orHorizontal!"
	def valign(self, value):
		try:
			self.guiObject.setVAlign(
				{ "top": self.guiObject.alignTop,
					"center": self.guiObject.alignCenter,
					"bottom": self.guiObject.alignBottom
				}[value])
		except KeyError:
			print "valign must be either top, center or bottom!"
	def halign(self, value):
		try:
			self.guiObject.setHAlign(
				{ "left": self.guiObject.alignLeft,
					"center": self.guiObject.alignCenter,
					"right": self.guiObject.alignRight,
					"block": self.guiObject.alignBlock
				}[value])
		except KeyError:
			print "halign must be either left, center, right or block!"
	def textOffset(self, value):
		x, y = value.split(',')
		self.guiObject.setTextOffset(ePoint(int(x) * self.scaleTuple[0][0] / self.scaleTuple[0][1], int(y) * self.scaleTuple[1][0] / self.scaleTuple[1][1]))
	def flags(self, value):
		flags = value.split(',')
		for f in flags:
			try:
				fv = eWindow.__dict__[f]
				self.guiObject.setFlag(fv)
			except KeyError:
				print "illegal flag %s!" % f
	def backgroundColor(self, value):
		self.guiObject.setBackgroundColor(parseColor(value))
	def backgroundColorSelected(self, value):
		self.guiObject.setBackgroundColorSelected(parseColor(value))
	def foregroundColor(self, value):
		self.guiObject.setForegroundColor(parseColor(value))
	def foregroundColorSelected(self, value):
		self.guiObject.setForegroundColorSelected(parseColor(value))
	def shadowColor(self, value):
		self.guiObject.setShadowColor(parseColor(value))
	def selectionDisabled(self, value):
		self.guiObject.setSelectionEnable(0)
	def transparent(self, value):
		self.guiObject.setTransparent(int(value))
	def borderColor(self, value):
		self.guiObject.setBorderColor(parseColor(value))
	def borderWidth(self, value):
		self.guiObject.setBorderWidth(int(value))
	def scrollbarSliderBorderWidth(self, value):
		self.guiObject.setScrollbarSliderBorderWidth(int(value))
	def scrollbarWidth(self, value):
		self.guiObject.setScrollbarWidth(int(value))
	def scrollbarSliderBorderColor(self, value):
		self.guiObject.setSliderBorderColor(parseColor(value))
	def scrollbarSliderForegroundColor(self, value):
		self.guiObject.setSliderForegroundColor(parseColor(value))
	def scrollbarMode(self, value):
		self.guiObject.setScrollbarMode(getattr(self.guiObject, value))
		#	{ "showOnDemand": self.guiObject.showOnDemand,
		#		"showAlways": self.guiObject.showAlways,
		#		"showNever": self.guiObject.showNever,
		#		"showLeft": self.guiObject.showLeft
		#	}[value])
	def enableWrapAround(self, value):
		self.guiObject.setWrapAround(True)
	def itemHeight(self, value):
		self.guiObject.setItemHeight(int(value))
	def pointer(self, value):
		(name, pos) = value.split(':')
		pos = parsePosition(pos, self.scaleTuple)
		ptr = loadPixmap(name, self.desktop)
		self.guiObject.setPointer(0, ptr, pos)
	def seek_pointer(self, value):
		(name, pos) = value.split(':')
		pos = parsePosition(pos, self.scaleTuple)
		ptr = loadPixmap(name, self.desktop)
		self.guiObject.setPointer(1, ptr, pos)
	def shadowOffset(self, value):
		self.guiObject.setShadowOffset(parsePosition(value, self.scaleTuple))
	def noWrap(self, value):
		self.guiObject.setNoWrap(1)

def applySingleAttribute(guiObject, desktop, attrib, value, scale = ((1,1),(1,1))):
	# Someone still using applySingleAttribute?
	AttributeParser(guiObject, desktop, scale).applyOne(attrib, value)

def applyAllAttributes(guiObject, desktop, attributes, scale):
	AttributeParser(guiObject, desktop, scale).applyAll(attributes)

def loadSingleSkinData(desktop, skin, path_prefix):
	"""loads skin data like colors, windowstyle etc."""
	assert skin.tag == "skin", "root element in skin must be 'skin'!"
	for c in skin.findall("output"):
		id = c.attrib.get('id')
		if id:
			id = int(id)
		else:
			id = 0
		if id == 0: # framebuffer
			for res in c.findall("resolution"):
				get_attr = res.attrib.get
				xres = get_attr("xres")
				if xres:
					xres = int(xres)
				else:
					xres = 720
				yres = get_attr("yres")
				if yres:
					yres = int(yres)
				else:
					yres = 576
				bpp = get_attr("bpp")
				if bpp:
					bpp = int(bpp)
				else:
					bpp = 32
				#print "Resolution:", xres,yres,bpp
				from enigma import gMainDC
				gMainDC.getInstance().setResolution(xres, yres)
				desktop.resize(eSize(xres, yres))
				if bpp != 32:
					# load palette (not yet implemented)
					pass
				if yres >= 1080:
					parameters["FileListName"] = (68,4,1000,34)
					parameters["FileListIcon"] = (7,4,52,37)
					parameters["FileListMultiName"] = (90,3,1000,32)
					parameters["FileListMultiIcon"] = (45, 4, 30, 30)
					parameters["FileListMultiLock"] = (2,0,36,36)
					parameters["ChoicelistDash"] = (0,3,1000,30)
					parameters["ChoicelistName"] = (68,3,1000,30)
					parameters["ChoicelistIcon"] = (7,0,52,38)
					parameters["PluginBrowserName"] = (180,8,38)
					parameters["PluginBrowserDescr"] = (180,42,25)
					parameters["PluginBrowserIcon"] = (15,8,150,60)
					parameters["PluginBrowserDownloadName"] = (120,8,38)
					parameters["PluginBrowserDownloadDescr"] = (120,42,25)
					parameters["PluginBrowserDownloadIcon"] = (15,0,90,76)
					parameters["ServiceInfo"] = (0,0,450,50)
					parameters["ServiceInfoLeft"] = (0,0,450,45)
					parameters["ServiceInfoRight"] = (450,0,1000,45)
					parameters["SelectionListDescr"] = (45,3,1000,32)
					parameters["SelectionListLock"] = (0,2,36,36)
					parameters["ConfigListSeperator"] = 500
					parameters["VirtualKeyboard"] = (68,68)
					parameters["PartnerBoxEntryListName"] = (8,2,225,38)
					parameters["PartnerBoxEntryListIP"] = (180,2,225,38)
					parameters["PartnerBoxEntryListPort"] = (405,2,150,38)
					parameters["PartnerBoxEntryListType"] = (615,2,150,38)
					parameters["PartnerBoxTimerServicename"] = (0,0,45)
					parameters["PartnerBoxTimerName"] = (0,42,30)
					parameters["PartnerBoxE1TimerTime"] = (0,78,255,30)
					parameters["PartnerBoxE1TimerState"] = (255,78,255,30)
					parameters["PartnerBoxE2TimerTime"] = (0,78,225,30)
					parameters["PartnerBoxE2TimerState"] = (225,78,225,30)
					parameters["PartnerBoxE2TimerIcon"] = (1050,8,20,20)
					parameters["PartnerBoxE2TimerIconRepeat"] = (1050,38,20,20)
					parameters["PartnerBoxBouquetListName"] = (0,0,45)
					parameters["PartnerBoxChannelListName"] = (0,0,45)
					parameters["PartnerBoxChannelListTitle"] = (0,42,30)
					parameters["PartnerBoxChannelListTime"] = (0,78,225,30)
					parameters["HelpMenuListHlp"] = (0,0,900,42)
					parameters["HelpMenuListExtHlp0"] = (0,0,900,39)
					parameters["HelpMenuListExtHlp1"] = (0,42,900,30)
					parameters["AboutHddSplit"] = 1
					parameters["DreamexplorerName"] = (62,0,1200,38)
					parameters["DreamexplorerIcon"] = (15,4,30,30)
					parameters["PicturePlayerThumb"] = (30,285,45,300,30,25)
					parameters["PlayListName"] = (38,2,1000,34)
					parameters["PlayListIcon"] = (7,7,24,24)
					parameters["SHOUTcastListItem"] = (30,27,35,96,35,33,60,32)

	for skininclude in skin.findall("include"):
		filename = skininclude.attrib.get("filename")
		if filename:
			skinfile = resolveFilename(SCOPE_CURRENT_SKIN, filename, path_prefix=path_prefix)
			if not fileExists(skinfile):
				skinfile = resolveFilename(SCOPE_SKIN_IMAGE, filename, path_prefix=path_prefix)
			if fileExists(skinfile):
				print "[Skin] Loading include:", skinfile
				loadSkin(skinfile)

	for c in skin.findall('switchpixmap'):
		for pixmap in c.findall('pixmap'):
			get_attr = pixmap.attrib.get
			name = get_attr('name')
			if not name:
				raise SkinError('[Skin] pixmap needs name attribute')
			filename = get_attr('filename')
			if not filename:
				raise SkinError('[Skin] pixmap needs filename attribute')
			resolved_png = resolveFilename(SCOPE_CURRENT_SKIN, filename, path_prefix=path_prefix)
			if fileExists(resolved_png):
				switchPixmap[name] = LoadPixmap(resolved_png, cached=True)
			else:
				raise SkinError('[Skin] switchpixmap pixmap filename="%s" (%s) not found' % (filename, resolved_png))

 	for c in skin.findall("colors"):
		for color in c.findall("color"):
			get_attr = color.attrib.get
			name = get_attr("name")
			color = get_attr("value")
			if name and color:
				colorNames[name] = parseColor(color)
				#print "Color:", name, color
			else:
				raise SkinError("need color and name, got %s %s" % (name, color))

	for c in skin.findall("fonts"):
		for font in c.findall("font"):
			get_attr = font.attrib.get
			filename = get_attr("filename", "<NONAME>")
			name = get_attr("name", "Regular")
			scale = get_attr("scale")
			if scale:
				scale = int(scale)
			else:
				scale = 100
			is_replacement = get_attr("replacement") and True or False
			render = get_attr("render")
			if render:
				render = int(render)
			else:
				render = 0
			resolved_font = resolveFilename(SCOPE_FONTS, filename, path_prefix=path_prefix)
			if not fileExists(resolved_font): #when font is not available look at current skin path
				skin_path = resolveFilename(SCOPE_CURRENT_SKIN, filename)
				if fileExists(skin_path):
					resolved_font = skin_path
			addFont(resolved_font, name, scale, is_replacement, render)
			#print "Font: ", resolved_font, name, scale, is_replacement

		fallbackFont = resolveFilename(SCOPE_FONTS, "fallback.font", path_prefix=path_prefix)
		if fileExists(fallbackFont):
			addFont(fallbackFont, "Fallback", 100, -1, 0)

		for alias in c.findall("alias"):
			get = alias.attrib.get
			try:
				name = get("name")
				font = get("font")
				size = int(get("size"))
				height = int(get("height", size)) # to be calculated some day
				width = int(get("width", size))
				global fonts
				fonts[name] = (font, size, height, width)
			except Exception, ex:
				print "[Skin] Bad font alias", ex

	for c in skin.findall("parameters"):
		for parameter in c.findall("parameter"):
			get = parameter.attrib.get
			try:
				name = get("name")
				value = get("value")
				parameters[name] = "," in value and map(parseParameter, value.split(",")) or parseParameter(value)
			except Exception, ex:
				print "[Skin] Bad parameter", ex

	for c in skin.findall("subtitles"):
		from enigma import eSubtitleWidget
		scale = ((1,1),(1,1))
		for substyle in c.findall("sub"):
			get_attr = substyle.attrib.get
			font = parseFont(get_attr("font"), scale)
			col = get_attr("foregroundColor")
			if col:
				foregroundColor = parseColor(col)
				haveColor = 1
			else:
				foregroundColor = gRGB(0xFFFFFF)
				haveColor = 0
			col = get_attr("borderColor")
			if col:
				borderColor = parseColor(col)
			else:
				borderColor = gRGB(0)
			borderwidth = get_attr("borderWidth")
			if borderwidth is None:
				# default: use a subtitle border
				borderWidth = 3
			else:
				borderWidth = int(borderwidth)
			face = eSubtitleWidget.__dict__[get_attr("name")]
			eSubtitleWidget.setFontStyle(face, font, haveColor, foregroundColor, borderColor, borderWidth)

	for windowstyle in skin.findall("windowstyle"):
		style = eWindowStyleSkinned()
		style_id = windowstyle.attrib.get("id")
		if style_id:
			style_id = int(style_id)
		else:
			style_id = 0
		# defaults
		font = gFont("Regular", 20)
		offset = eSize(20, 5)
		for title in windowstyle.findall("title"):
			get_attr = title.attrib.get
			offset = parseSize(get_attr("offset"), ((1,1),(1,1)))
			font = parseFont(get_attr("font"), ((1,1),(1,1)))

		style.setTitleFont(font);
		style.setTitleOffset(offset)
		#print "  ", font, offset
		for borderset in windowstyle.findall("borderset"):
			bsName = str(borderset.attrib.get("name"))
			for pixmap in borderset.findall("pixmap"):
				get_attr = pixmap.attrib.get
				bpName = get_attr("pos")
				filename = get_attr("filename")
				if filename and bpName:
					png = loadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, filename, path_prefix=path_prefix), desktop)
					style.setPixmap(eWindowStyleSkinned.__dict__[bsName], eWindowStyleSkinned.__dict__[bpName], png)
				#print "  borderset:", bpName, filename
		for color in windowstyle.findall("color"):
			get_attr = color.attrib.get
			colorType = get_attr("name")
			color = parseColor(get_attr("color"))
			try:
				style.setColor(eWindowStyleSkinned.__dict__["col" + colorType], color)
			except:
				raise SkinError("Unknown color %s" % colorType)
				#pass
			#print "  color:", type, color
		x = eWindowStyleManager.getInstance()
		x.setStyle(style_id, style)
	for margin in skin.findall("margin"):
		style_id = margin.attrib.get("id")
		if style_id:
			style_id = int(style_id)
		else:
			style_id = 0
		r = eRect(0,0,0,0)
		v = margin.attrib.get("left")
		if v:
			r.setLeft(int(v))
		v = margin.attrib.get("top")
		if v:
			r.setTop(int(v))
		v = margin.attrib.get("right")
		if v:
			r.setRight(int(v))
		v = margin.attrib.get("bottom")
		if v:
			r.setBottom(int(v))
		# the "desktop" parameter is hardcoded to the UI screen, so we must ask
		# for the one that this actually applies to.
		getDesktop(style_id).setMargins(r)

dom_screens = {}

def loadSkin(name, scope = SCOPE_SKIN):
	# Now a utility for plugins to add skin data to the screens
	global dom_screens, display_skin_id
	filename = resolveFilename(scope, name)
	if fileExists(filename):
		path = os.path.dirname(filename) + "/"
		for elem in xml.etree.cElementTree.parse(filename).getroot():
			if elem.tag == 'screen':
				name = elem.attrib.get('name', None)
				if name:
					sid = elem.attrib.get('id', None)
					if sid and (sid != display_skin_id):
						# not for this display
						elem.clear()
						continue
					if name in dom_screens:
						print "loadSkin: Screen already defined elsewhere:", name
						elem.clear()
					else:
						dom_screens[name] = (elem, path)
				else:
					elem.clear()
			else:
				elem.clear()

def loadSkinData(desktop):
	# Kinda hackish, but this is called once by mytest.py
	global dom_skins
	skins = dom_skins[:]
	skins.reverse()
	for (path, dom_skin) in skins:
		loadSingleSkinData(desktop, dom_skin, path)
		for elem in dom_skin:
			if elem.tag == 'screen':
				name = elem.attrib.get('name', None)
				if name:
					sid = elem.attrib.get('id', None)
					if sid and (sid != display_skin_id):
						# not for this display
						elem.clear()
						continue
					if name in dom_screens:
						# Kill old versions, save memory
						dom_screens[name][0].clear()
					dom_screens[name] = (elem, path)
				else:
					# without name, it's useless!
					elem.clear()
			else:
				# non-screen element, no need for it any longer
				elem.clear()
	# no longer needed, we know where the screens are now.
	del dom_skins

class additionalWidget:
	pass

# Class that makes a tuple look like something else. Some plugins just assume
# that size is a string and try to parse it. This class makes that work.
class SizeTuple(tuple):
	def split(self, *args):
		return (str(self[0]), str(self[1]))
	def strip(self, *args):
		return '%s,%s' % self
	def __str__(self):
		return '%s,%s' % self

class SkinContext:
	def __init__(self, parent=None, pos=None, size=None, font=None):
		if parent is not None:
			if pos is not None:
				pos, size = parent.parse(pos, size, font)
				self.x, self.y = pos
				self.w, self.h = size
			else:
				self.x = None
				self.y = None
				self.w = None
				self.h = None
	def __str__(self):
		return "Context (%s,%s)+(%s,%s) " % (self.x, self.y, self.w, self.h)
	def parse(self, pos, size, font):
		if pos == "fill":
			pos = (self.x, self.y)
			size = (self.w, self.h)
			self.w = 0
			self.h = 0
		else:
			w,h = size.split(',')
			w = parseCoordinate(w, self.w, 0, font)
			h = parseCoordinate(h, self.h, 0, font)
			if pos == "bottom":
				pos = (self.x, self.y + self.h - h)
				size = (self.w, h)
				self.h -= h
			elif pos == "top":
				pos = (self.x, self.y)
				size = (self.w, h)
				self.h -= h
				self.y += h
			elif pos == "left":
				pos = (self.x, self.y)
				size = (w, self.h)
				self.x += w
				self.w -= w
			elif pos == "right":
				pos = (self.x + self.w - w, self.y)
				size = (w, self.h)
				self.w -= w
			else:
				size = (w, h)
				pos = pos.split(',')
				pos = (self.x + parseCoordinate(pos[0], self.w, size[0], font), self.y + parseCoordinate(pos[1], self.h, size[1], font))
		return (SizeTuple(pos), SizeTuple(size))

class SkinContextStack(SkinContext):
	# A context that stacks things instead of aligning them
	def parse(self, pos, size, font):
		if pos == "fill":
			pos = (self.x, self.y)
			size = (self.w, self.h)
		else:
			w,h = size.split(',')
			w = parseCoordinate(w, self.w, 0, font)
			h = parseCoordinate(h, self.h, 0, font)
			if pos == "bottom":
				pos = (self.x, self.y + self.h - h)
				size = (self.w, h)
			elif pos == "top":
				pos = (self.x, self.y)
				size = (self.w, h)
			elif pos == "left":
				pos = (self.x, self.y)
				size = (w, self.h)
			elif pos == "right":
				pos = (self.x + self.w - w, self.y)
				size = (w, self.h)
			else:
				size = (w, h)
				pos = pos.split(',')
				pos = (self.x + parseCoordinate(pos[0], self.w, size[0], font), self.y + parseCoordinate(pos[1], self.h, size[1], font))
		return (SizeTuple(pos), SizeTuple(size))

def readSkin(screen, skin, names, desktop):
	if not isinstance(names, list):
		names = [names]

	# try all skins, first existing one have priority
	global dom_screens
	for n in names:
		myscreen, path = dom_screens.get(n, (None,None))
		if myscreen is not None:
			# use this name for debug output
			name = n
			break
	else:
		name = "<embedded-in-'%s'>" % screen.__class__.__name__

	# otherwise try embedded skin
	if myscreen is None:
		myscreen = getattr(screen, "parsedSkin", None)

	# try uncompiled embedded skin
	if myscreen is None and getattr(screen, "skin", None):
		skin = screen.skin
		print "[SKIN] Parsing embedded skin", name
		if isinstance(skin, tuple):
			for s in skin:
				candidate = xml.etree.cElementTree.fromstring(s)
				if candidate.tag == 'screen':
					sid = candidate.attrib.get('id', None)
					if (not sid) or (int(sid) == display_skin_id):
						myscreen = candidate
						break
			else:
				print "[Skin] No suitable screen!"
		else:
			myscreen = xml.etree.cElementTree.fromstring(skin)
		if myscreen:
			screen.parsedSkin = myscreen
	if myscreen is None:
		print "[Skin] No skin to read..."
		myscreen = screen.parsedSkin = xml.etree.cElementTree.fromstring("<screen></screen>")

	screen.skinAttributes = [ ]
	skin_path_prefix = getattr(screen, "skin_path", path)

	context = SkinContextStack()
	s = desktop.bounds()
	context.x = s.left()
	context.y = s.top()
	context.w = s.width()
	context.h = s.height()
	del s
	collectAttributes(screen.skinAttributes, myscreen, context, skin_path_prefix, ignore=("name",))
	context = SkinContext(context, myscreen.attrib.get('position'), myscreen.attrib.get('size'))

	screen.additionalWidgets = [ ]
	screen.renderer = [ ]
	visited_components = set()

	# now walk all widgets and stuff
	def process_none(widget, context):
		pass

	def process_widget(widget, context):
		get_attr = widget.attrib.get
		# ok, we either have 1:1-mapped widgets ('old style'), or 1:n-mapped
		# widgets (source->renderer).
		wname = get_attr('name')
		wsource = get_attr('source')
		if wname is None and wsource is None:
			print "widget has no name and no source!"
			return
		if wname:
			#print "Widget name=", wname
			visited_components.add(wname)
			# get corresponding 'gui' object
			try:
				attributes = screen[wname].skinAttributes = [ ]
			except:
				raise SkinError("component with name '" + wname + "' was not found in skin of screen '" + name + "'!")
			# assert screen[wname] is not Source
			collectAttributes(attributes, widget, context, skin_path_prefix, ignore=('name',))
		elif wsource:
			# get corresponding source
			#print "Widget source=", wsource
			while True: # until we found a non-obsolete source
				# parse our current "wsource", which might specifiy a "related screen" before the dot,
				# for example to reference a parent, global or session-global screen.
				scr = screen
				# resolve all path components
				path = wsource.split('.')
				while len(path) > 1:
					scr = screen.getRelatedScreen(path[0])
					if scr is None:
						#print wsource
						#print name
						raise SkinError("specified related screen '" + wsource + "' was not found in screen '" + name + "'!")
					path = path[1:]
				# resolve the source.
				source = scr.get(path[0])
				if isinstance(source, ObsoleteSource):
					# however, if we found an "obsolete source", issue warning, and resolve the real source.
					print "WARNING: SKIN '%s' USES OBSOLETE SOURCE '%s', USE '%s' INSTEAD!" % (name, wsource, source.new_source)
					print "OBSOLETE SOURCE WILL BE REMOVED %s, PLEASE UPDATE!" % (source.removal_date)
					if source.description:
						print source.description
					wsource = source.new_source
				else:
					# otherwise, use that source.
					break

			if source is None:
				raise SkinError("source '" + wsource + "' was not found in screen '" + name + "'!")

			wrender = get_attr('render')
			if not wrender:
				raise SkinError("you must define a renderer with render= for source '%s'" % wsource)
			for converter in widget.findall("convert"):
				ctype = converter.get('type')
				assert ctype, "'convert'-tag needs a 'type'-attribute"
				#print "Converter:", ctype
				try:
					parms = converter.text.strip()
				except:
					parms = ""
				#print "Params:", parms
				converter_class = my_import('.'.join(("Components", "Converter", ctype))).__dict__.get(ctype)
				c = None
				for i in source.downstream_elements:
					if isinstance(i, converter_class) and i.converter_arguments == parms:
						c = i
				if c is None:
					c = converter_class(parms)
					c.connect(source)
				source = c

			renderer_class = my_import('.'.join(("Components", "Renderer", wrender))).__dict__.get(wrender)
			renderer = renderer_class() # instantiate renderer
			renderer.connect(source) # connect to source
			attributes = renderer.skinAttributes = [ ]
			collectAttributes(attributes, widget, context, skin_path_prefix, ignore=('render', 'source'))
			screen.renderer.append(renderer)

	def process_applet(widget, context):
		try:
			codeText = widget.text.strip()
			widgetType = widget.attrib.get('type')
			code = compile(codeText, "skin applet", "exec")
		except Exception, ex:
			raise SkinError("applet failed to compile: " + str(ex))
		if widgetType == "onLayoutFinish":
			screen.onLayoutFinish.append(code)
		else:
			raise SkinError("applet type '%s' unknown!" % widgetType)

	def process_elabel(widget, context):
		w = additionalWidget()
		w.widget = eLabel
		w.skinAttributes = [ ]
		collectAttributes(w.skinAttributes, widget, context, skin_path_prefix, ignore=('name',))
		screen.additionalWidgets.append(w)

	def process_epixmap(widget, context):
		w = additionalWidget()
		w.widget = ePixmap
		w.skinAttributes = [ ]
		collectAttributes(w.skinAttributes, widget, context, skin_path_prefix, ignore=('name',))
		screen.additionalWidgets.append(w)

	def process_screen(widget, context):
		for w in widget.getchildren():
			conditional = w.attrib.get('conditional')
			if conditional and not [i for i in conditional.split(",") if i in screen.keys()]:
				continue
			objecttypes = w.attrib.get('objectTypes', '').split(",")
			if len(objecttypes) > 1 and (objecttypes[0] not in screen.keys() or not [i for i in objecttypes[1:] if i == screen[objecttypes[0]].__class__.__name__]):
					continue
			p = processors.get(w.tag, process_none)
			try:
				p(w, context)
			except SkinError, e:
				print "[Skin] Error in screen '%s' widget '%s':" % (name, w.tag), e

	def process_panel(widget, context):
		n = widget.attrib.get('name')
		if n:
			try:
				s = dom_screens[n]
			except KeyError:
				print "[Skin] Unable to find screen '%s' referred in screen '%s'" % (n, name)
			else:
				process_screen(s[0], context)
		layout = widget.attrib.get('layout')
		if layout == 'stack':
			cc = SkinContextStack
		else:
			cc = SkinContext
		try:
			c = cc(context, widget.attrib.get('position'), widget.attrib.get('size'), widget.attrib.get('font'))
		except Exception, ex:
			raise SkinError("Failed to create skincontext (%s,%s,%s) in %s: %s" % (widget.attrib.get('position'), widget.attrib.get('size'), widget.attrib.get('font'), context, ex) )
		process_screen(widget, c)

	processors = {
		None: process_none,
		"widget": process_widget,
		"applet": process_applet,
		"eLabel": process_elabel,
		"ePixmap": process_epixmap,
		"panel": process_panel
	}

	try:
		print "[Skin] Processing screen: %s" % name
		context.x = 0 # reset offsets, all components are relative to screen
		context.y = 0 # coordinates.
		process_screen(myscreen, context)
	except Exception, e:
		print "[Skin] Error in %s:" % name, e

	from Components.GUIComponent import GUIComponent
	nonvisited_components = [x for x in set(screen.keys()) - visited_components if isinstance(x, GUIComponent)]
	assert not nonvisited_components, "the following components in %s don't have a skin entry: %s" % (name, ', '.join(nonvisited_components))
	# This may look pointless, but it unbinds 'screen' from the nested scope. A better
	# solution is to avoid the nested scope above and use the context object to pass
	# things around.
	screen = None
	visited_components = None
