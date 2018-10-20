#!/usr/bin/env python3

"""
Transcode files from FLAC/WAVE to Opus/AAC/FLAC/WAVE while preserving the folder structure
"""

# Versioning according to Semantic Versioning 2.0.0 (https://semver.org/)
__version__ = '0.4.6'

import abc
import argparse
import logging
import os
import pathlib
import queue
import subprocess as sp
import shutil
import tempfile
import threading
import time

class TranscodeJob:
    """Transcode job"""

    def __init__(self,
            inpath: str,
            outfolder: str,
            recursive_mode: bool=False,
            force_overwrite: bool=False,
            source_format: str='flac',
            target_format: str='opus',
            encoding_quality: int=50,
            copy_image: bool=False,
            max_threads: int=4):
        
        self.inpath = pathlib.Path(inpath)
        self.outfolder = pathlib.Path(outfolder)

        # Check if inpath exists
        if not self.inpath.exists():
            raise FileNotFoundError('Input path does not exist')
        self.inpath = self.inpath.expanduser().resolve() # Expand user if necessary and resolve full path

        # Check if output-folder exists and create if necessary
        if not self.outfolder.exists():
            os.makedirs(self.outfolder, exist_ok=True) # Set flag to avoid race condition
        
        # Check if outfolder is a directory
        if not self.outfolder.is_dir():
            raise Exception('Output folder is invalid')
        self.outfolder = self.outfolder.expanduser().resolve() # Expand user if necessary and resolve full path

        # Check input values
        if encoding_quality < 0 or encoding_quality > 100:
            raise ValueError('Invalid value for encoding quality')
        self.encoding_quality = encoding_quality

        if not source_format in ['flac', 'wave']:
            raise ValueError('Unsupported input format')
        self.source_format = source_format

        if not target_format in ['aac', 'opus', 'flac', 'wave']:
            raise ValueError('Unsupported output format')
        self.target_format = target_format

        if max_threads < 1 or max_threads > 64:
            raise ValueError('Invalid value for maximum threads')
        self.max_threads = max_threads
        
        self.recursive_mode = recursive_mode
        self.force_overwrite = force_overwrite
        self.copy_image = copy_image
        
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        self.files_found = 0

    def start(self):
        """Start the transcode job"""

        logging.info('Starting transcode job')

        # Change current working directory to the path of the binaries
        tmp_cwd = os.getcwd()
        logging.debug('Original CWD was %s', tmp_cwd)
        bin_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'bin')
        logging.debug('Changing CWD to %s', bin_path)
        os.chdir(bin_path)

        # Select decoder
        decoder_map = {'flac': FLACDecoder, 'wave': WAVEDecoder}
        decoder = decoder_map[self.source_format](True, self.copy_image) 
        logging.info('Selected decoder: %s', decoder.__class__.__name__)

        # Select encoder
        encoder_map = {'opus': XiphOpusEncoder, 'aac': NeroAACEncoder, 'flac': FLACEncoder, 'wave': WAVEEncoder}
        encoder = encoder_map[self.target_format](True, self.copy_image, self.encoding_quality)
        logging.info('Selected encoder: %s', encoder.__class__.__name__)

        # Create thread pool and start daemon
        logging.info('Creating thread-pool with %d threads', self.max_threads)
        for _ in range(self.max_threads):
            transcoder = Transcoder(self.input_queue, self.output_queue, decoder, encoder, self.force_overwrite)
            transcoder.daemon = True
            transcoder.start()

        # Input is a file
        if self.inpath.is_file():
            logging.debug('Inpath is a file')
            if not self.inpath.suffix == decoder.suffix:
                raise Exception('Input file has wrong suffix')
            
            self.input_queue.put((self.inpath, self.outfolder))
            self.files_found += 1
        
        # Input is a directory
        elif self.inpath.is_dir():
            logging.debug('Inpath is a directory')
            if self.recursive_mode:
                files = self.inpath.rglob('*' + decoder.suffix)
            else:
                files = self.inpath.glob('*' + decoder.suffix)
        
            for f in files:
                # clone directory structure from inpath in outfolder
                rel_path = f.relative_to(self.inpath).parent
                subfolder = self.outfolder.joinpath(rel_path)
                subfolder.mkdir(parents=True, exist_ok=True)

                self.input_queue.put((f, subfolder))
                self.files_found += 1

            if self.files_found == 0:
                raise Exception('No suitable files were found in the folder')
        
            logging.info('Found %d transcodable files', self.files_found)

        else:
            raise Exception('Input is neither a file nor a folder')

        # Wait for the threads to finish
        self.input_queue.join()

        # Change current working directory back to the initial value
        logging.debug('Changing CWD back to %s', tmp_cwd)
        os.chdir(tmp_cwd)

        print('Done')


