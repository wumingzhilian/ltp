# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import re
import json
import socket
import urllib.request
import sphinx

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Linux Test Project'
copyright = '2024, Linux Test Project'
author = 'Linux Test Project'
release = '1.0'
ltp_repo = 'https://github.com/linux-test-project/ltp'
ltp_repo_base_url = f"{ltp_repo}/tree/master"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'linuxdoc.rstKernelDoc',
    'sphinxcontrib.spelling',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.extlinks',
]

exclude_patterns = ["html*", '_static*']
extlinks = {
    'repo': (f'{ltp_repo}/%s', '%s'),
    'master': (f'{ltp_repo}/blob/master/%s', '%s'),
    'git_man': ('https://git-scm.com/docs/git-%s', 'git %s'),
    # TODO: allow 2nd parameter to show page description instead of plain URL
    'kernel_doc': ('https://docs.kernel.org/%s.html', 'https://docs.kernel.org/%s.html'),
    'kernel_tree': ('https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/%s', '%s'),
}

spelling_lang = "en_US"
spelling_warning = True
spelling_exclude_patterns = ['users/stats.rst']
spelling_word_list_filename = "spelling_wordlist"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']


def generate_syscalls_stats(_):
    """
    Since syscalls tests have been removed, we'll just generate a notice.
    """
    output = '_static/syscalls.rst'
    
    with open(output, 'w+', encoding='utf-8') as stats:
        stats.write(".. note::\n\n    Syscalls tests have been removed from this version of LTP.\n")


def _generate_tags_table(tags):
    """
    Generate the tags table from tags hash.
    """
    supported_url_ref = {
        "linux-git": "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=",
        "linux-stable-git": "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/commit/?id=",
        "glibc-git": "https://sourceware.org/git/?p=glibc.git;a=commit;h=",
        "musl-git": "https://git.musl-libc.org/cgit/musl/commit/src/linux/clone.c?id=",
        "CVE": "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-",
    }

    table = [
        '.. list-table::',
        '   :header-rows: 1',
        '',
        '   * - Tag',
        '     - Info',
    ]

    for tag in tags:
        tag_key = tag[0]
        tag_val = tag[1]

        tag_url = supported_url_ref.get(tag_key, None)
        if tag_url:
            tag_val = f'`{tag_val} <{tag_url}{tag_val}>`_'

        table.extend([
            f'   * - {tag_key}',
            f'     - {tag_val}',
        ])

    return table


def _generate_options_table(options):
    """
    Generate the options table from the options hash.
    """
    table = [
        '.. list-table::',
        '   :header-rows: 1',
        '',
        '   * - Option',
        '     - Description',
    ]

    for opt in options:
        if not isinstance(opt, list):
            table.clear()
            break

        key = opt[0]
        val = opt[2]

        if key.endswith(':'):
            key = key[:-1] if key.endswith(':') else key

        key = f'-{key}'

        table.extend([
            f'   * - {key}',
            f'     - {val}',
        ])

    return table


def _generate_table_cell(key, values):
    """
    Generate a cell which can be multiline if value is a list.
    """
    cell = []

    if len(values) > 1:
        cell.extend([
            f'   * - {key}',
            f'     - | {values[0]}',
        ])

        for item in values[1:]:
            cell.append(f'       | {item}')
    else:
        cell.extend([
            f'   * - {key}',
            f'     - {values[0]}',
        ])

    return cell


def _generate_setup_table(keys):
    """
    Generate the table with test setup configuration.
    """
    exclude = [
        # following keys are already handled
        'options',
        'runtime',
        'timeout',
        'fname',
        'doc',
        # following keys don't need to be shown
        'child_needs_reinit',
        'needs_checkpoints',
        'forks_child',
        'tags',
    ]
    my_keys = {k: v for k, v in keys.items() if k not in exclude}
    if len(my_keys) == 0:
        return []

    table = [
        '.. list-table::',
        '   :header-rows: 1',
        '',
        '   * - Key',
        '     - Value',
    ]

    values = []

    for key, value in my_keys.items():
        if key in exclude:
            continue

        values.clear()

        if key == 'ulimit':
            for item in value:
                values.append(f'{item[0]} : {item[1]}')
        elif key == 'hugepages':
            if len(value) == 1:
                values.append(f'{value[0]}')
            else:
                values.append(f'{value[0]}, {value[1]}')
        elif key == 'filesystems':
            for v in value:
                for item in v:
                    if isinstance(item, list):
                        continue

                    if item.startswith('.type'):
                        values.append(item.replace('.type=', ''))
        elif key == "save_restore":
            for item in value:
                values.append(item[0])
        else:
            if isinstance(value, list):
                values.extend(value)
            else:
                values.append(value)

        table.extend(_generate_table_cell(key, values))

    return table


def generate_test_catalog(_):
    """
    Generate the test catalog from ltp.json metadata file.
    """
    output = '_static/tests.rst'
    metadata_file = '../metadata/ltp.json'
    text = [
        '.. warning::',
        '    The following catalog has been generated using LTP metadata',
        '    which is including only tests using the new :ref:`LTP C API`.',
        ''
    ]

    metadata = None
    with open(metadata_file, 'r', encoding='utf-8') as data:
        metadata = json.load(data)

    timeout_def = metadata['defaults']['timeout']

    for test_name, conf in sorted(metadata['tests'].items()):
        text.extend([
            f'{test_name}',
            len(test_name) * '-'
        ])

        # source url location
        test_fname = conf.get('fname', None)
        if test_fname:
            text.extend([
                '',
                f"`source <{ltp_repo_base_url}/{test_fname}>`__",
                ''
            ])

        # test description
        desc = conf.get('doc', None)
        if desc:
            desc_text = []
            for line in desc:
                if line.startswith("[Description]"):
                    desc_text.append("**Description**")
                elif line.startswith("[Algorithm]"):
                    desc_text.append("**Algorithm**")
                else:
                    desc_text.append(line)

            text.extend([
                '\n'.join(desc_text),
            ])

        # timeout information
        timeout = conf.get('timeout', None)
        if timeout:
            text.extend([
                '',
                f'Test timeout is {timeout} seconds.',
            ])
        else:
            text.extend([
                '',
                f'Test timeout defaults is {timeout_def} seconds.',
            ])

        # runtime information
        runtime = conf.get('runtime', None)
        if runtime:
            text.extend([
                f'Maximum runtime is {runtime} seconds.',
                ''
            ])
        else:
            text.append('')

        # options information
        opts = conf.get('options', None)
        if opts:
            text.append('')
            text.extend(_generate_options_table(opts))
            text.append('')

        # tags information
        tags = conf.get('tags', None)
        if tags:
            text.append('')
            text.extend(_generate_tags_table(tags))
            text.append('')

        # parse struct tst_test content
        text.append('')
        text.extend(_generate_setup_table(conf))
        text.append('')

        # small separator between tests
        text.extend([
            '',
            '.. raw:: html',
            '',
            '    <hr>',
            '',
        ])

    with open(output, 'w+', encoding='utf-8') as new_tests:
        new_tests.write('\n'.join(text))


def setup(app):
    """
    Setup the current documentation, using self generated data and graphics
    customizations.
    """
    app.add_css_file('custom.css')
    app.connect('builder-inited', generate_syscalls_stats)
    app.connect('builder-inited', generate_test_catalog)
