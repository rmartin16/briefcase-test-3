import subprocess
from unittest import mock

import pytest

from briefcase.exceptions import BriefcaseCommandError
from briefcase.platforms.macOS.app import macOSAppRunCommand


def test_run_app(first_app_config, tmp_path):
    "A macOS app can be started"
    command = macOSAppRunCommand(base_path=tmp_path)
    command.subprocess = mock.MagicMock()

    command.run_app(first_app_config)

    # Calls were made to start the app and to start a log stream.
    bin_path = str(command.binary_path(first_app_config))
    command.subprocess.run.assert_has_calls([
        mock.call(
            ['open', '-n', bin_path],
            check=True
        ),
        mock.call(
            [
                'log', 'stream',
                '--style', 'compact',
                '--predicate',
                'senderImagePath=="{bin_path}/Contents/MacOS/First App"'
                ' OR (processImagePath=="{bin_path}/Contents/MacOS/First App"'
                ' AND senderImagePath=="/usr/lib/libffi.dylib")'.format(bin_path=bin_path)
            ],
            check=True,
        )
    ])


def test_run_app_failed(first_app_config, tmp_path):
    "If there's a problem started the app, an exception is raised"
    command = macOSAppRunCommand(base_path=tmp_path)
    command.subprocess = mock.MagicMock()
    command.subprocess.run.side_effect = subprocess.CalledProcessError(
        cmd=['open', '-n', str(command.binary_path(first_app_config))],
        returncode=1
    )

    with pytest.raises(BriefcaseCommandError):
        command.run_app(first_app_config)

    # The run command was still invoked, though
    command.subprocess.run.assert_called_with(
        ['open', '-n', str(command.binary_path(first_app_config))],
        check=True
    )


def test_run_app_log_stream_failed(first_app_config, tmp_path):
    "If the log can't be streamed, the app still starts"
    command = macOSAppRunCommand(base_path=tmp_path)
    command.subprocess = mock.MagicMock()
    command.subprocess.run.side_effect = [
        0,
        subprocess.CalledProcessError(
            cmd=['log', 'stream'],
            returncode=1
        )
    ]

    # The run command raises an error because the log stream couldn't start
    with pytest.raises(BriefcaseCommandError):
        command.run_app(first_app_config)

    # Calls were made to start the app and to start a log stream.
    bin_path = str(command.binary_path(first_app_config))
    command.subprocess.run.assert_has_calls([
        mock.call(
            ['open', '-n', bin_path],
            check=True
        ),
        mock.call(
            [
                'log', 'stream',
                '--style', 'compact',
                '--predicate',
                'senderImagePath=="{bin_path}/Contents/MacOS/First App"'
                ' OR (processImagePath=="{bin_path}/Contents/MacOS/First App"'
                ' AND senderImagePath=="/usr/lib/libffi.dylib")'.format(bin_path=bin_path)
            ],
            check=True,
        )
    ])