class Transcoder(threading.Thread):
    """Transcoder"""

    def __init__(self, input_queue, output_queue, decoder, encoder, force_overwrite):
        threading.Thread.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.tmp_file_queue = queue.Queue() # Store path of temporary files to be able to delete them later

        self.decoder = decoder
        self.encoder = encoder
        self.force_overwrite = force_overwrite

    def run(self):
        while True:
            infile, outfolder = self.input_queue.get()
            outfile = self._create_outfile_name(infile, outfolder)
            self._transcode(infile, outfile)
            self._delete_tmp_files()
            self.input_queue.task_done()

    def _transcode(self, infile, outfile):
        """Transcode the infile to the outfile"""

        # Overwrite existing files?
        if outfile.exists():
            if self.force_overwrite:
                logging.debug('Overwrite enabled. Deleting the following file: %s', outfile)
                outfile.unlink()
            else:
                logging.debug('Overwrite disabled. Skipping the following file: %s', outfile)
                return

        # Create temporary files
        tmp_audio = self._create_tmp_file()
        tmp_image = self._create_tmp_file()

        # Call decoder
        try:
            logging.info('Decoding from file: %s', infile)
            tags = self.decoder.decode(infile, tmp_audio, tmp_image)
            logging.debug('Found %d metadata tags', len(tags))
        except Exception as e:
            logging.warning('Failed to decode file: %s', str(e))
            return

        # Call encoder
        try:
            logging.info('Encoding to file: %s', outfile)
            self.encoder.encode(tmp_audio, outfile, tags, tmp_image)
        except Exception as e:
            logging.warning('Failed to encode file: %s', str(e))
            return

    def _create_tmp_file(self):
        """Create a temporary file and return the path to it"""

        fd, fname = tempfile.mkstemp()
        os.close(fd)
        self.tmp_file_queue.put(fname)

        return fname

    def _delete_tmp_files(self):
        """Delete temporary files"""

        self.tmp_file_queue.put('') # Workaround
        max_attempts = 20 # How often should it be tried?

        for tmp_file in iter(self.tmp_file_queue.get, ''):
            attempts = 0

            # Try up to 'max_attempts' times to delete the file
            while os.path.exists(tmp_file) and attempts < max_attempts:
                attempts += 1
                try:
                    os.remove(tmp_file)
                except:
                    time.sleep(0.2) # Suspend execution for 200ms

    def _create_outfile_name(self, infile, outfolder):
        """Create the full filename of the target file"""

        rel_outfile = infile.with_suffix(self.encoder.suffix).name
        abs_outfile = outfolder.joinpath(rel_outfile)

        return abs_outfile

