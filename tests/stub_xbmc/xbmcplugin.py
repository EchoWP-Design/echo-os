from xbmcgui import _log
def setContent(h, c): _log("setContent", content=c)
def addDirectoryItem(h, url, item, isFolder=False): _log("addDirectoryItem", url=url, label=item.label, art=item.art, folder=isFolder)
def endOfDirectory(h): _log("endOfDirectory")
