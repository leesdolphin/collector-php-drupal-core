import json
import os
import pathlib
import re
import sys

import defusedxml.cElementTree as ElementTree
import requests
import semver


# Usually `/repo`
WORKING_DIR = pathlib.Path('./').resolve()

# Modern Drupal(Drupal 8.x) uses `const VERSION`.
MODERN_VERSION_REGEX = re.compile(r"const VERSION = '(.*)';")
MODERN_VERSION_FILES = {
    'core/includes/bootstrap.inc',
    'core/lib/Drupal.php',
}

# Older Drupal(Drupal 7.x and lower) uses `define('VERSION'`.
# Version 4.8 and below use a different mechanism; we don't handle them.
LEGACY_VERSION_REGEX = re.compile(r"define\('VERSION', '(.*)'\);")
LEGACY_VERSION_FILES = {
    'includes/bootstrap.inc',
    'modules/drupal/drupal.module',
    'modules/drupal.module',
    'modules/system.module',
    'modules/system/system.module',
}

RELEASE_VERSIONS_URL_BASE = 'https://updates.drupal.org/release-history/drupal'


def find_version(root, files, regex):
    for file in files:
        fq_file = root / file
        if not fq_file.exists():
            continue
        with fq_file.open('r') as f:
            match = regex.search(f.read())
            if match:
                # Found a drupal version
                return match.group(1)
    return None


def main():
    path = sys.argv[1] if len(sys.argv) >= 2 else ''
    root = (WORKING_DIR / path).resolve()
    #
    # version = find_version(
    #     MODERN_VERSION_FILES,
    #     MODERN_VERSION_REGEX,
    # )
    # if version is None:
    #     version = find_version(
    #         LEGACY_VERSION_FILES,
    #         LEGACY_VERSION_REGEX,
    #     )
    # if version is None:
    #     raise ValueError(
    #         f"Cannot find a supported Drupal installation in {root}"
    #     )
    version = '8.1.1'
    major, _, _ = version.partition('.')
    versions_url = RELEASE_VERSIONS_URL_BASE + f'/{major}.x'
    version_feed = requests.get(versions_url)
    version_feed.raise_for_status()
    xml = ElementTree.fromstring(version_feed.text)
    releases = xml.find('releases')
    versions_available = []
    for release in releases:
        rel_ver = release.find('version')
        rel_tag = release.find('tag')
        rel_dl_url = release.find('download_link')
        rel_dl_sum = release.find('mdhash')
        is_dev = release.find('version_extra') is not None
        if None in [rel_ver, rel_tag, rel_dl_url, rel_dl_sum]:
            continue
        data = {
            'version': rel_ver.text,
            'tar': rel_dl_url.text,
            'md5': rel_dl_sum.text,
            'dev': is_dev,
        }
        if rel_tag.text != rel_ver.text:
            data['tag'] = rel_tag.text
        versions_available.append(data)
    versions_available.sort(key=semver.parse_version_info)

    schema_output = json.dumps({
        'dependencies': [
            {
                'name': 'Drupal',
                'installed': {
                    'version': version,
                    'series': f'{major}.x',
                },
                'available': versions_available,
                'path': str(root.relative_to(WORKING_DIR)),
                'source': 'drupal-core',
            }
        ]
    })
    print(f'BEGIN_DEPENDENCIES_SCHEMA_OUTPUT>{schema_output}<END_DEPENDENCIES_SCHEMA_OUTPUT')


main()