class Decoder:
    """Abstract decoder class"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def decode(self):
        raise NotImplementedError


class FLACDecoder(Decoder):
    """
    Decoder for FLAC files using the reference implementation »flac« and »metaflac«

    Handles Vorbis Comment metadata and cover images

    Reference:
        - https://xiph.org/vorbis/doc/v-comment.html
        - https://wiki.xiph.org/VorbisComment

    """

    suffix = '.flac'

    def __init__(self, extract_metadata=True, extract_image=False):
        # Check if the the necessary binaries exist
        if not shutil.which('flac'):
            raise FileNotFoundError('Cannot locate required executable »flac«')
        if not shutil.which('metaflac'):
            raise FileNotFoundError('Cannot locate required executable »metaflac«')

        self.extract_metadata = extract_metadata
        self.extract_image = extract_image

    def decode(self, infile, outfile, tmp_image=None):
        """Decode audio and extract metadata"""

        # Quick sanity check of file
        self._check_flac_marker(infile)

        # Workaround for subprocess not beeing able to handle pathlib.WindowsPath paths
        infile = str(infile)
        outfile = str(outfile)

        # Decode audio with »flac« binary
        with open(os.devnull, 'w') as fnull:
            sp.check_call(['flac', infile,
                           '-o', outfile,
                           '--force',
                           '--no-utf8-convert',
                           '--decode',
                           '--totally-silent'],
                           stdout=fnull, stderr=fnull)

        # Extract metadata and embedded images with »metaflac« binary
        if self.extract_metadata or self.extract_image:
            tags = {}
            cmd = ['metaflac', infile]

            if self.extract_metadata:
                cmd.append('--no-utf8-convert')
                cmd.append('--export-tags-to=-')

            if self.extract_image:
                cmd.append('--export-picture-to=' + tmp_image)

            out = sp.check_output(cmd).decode('utf-8')

        # No metadata found
        if not out:
            return tags

        # Make a dict from the tags-string
        for line in out.splitlines():
            key, value = line.split('=', 1)
            tags[key.upper()] = value

        return tags

    def _check_flac_marker(self, infile):
        """Check if the file begins with the 'fLaC' stream marker"""

        with open(infile, 'rb') as f:
            if f.read(4) != b'fLaC':
                raise Exception('Not a valid FLAC file')


class WAVEDecoder(Decoder):
    """Decoder for WAVE files"""

    suffix = '.wav'

    def __init__(self, extract_metadata=False, extract_image=False):
        if extract_metadata or extract_image:
            raise Exception('WAVE files have no native support for metadata or embedded images.')

    def decode(self, infile, outfile, tmp_image=None):
        """Copy WAVE file"""

        # Quick sanity check of file
        self._check_wav_marker(infile)

        shutil.copyfile(infile, outfile)
        return {}

    def _check_wav_marker(self, infile):
        """Check if the file contains 'RIFF' and 'WAVE' markers"""

        with open(infile, 'rb') as f:
            riff_marker = f.read(4)
            f.seek(8)
            wave_marker = f.read(4)

            if riff_marker != b'RIFF' or wave_marker != b'WAVE':
                raise Exception('Not a valid WAVE file')


class Encoder:
    """Abstract encoder class"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def encode(self):
        raise NotImplementedError


class FLACEncoder(Encoder):
    """Encoder for FLAC files using »flac«"""

    suffix = '.flac'

    def __init__(self, embed_metadata=True, embed_image=True, quality=50):
        # Check if the the necessary binaries exist
        if not shutil.which('flac'):
            raise FileNotFoundError('Cannot locate required executable »flac«')
        if not shutil.which('metaflac'):
            raise FileNotFoundError('Cannot locate required executable »metaflac«')

        self.embed_metadata = embed_metadata
        self.embed_image = embed_image
        self.quality = str(quality / 10)

    def encode(self, infile, outfile, tags={}, tmp_image=None):
        """Encode audio and embed metadata"""

        cmd = ['flac', '--totally-silent', '-o', outfile]

        if self.embed_metadata:
            for key, value in tags.items():
                cmd.append('-T')
                cmd.append('{0}={1}'.format(key, value))

        if self.embed_image:
           cmd.append('--picture=' + tmp_image)

        cmd.append(infile)

        with open(os.devnull, 'w') as fnull:
            sp.check_call(cmd, stdout=fnull, stderr=fnull)


