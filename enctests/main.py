import os
import sys
import time
import pyseq
import shlex
import argparse
import subprocess
import configparser

from pathlib import Path

import opentimelineio as otio

# Test config files
from enctests.utils import sizeof_fmt

ENCODE_TEST_SUFFIX = '.enctest'
SOURCE_SUFFIX = '.source'

# OpenImageIO
OIIOTOOL_BIN = os.getenv(
    "OIIOTOOL_BIN",
    "oiiotool"
)

IDIFF_BIN = os.getenv(
    "IDIFF_BIN",
    "idiff"
)

# We assume macos and linux both have the same binary name
FFMPEG_BIN = os.getenv(
    'FFMPEG_BIN',
    'win' in sys.platform and 'ffmpeg.exe' or 'ffmpeg'
)

# Which vmaf model to use
VMAF_MODEL = os.getenv(
    'VMAF_MODEL',
    "vmaf_v0.6.1.json"
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--source-folder',
        action='store',
        default='./sources',
        help='Where to look for source media files'
    )

    parser.add_argument(
        '--test-config-dir',
        action='store',
        default='./test_configs',
        help='Where to look for *.enctest files'
    )

    parser.add_argument(
        '--prep-tests',
        action='store_true',
        default=False,
        help='Create *.enctest files from media in --source-folder'
    )

    parser.add_argument(
        '--encoded-folder',
        action='store',
        default='./encoded',
        help='Where to store the encoded files'
    )

    parser.add_argument(
        '--encode-all',
        action='store_true',
        default=False,
        help='Encode all tests. Default to only encoding new tests'
    )

    parser.add_argument(
        '--output',
        action='store',
        default='encoding-test-results.otio',
        help='Full path to results file (.otio)'
    )

    args = parser.parse_args()

    if not args.output.endswith('.otio'):
        args.output += '.otio'

    return args


def parse_config_file(path):
    encfile = path.as_posix()
    config = configparser.ConfigParser()
    config.read(encfile)

    return config


def create_media_reference(path, source_clip):
    config = source_clip.metadata['aswf_enctests'].get('SOURCE_INFO')
    rate = float(config.get('rate'))
    duration = float(config.get('duration'))

    if path.is_dir():
        # Create ImageSequenceReference
        seq = pyseq.get_sequences(path.as_posix())[0]
        available_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(
                seq.start(), rate
            ),
            duration=otio.opentime.RationalTime(
                seq.length(), rate
            )
        )
        mr = otio.schema.ImageSequenceReference(
            target_url_base=Path(seq.directory()).as_uri(),
            name_prefix=seq.head(),
            name_suffix=seq.tail(),
            start_frame=seq.start(),
            frame_step=1,
            frame_zero_padding=len(max(seq.digits, key=len)),
            rate=rate,
            available_range=available_range
        )

    else:
        # Create ExternalReference
        available_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(
                0, rate
            ),
            duration=otio.opentime.RationalTime(
                duration, rate
            )
        )
        mr = otio.schema.ExternalReference(
            target_url=path.resolve().as_uri(),
            available_range=available_range,
        )
        mr.name = path.name

    return mr


def create_clip(args, config):
    path = Path(args.source_folder).joinpath(
        Path(config.get('path'))
    )
    clip = otio.schema.Clip(name=path.stem)
    clip.metadata.update({'aswf_enctests': {config.name: dict(config)}})

    # Source range
    clip.source_range = get_source_range(config)

    # The initial MediaReference is stored as default
    mr = create_media_reference(path, clip)
    clip.media_reference = mr

    return clip


def get_source_range(config):
    source_range = otio.opentime.TimeRange(
        start_time=otio.opentime.RationalTime(
            config.getint('in'),
            config.getfloat('rate')
        ),
        duration=otio.opentime.RationalTime.from_seconds(
            config.getint('duration') /
            config.getint('rate'),
            config.getfloat('rate')
        )
    )

    return source_range


def create_source_files(args):
    with os.scandir(args.source_folder) as it:
        for item in it:
            path = Path(item.path)
            if path.suffix == ENCODE_TEST_SUFFIX:
                # We only register new media
                continue

            if path.is_dir():
                seq = pyseq.get_sequences(path.as_posix())[0]


def get_configs(root_dir, config_type):
    configs = []
    with os.scandir(root_dir) as it:
        for item in it:
            path = Path(item.path)
            if path.suffix == config_type:
                config = parse_config_file(path)
                configs.append(config)

    return configs


