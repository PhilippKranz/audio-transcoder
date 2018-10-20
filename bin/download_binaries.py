#!/usr/bin/env python3

"""
Download and extract necessary programs
"""

import os
import urllib.parse
import urllib.request
import zipfile

TMP_FILE = 'tmp.zip'

# Components of the URL and members of the archive
FLAC_URL_TEMPLATE = 'https://ftp.osuosl.org/pub/xiph/releases/flac/flac-{version}-win.zip'
FLAC_VERSION = '1.3.2'
FLAC_PLATFORM = 'win64'
FLAC_MEMBERS_TEMPLATE = ['flac-{version}-win/{platform}/flac.exe', 'flac-{version}-win/{platform}/metaflac.exe']
NERO_URL_TEMPLATE = 'https://web.archive.org/web/20170610150750if_/http://ftp6.nero.com/tools/NeroAACCodec-{version}.zip'
NERO_VERSION = '1.5.1'
NERO_PLATFORM = 'win32'
NERO_MEMBERS_TEMPLATE = ['{platform}/neroAacEnc.exe', '{platform}/neroAacTag.exe']
OPUS_URL_TEMPLATE = 'https://archive.mozilla.org/pub/opus/{platform}/opus-tools-{version}-{platform}.zip'
OPUS_VERSION = '0.2'
OPUS_PLATFORM = 'win64'
OPUS_MEMBERS_TEMPLATE = ['opusenc.exe']

def get_files(url_template: str, version: str, platform: str, members_templates: list):
    """Construct the URL; download and extract the files"""

    url_final = url_template.format(version=version, platform=platform)
    members_final = [member.format(version=version, platform=platform) for member in members_templates]
    
    download_file(url_final)
    extract_files(members_final)
    os.remove(TMP_FILE)

def download_file(url: str):
    """Download the file"""

    try:
        print('Downloading »{}«...'.format(url.rsplit('/', 1).pop()).ljust(60), end='')
        urllib.request.urlretrieve(url, TMP_FILE)
        print('Success!')
    except:
        print('Failed!')

def extract_files(members: list):
    """Extract the files in members from the archive to the cwd without cloning the path"""
    
    try:
        with zipfile.ZipFile(TMP_FILE, 'r') as zip_file:
            for zip_info in zip_file.infolist():
                if zip_info.filename in members:
                    zip_info.filename = os.path.basename(zip_info.filename)
                    print('Extracting  »{}«...'.format(zip_info.filename).ljust(60), end='')
                    zip_file.extract(zip_info)
                    print('Success!')

    except:
        print('Failed!')      

def main():
    if os.name is not 'nt':
        print('This program only works on the Windows Operating System.')
        exit()

    get_files(FLAC_URL_TEMPLATE, FLAC_VERSION, FLAC_PLATFORM, FLAC_MEMBERS_TEMPLATE)
    get_files(NERO_URL_TEMPLATE, NERO_VERSION, NERO_PLATFORM, NERO_MEMBERS_TEMPLATE)
    get_files(OPUS_URL_TEMPLATE, OPUS_VERSION, OPUS_PLATFORM, OPUS_MEMBERS_TEMPLATE)

    print('Press any key to close this window')
    input()

if __name__ == '__main__':
    main()