class NeroAACEncoder(Encoder):
    """
    Encoder for AAC files using Nero AAC Encoder

    Reference:
        - ftp://ftp6.nero.com/tutorials/nerodigital/audio_encoder/NeroDigitalAudio_tut_eng.pdf

    """

    suffix = '.m4a'

    def __init__(self, embed_metadata=True, embed_image=True, quality=50):
        # Check if the the necessary binaries exist
        if not shutil.which('neroAacEnc'):
            raise FileNotFoundError('Cannot locate required executable »neroAacEnc«')
        if not shutil.which('neroAacTag'):
            raise FileNotFoundError('Cannot locate required executable »neroAacTag«')

        self.embed_metadata = embed_metadata
        self.embed_image = embed_image
        self.quality = str(quality / 100)

    def encode(self, infile, outfile, tags={}, tmp_image=None):
        """Encode audio and embed metadata"""

        # Workaround for subprocess not beeing able to handle pathlib.WindowsPath paths
        infile = str(infile)
        outfile = str(outfile)

        # Encode audio with »neroAacEnc« binary
        with open(os.devnull, 'w') as fnull:
            sp.check_call(['neroAacEnc',
                           '-if', infile,
                           '-of', outfile,
                           '-q', self.quality],
                           stdout=fnull, stderr=fnull)

        # Inject metadata and image with »neroAacTag« binary
        if self.embed_metadata or self.embed_image:
            cmd = ['neroAacTag', outfile]

            if self.embed_metadata:
                tags = self._map_vorbis_comment_to_neroaactag(tags)
                for key, value in tags.items():
                    cmd.append('-meta:{0}={1}'.format(key, value))

            if self.embed_image:
                cmd.append('-add-cover:front:' + tmp_image)

            with open(os.devnull, 'w') as fnull:
                sp.check_call(cmd, stdout=fnull, stderr=fnull)

    def _map_vorbis_comment_to_neroaactag(self, tags_in):
        """
        The Vorbis comment field names are mapped to the corresponding
        standard Nero Digital metadata field names where possible.

        Some field names of these two sets of metadata can't be mapped
        correctly. This information of the source file will thus not
        be available in the target file. The affected field names are:

        Vorbis:
            CONTACT, DESCRIPTION, LOCATION, PERFORMER, VERSION

        MPEG-4:
            lyrics, mood, rating, tempo, url
            (composer, disc, totaldiscs totaltracks)

        References:
            - https://www.xiph.org/vorbis/doc/v-comment.html
            - https://wiki.xiph.org/Field_names

        """

        # Standard field names from the Ogg Vorbis I format specification
        schema_crosswalk = {
            'ARTIST':       'artist',
            'TITLE':        'title',
            'ALBUM':        'album',
            'DATE':         'year',
            'TRACKNUMBER':  'track',
            'GENRE':        'genre',
            'COMMENT':      'comment',
            'ORGANIZATION': 'label',
            'LICENSE':      'credits',
            'COPYRIGHT':    'copyright',
            'ISRC':         'isrc',
        }

        # Proposed field names from the xiph.org Wiki page
        schema_crosswalk_proposed = {
            'COMPOSER':     'composer',
            'TRACKTOTAL':   'totaltracks',
            'DISCNUMBER':   'disc',
            'DISCTOTAL':    'totaldiscs'
        }

        # Comment out the following line if you only want to use the standard field names
        schema_crosswalk.update(schema_crosswalk_proposed)

        tags_out = dict()

        # Save the information of the VERSION field in the TITLE field
        if 'VERSION' in tags_in:
            tags_in['TITLE'] += ' [' + tags_in['VERSION'] + ']'

        # Convert tracknumbers from form '0n' to 'n'
        if 'TRACKNUMBER' in tags_in:
            tags_in['TRACKNUMBER'] = int(tags_in['TRACKNUMBER'])

        for vorbis_field, nero_field in schema_crosswalk.items():
            if vorbis_field in tags_in:
                tags_out[nero_field] = tags_in[vorbis_field]

        return tags_out


