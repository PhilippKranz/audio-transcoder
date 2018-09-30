# Audio Transcoder
Transcode files from FLAC/WAVE to Opus/AAC/FLAC/WAVE while preserving the folder structure.

## Getting Started
### Prerequisites
#### Console
For optimal operation you need a console with good support for Unicode.

> Note: On Microsoft Windows is is recommended that you use `powershell.exe` instead of `cmd.exe`.

#### Python
This program is written for *Python 3.7.0* and above.

> Note: Your can check the version of Python with `python --version`. 
> ```shell
> $ python --version
> Python 3.7.0
> ``` 

#### Additional Programs
The following programs mast be present in order to use the `audio-transcoder`.

Program name | Recommended version   | Link | Available for
------------|-----------------------|------|--------------
flac        | 1.3.2                 | [xiph.org](https://xiph.org/flac/download.html) | Windows, GNU/Linux, macOS
metaflac    | 1.3.2                 | [xiph.org](https://xiph.org/flac/download.html) | Windows, GNU/Linux, macOS
opusenc     | 0.2                   | [opus-codec.org](https://opus-codec.org/downloads/) | Windows, GNU/Linux, macOS
neroAacEnc  | 1.5.4.0               | [nero.com](https://web.archive.org/web/20170610150750/http://ftp6.nero.com/tools/NeroAACCodec-1.5.1.zip) | Windows
neroAacTag  | 1.5.1.0               | [nero.com](https://web.archive.org/web/20170610150750/http://ftp6.nero.com/tools/NeroAACCodec-1.5.1.zip) | Windows

> Note: Please read the section on [installing](###Installing) to learn how to easily get these programs.

### Installing
#### On GNU/Linux and MacOS
1. Download [transcode.py](transcode.py)

2. Make the file executable and move it to `/usr/local/bin`
    ```shell
    $ chmod u+x ./transcode.py
    $ mv  ./transcode.py /usr/local/bin
    ```
    > Note: If you get permission errors you might have to use `sudo`.

3. Install `flac` and `opus-tools` with a packet manager
    ```shell
    $ apt install flac opus-tools    # Debian, Ubuntu, etc. with APT
    $ yum install flac opus-tools    # Fedora, RHEL, CentOS, etc. with yum
    $ zypper install flac opus-tools # openSUSE, SLES, etc. with ZYpp
    $ brew install flac opus-tools   # MacOS with Homebrew (https://brew.sh/)
    ```
    > Note: If you get permission errors you might have to use `sudo`.
4. Done

#### On Microsoft Windows
1. Download [transcode.py](transcode.py)

2. Download [download_binaries.py](bin/download_binaries.py) and place it in `./bin`

3. Navigate to `./bin` and execute the file [download_binaries.py](bin/download_binaries.py)

4. Done

## Using the Program
Invoke [transcode.py](transcode.py) from the command line and use the following arguments.

### Arguments
```
positional arguments:
  inpath                file or folder to transcode

optional arguments:
  -h, --help            show this help message and exit
  -o OUTFOLDER, --outfolder OUTFOLDER
                        target folder for the transcoded files
  -q {0-100}, --encoding_quality {0-100}
                        quality setting for the encoder
  -r, --recursive       convert files from subfolders
  -f, --force_overwrite
                        force overwrite of existing files
  -i, --copy_image      copy the embeded (cover) image file
  -s {flac,wave}, --source_format {flac,wave}
                        filename extension of the source file
  -t {opus,aac,flac,wave}, --target_format {opus,aac,flac,wave}
                        filename extension of the target file
  --max_threads {1-64}  maximum number of threads
  --silent              suppress output
  --verbose             output detailed information
  --version             show program's version number and exit
```

### Example
```shell
$ ./transcode.py C:\Users\Phil\Music\Lossless -o C:\Users\Phil\Music\Lossy -s flac -t opus -r
```
This transcodes all **FLAC** files from **C:\Users\Phil\Music\Lossless** (including files from subfolders) to **opus** files, placing them in **C:\Users\Phil\Music\Lossy** while replicating the original folder structure.

## Versioning
We use [Semantic Versioning 2.0.0](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/PhilippKranz/audio-transcoder/tags).

## Authors
* **Philipp Kranz** - *Programming and testing*
* **Dominik Kranz** - *Testing*

## License
This project is licensed under the GNU General Public License, Version 3. See the [LICENSE](LICENSE) file for details.
