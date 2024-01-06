# installer for digiwx driver
# Copyright 2024 Matthew Wall
# Distributed under the terms of the GNU Public License (GPLv3)

from weecfg.extension import ExtensionInstaller

def loader():
    return DigiWXInstaller()

class DigiWXInstaller(ExtensionInstaller):
    def __init__(self):
        super(DigiWXInstaller, self).__init__(
            version="0.1",
            name='digiwx',
            description='Collect data from DigiWX hardware',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            files=[('bin/user', ['bin/user/digiwx.py'])]
            )