class XiphOpusEncoder(Encoder):
    """
    Encoder for Opus files using opus-tools

    Reference:
        - https://mf4.xiph.org/jenkins/view/opus/job/opus-tools/ws/man/opusenc.html

    """

    suffix = '.opus'

    def __init__(self, embed_metadata=True, embed_image=False, quality=50):
        # Check if the the necessary binary exists
        if not shutil.which('opusenc'):
            raise FileNotFoundError('Cannot locate required executable »opusenc«')

        self.embed_metadata = embed_metadata
        self.embed_image = embed_image
        self.quality = str(quality / 10)

    def encode(self, infile, outfile, tags={}, tmp_image=None):
        """Encode audio and embed metadata"""

        # Workaround for subprocess not beeing able to handle pathlib.WindowsPath paths
        infile = str(infile)
        outfile = str(outfile)

        cmd = ['opusenc', '--comp', self.quality]

        if self.embed_metadata:
            for key, value in tags.items():
                cmd.append('--comment')
                cmd.append('{0}={1}'.format(key, value))

        if self.embed_image:
            cmd.append('--picture ' + tmp_image)

        cmd.append(infile)
        cmd.append(outfile)

        with open(os.devnull, 'w') as fnull:
            sp.check_call(cmd, stdout=fnull, stderr=fnull)


class WAVEEncoder(Encoder):
    """Encoder for WAVE files"""

    suffix = '.wav'

    def __init__(self, embed_metadata=False, embed_image=False, quality=100):
        if embed_metadata or embed_image:
            raise Exception('WAVE files do not support embedding of metadata or images')

    def encode(self, infile, outfile, tags=None, tmp_image=None):
        """Move file from infile to outfile"""
        shutil.copyfile(infile, outfile)


def main():
    """Main function"""

    # Parse agruments
    description = 'Transcode files from FLAC/WAVE to Opus/AAC/FLAC/WAVE'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('inpath', help='file or folder to transcode')
    parser.add_argument('-o', '--outfolder',
                        dest='outfolder',
                        default='~',
                        help='target folder for the transcoded files')
    parser.add_argument('-q', '--encoding_quality',
                        dest='encoding_quality',
                        type=int,
                        default='50',
                        choices=range(0,101),
                        metavar='{0-100}',
                        help='quality setting for the encoder')
    parser.add_argument('-r', '--recursive',
                        dest='recursive_mode',
                        action='store_true',
                        help='convert files from subfolders')
    parser.add_argument('-f', '--force_overwrite',
                        dest='force_overwrite',
                        action='store_true',
                        help='force overwrite of existing files')
    parser.add_argument('-i', '--copy_image',
                        dest='copy_image',
                        action='store_true',
                        help='copy the embeded (cover) image file')
    parser.add_argument('-s', '--source_format',
                        dest='source_format',
                        default='flac',
                        choices=['flac', 'wave'],
                        help='filename extension of the source file')
    parser.add_argument('-t', '--target_format',
                        dest='target_format',
                        default='opus',
                        choices=['opus', 'aac', 'flac', 'wave'],
                        help='filename extension of the target file')
    parser.add_argument('--max_threads',
                        dest='max_threads',
                        type=int,
                        default='4',
                        choices=range(1,65),
                        metavar='{1-64}',
                        help='maximum number of threads')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--silent',
                        dest='silent',
                        action='store_true',
                        help='suppress output')
    group.add_argument('--verbose',
                        dest='verbose',
                        action='store_true',
                        help='output detailed information')
    parser.add_argument('--version',
                        action='version',
                        version='Audio Transcoder ' + str(__version__))
    args = parser.parse_args()
    
    # Determine log level
    if args.silent:
        loglevel = logging.CRITICAL
    elif args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO

    # Start logging
    logging.basicConfig(level=loglevel, format='%(levelname)s: %(message)s [%(threadName)s]')

    # Start transcode job
    job = TranscodeJob(args.inpath, args.outfolder, args.recursive_mode, args.force_overwrite, args.source_format, args.target_format, args.encoding_quality, args.copy_image, args.max_threads)
    job.start()

if __name__ == '__main__':
    main()