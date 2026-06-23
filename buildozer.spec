[app]

# (str) Title of your application
title = PureNote

# (str) Package name
package.name = purenote

# (str) Package domain (needed for android/ios packaging)
package.domain = bbnss.test

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
# No `db`: the notes database is created/seeded at runtime, never shipped.
source.include_exts = py,png,jpg,ttf,kv

# (list) Source files to exclude
source.exclude_exts = bak,orig
source.exclude_dirs = .venv,images,__pycache__,PureNote_export

# (str) Application versioning
version = 2.0

# (list) Application requirements
requirements = python3,kivy==2.3.1,plyer

# (str) Presplash of the application
presplash.filename = %(source.dir)s/logo.png

# (str) Icon of the application
icon.filename = %(source.dir)s/logo.png

# (list) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (list) Permissions
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
# Google Play currently requires target API 35 (Android 15) for new apps/updates.
android.api = 35

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
# android.ndk = 25b

# (list) The Android archs to build for
# Debug: arm64-v8a only (faster). Re-add armeabi-v7a for the release AAB.
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >= 23)
android.allow_backup = True

# (str) Format used to package the app for release mode (aab for the Play Store).
android.release_artifact = aab

# (str) Format used to package the app for debug mode (apk for sideloading).
android.debug_artifact = apk

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
