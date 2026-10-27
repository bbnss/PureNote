[app]
title = PureNote
package.name = purenote
# Keep this ID so existing installations retain their private notes.
package.domain = bbnss.test
source.dir = .
source.include_exts = py,png,jpg,ttf,kv
source.exclude_exts = bak,orig
source.exclude_dirs = .venv,.build-venv,.git,.github,tests,images,__pycache__,PureNote_export,.pytest_cache,.ruff_cache
version = 3.0.2
android.numeric_version = 10218
# Avoid a transitive Android wheel that p4a's pure-Python install stage rejects.
requirements = python3,kivy==2.3.1,sqlite3,pyjnius,charset_normalizer==3.4.2
presplash.filename = %(source.dir)s/logo.png
icon.filename = %(source.dir)s/logo.png
orientation = portrait
fullscreen = 0

android.accept_sdk_license = True
# Notes are private. File access is granted by the system document picker.
# Omit android.permissions entirely: an empty value becomes android.permission.
android.api = 36
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.allow_backup = False
android.release_artifact = aab
android.debug_artifact = apk
p4a.bootstrap = sdl2
# Official v2026.05.09 release; don't silently pick up recipe changes.
p4a.branch = master
p4a.commit = 58d21141f17c889bf8585f5665921d72028f8831

[buildozer]
log_level = 2
warn_on_root = 1