def tests_only(test_configs):
    for config in test_configs:
        for section in config.sections():
            if section.lower().startswith('test'):
                yield config[section]


def get_source_path(source_clip):
    source_mr = source_clip.media_reference
    symbol = ''
    path = Path()
    if isinstance(source_mr, otio.schema.ExternalReference):
        path = Path(source_mr.target_url)

    elif isinstance(source_mr, otio.schema.ImageSequenceReference):
        symbol = f'%0{source_mr.frame_zero_padding}d'
        path = Path(source_mr.abstract_target_url(symbol=symbol))

    return path, symbol


def get_test_metadata_dict(otio_item, testname):
    ffmpeg_version = get_ffmpeg_version()
    aswf_meta = otio_item.metadata.setdefault('aswf_enctests', {})
    enc_meta = aswf_meta.setdefault(testname, {})

    return enc_meta.setdefault(ffmpeg_version, {})


def get_ffmpeg_version():
    cmd = f'{FFMPEG_BIN} -version -v quiet -hide_banner'
    _raw = subprocess.check_output(shlex.split(cmd))
    version = b'_'.join(_raw.split(b' ')[:3])

    return version


def ffmpeg_convert(args, source_clip, test_config):
    ffmpeg_cmd = "\
{ffmpeg_bin}\
{input_args} \
-i {source} \
-vframes {duration}\
{compression_args} \
-y {outfile}\
"

    source_path, symbol = get_source_path(source_clip)

    # Append test name to source filename
    stem = source_path.stem.replace(symbol, '')
    out_file = Path(args.encoded_folder).absolute().joinpath(
        f"{stem}-{test_config.name}{test_config.get('suffix')}"
    )
    input_args = ' '.join(
        source_clip.metadata['aswf_enctests']['SOURCE_INFO'].get('input_args').split('\n')
    )
    encoding_args = ' '.join(
        test_config.get('encoding_args').split('\n')
    )

    duration = source_clip.source_range.duration.to_frames()
    cmd = ffmpeg_cmd.format(
                ffmpeg_bin=FFMPEG_BIN,
                input_args=input_args,
                source=source_path,
                duration=duration,
                compression_args=encoding_args,
                outfile=out_file
            )

    print('ffmpeg command:', cmd)
    # Time encoding process
    t1 = time.perf_counter()

    # Do encoding
    subprocess.call(shlex.split(cmd))

    # Store encoding time
    enctime = time.perf_counter() - t1

    # Create a media reference of output file
    mr = create_media_reference(out_file, source_clip)

    # Update metadata
    enc_meta = get_test_metadata_dict(mr, test_config.name)
    enc_meta['encode_time'] = round(enctime, 4)
    enc_meta['encode_arguments'] = encoding_args
    enc_meta['filesize'] = sizeof_fmt(out_file)

    return mr


def prep_sources(args, collection):
    source_configs = get_configs(args.source_folder, SOURCE_SUFFIX)
    for config in source_configs:
        source_clip = create_clip(args, config['SOURCE_INFO'])
        collection.append(source_clip)


def run_tests(args, test_configs, collection):
    for source_clip in collection:
        references = source_clip.media_references()

        # # Create lossless reference for comparisons
        # lossless_ref = ffmpeg_convert(args, config, 'BASELINE_SETTINGS')
        # references.update({'baseline': lossless_ref})

        for test_config in tests_only(test_configs):
            # perform enctest
            testname = test_config.name
            print(f'Running "{testname}"')
            test_ref = ffmpeg_convert(args, source_clip, test_config)
            references.update({testname: test_ref})

        # Add media references to clip
        source_clip.set_media_references(
            references, source_clip.DEFAULT_MEDIA_KEY
        )


def main():
    args = parse_args()

    if args.prep_tests:
        create_source_files(args)

        return

    # Make sure we have a folder for test configs
    Path(args.test_config_dir).mkdir(exist_ok=True)

    # Make sure we have a destination folder
    Path(args.encoded_folder).mkdir(exist_ok=True)

    # Load test config files
    test_configs = get_configs(args.test_config_dir, ENCODE_TEST_SUFFIX)

    # Create a collection object to hold clips
    collection = otio.schema.SerializableCollection(name='aswf_enctests')

    # Prep source files
    prep_sources(args, collection)

    # Run tests
    run_tests(args, test_configs, collection)
    print(f'Results: {collection}')
    print(f'Results: {collection[0].media_references()}')

    # Store results in an *.otio file
    otio.adapters.write_to_file(collection, args.output)


if __name__== '__main__':
    main()
