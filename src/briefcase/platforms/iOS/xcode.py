import subprocess
import time

from briefcase.config import BaseConfig
from briefcase.console import select_option
from briefcase.commands import (
    BuildCommand,
    CreateCommand,
    PublishCommand,
    RunCommand,
    UpdateCommand
)
from briefcase.exceptions import BriefcaseCommandError
from briefcase.platforms.iOS import iOSMixin
from briefcase.integrations.xcode import get_simulators, get_device_state, DeviceState


class iOSXcodePassiveMixin(iOSMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, output_format='Xcode', **kwargs)

    def binary_path(self, app):
        return (
            self.platform_path
            / '{app.formal_name}'.format(app=app)
            / 'build' / 'Debug-iphonesimulator'
            / '{app.formal_name}.app'.format(app=app)
        )

    def bundle_path(self, app):
        return self.platform_path / '{app.formal_name}'.format(app=app)


class iOSXcodeMixin(iOSXcodePassiveMixin):
    def add_options(self, parser):
        super().add_options(parser)
        parser.add_argument(
            '-d',
            '--device',
            help='The device UDID to target',
            required=False,
        )

    def select_target_device(self):
        """
        Select the target device to use for iOS builds.

        Interrogates the system to get the list of available simulators

        If there is only a single iOS version available, that version
        will be selected automatically.

        If there is only one simulator available, that version will be selected
        automatically.

        If the user has specified a device at the command line, it will be
        used in preference to any
        """
        simulators = get_simulators('iOS', sub=self.subprocess)

        if self.options.device:
            # User has provided a UDID at the command line; look for it.
            for iOS_version, devices in simulators.items():
                try:
                    device = devices[self.options.device]
                    return self.options.device, iOS_version, device
                except KeyError:
                    # UDID doesn't exist in this iOS version; try another.
                    pass

            # We've iterated through all available iOS versions and
            # found no match; return an error.
            raise BriefcaseCommandError(
                "Invalid simulator UDID {udid}".format(
                    udid=self.options.device
                )
            )

        if len(simulators) == 0:
            raise BriefcaseCommandError(
                "No iOS simulators available."
            )
        elif len(simulators) == 1:
            iOS_version = list(simulators.keys())[0]
        else:
            print()
            print("Select iOS version:")
            print()
            iOS_version = select_option({
                version: version
                for version in simulators.keys()
            }, input=self.input)

        devices = simulators[iOS_version]

        if len(devices) == 0:
            raise BriefcaseCommandError(
                "No simulators available for iOS {iOS_version}.".format(
                    iOS_version=iOS_version
                )
            )
        elif len(devices) == 1:
            udid = list(devices.keys())[0]
        else:
            print()
            print("Select simulator device:")
            print()
            udid = select_option(devices, input=self.input)

        device = devices[udid]

        return udid, iOS_version, device


class iOSXcodeCreateCommand(iOSXcodePassiveMixin, CreateCommand):
    description = "Create and populate a iOS Xcode project."


class iOSXcodeUpdateCommand(iOSXcodePassiveMixin, UpdateCommand):
    description = "Update an existing iOS Xcode project."


class iOSXcodeBuildCommand(iOSXcodeMixin, BuildCommand):
    description = "Build an iOS Xcode project."

    def build_app(self, app: BaseConfig):
        """
        Build the Xcode project for the application.

        :param app: The application to build
        """
        udid, iOS_version, device = self.select_target_device()

        print()
        print("Targeting an {device} running iOS {iOS_version} (device UDID {udid})".format(
            device=device,
            iOS_version=iOS_version,
            udid=udid,
        ))

        print()
        print('[{app.name}] Building XCode project...'.format(
            app=app
        ))

        # build_settings = [
        #     ('AD_HOC_CODE_SIGNING_ALLOWED', 'YES'),
        #     ('CODE_SIGN_IDENTITY', '-'),
        #     ('VALID_ARCHS', '"i386 x86_64"'),
        #     ('ARCHS', 'x86_64'),
        #     ('ONLY_ACTIVE_ARCHS', 'NO')
        # ]
        # build_settings_str = ['{}={}'.format(*x) for x in build_settings]

        try:
            print()
            self.subprocess.run(
                [
                    'xcodebuild',  # ' '.join(build_settings_str),
                    '-project', self.bundle_path(app) / '{app.formal_name}.xcodeproj'.format(app=app),
                    '-destination',
                    'platform="iOS Simulator,name={device},OS={iOS_version}"'.format(
                        device=device,
                        iOS_version=iOS_version,
                    ),
                    '-quiet',
                    '-configuration', 'Debug',
                    '-arch', 'x86_64',
                    '-sdk', 'iphonesimulator',
                    'build'
                ],
                check=True,
            )
            print('Build succeeded.')
        except subprocess.CalledProcessError:
            print()
            raise BriefcaseCommandError(
                "Unable to build app {app.name}.".format(app=app)
            )


