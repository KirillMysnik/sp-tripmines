from cvars.public import PublicConVar
from plugins.info import PluginInfo


info = PluginInfo()
info.name = "TripMines"
info.basename = 'tripmines'
info.author = 'Kirill "iPlayer" Mysnik'
info.version = '0.2'
info.variable = 'tm_version'
info.convar = PublicConVar(
    info.variable, info.version, "{} version".format(info.name))

info.url = "https://github.com/KirillMysnik/sp-tripmines"
