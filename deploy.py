import os

DEST_DIR = r"Z:\SteamApps\steamapps\common\Counter-Strike Source\cstrike"
def copy_dir(dirname):
    os.system('xcopy /E /Y "%s" "%s"' % (os.path.join(os.getcwd(), dirname), os.path.join(DEST_DIR, dirname)))

for dirname in ('addons', 'cfg', 'resource', 'sound', 'materials'):
    copy_dir(dirname)