class iOSXcodeRunCommand(iOSXcodeMixin, RunCommand):
    description = "Run an iOS Xcode project."

    def run_app(self, app: BaseConfig):
        """
        Start the application.

        :param app: The config object for the app
        :param base_path: The path to the project directory.
        """
        udid, iOS_version, device = self.select_target_device()
        print()
        print("Targeting an {device} running iOS {iOS_version} (device UDID {udid})".format(
            device=device,
            iOS_version=iOS_version,
            udid=udid,
        ))

        # The simulator needs to be booted before being started.
        # If it's shut down, we can boot it again; but if it's currently
        # shutting down, we need to wait for it to shut down before restarting.
        device_state = get_device_state(udid, sub=self.subprocess)
        if device_state not in {DeviceState.SHUTDOWN, DeviceState.BOOTED}:
            print('Waiting for simulator...', flush=True, end='')
            while device_state not in {DeviceState.SHUTDOWN, DeviceState.BOOTED}:
                time.sleep(2)
                print('.', flush=True, end='')
                device_state = get_device_state(udid, sub=self.subprocess)

        if device_state == DeviceState.SHUTDOWN:
            try:
                print("Booting {device} simulator running iOS {iOS_version}...".format(
                        device=device,
                        iOS_version=iOS_version,
                    )
                )
                self.subprocess.run(
                    ['xcrun', 'simctl', 'boot', udid],
                    check=True
                )
            except subprocess.CalledProcessError:
                raise BriefcaseCommandError(
                    "Unable to boot {device} simulator running iOS {iOS_version}".format(
                        device=device,
                        iOS_version=iOS_version,
                    )
                )

        # We now know the simulator is *running*, so we can open it.
        try:
            print("Opening {device} simulator running iOS {iOS_version}...".format(
                    device=device,
                    iOS_version=iOS_version,
                )
            )
            self.subprocess.run(
                ['open', '-a', 'Simulator', '--args', '-CurrentDeviceUDID', udid],
                check=True
            )
        except subprocess.CalledProcessError:
            raise BriefcaseCommandError(
                "Unable to open {device} simulator running iOS {iOS_version}".format(
                    device=device,
                    iOS_version=iOS_version,
                )
            )

        # Try to uninstall the app first. If the app hasn't been installed
        # before, this will still succeed.
        app_identifier = '.'.join([app.bundle, app.name])
        print('[{app.name}] Uninstalling old app version...'.format(
            app=app
        ))
        try:
            self.subprocess.run(
                ['xcrun', 'simctl', 'uninstall', udid, app_identifier],
                check=True
            )
        except subprocess.CalledProcessError:
            raise BriefcaseCommandError(
                "Unable to uninstall old version of app {app.name}.".format(
                    app=app
                )
            )

        # Install the app.
        print('[{app.name}] Installing new app version...'.format(
            app=app
        ))
        try:
            self.subprocess.run(
                ['xcrun', 'simctl', 'install', udid, self.binary_path(app)],
                check=True
            )
        except subprocess.CalledProcessError:
            raise BriefcaseCommandError(
                "Unable to install new version of app {app.name}.".format(
                    app=app
                )
            )

        print('[{app.name}] Starting app...'.format(
            app=app
        ))
        try:
            self.subprocess.run(
                ['xcrun', 'simctl', 'launch', udid, app_identifier],
                check=True
            )
        except subprocess.CalledProcessError:
            raise BriefcaseCommandError(
                "Unable to launch app {app.name}.".format(
                    app=app
                )
            )


class iOSXcodePublishCommand(iOSXcodeMixin, PublishCommand):
    description = "Publish an iOS app."
    publication_channels = ['ios_appstore']
    default_publication_channel = 'ios_appstore'


# Declare the briefcase command bindings
create = iOSXcodeCreateCommand  # noqa
update = iOSXcodeUpdateCommand  # noqa
build = iOSXcodeBuildCommand  # noqa
run = iOSXcodeRunCommand  # noqa
publish = iOSXcodePublishCommand  # noqa
