[app]
title = MPro
package.name = mpro
package.domain = org.mpro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0

# ← FIXED: only libs that work on Android
requirements = python3,kivy,websockets,numpy,certifi
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,RECORD_AUDIO,MODIFY_AUDIO_SETTINGS
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = armeabi-v7a, arm64-v8a
[buildozer]
log_level = 2
warn_on_root = 1
