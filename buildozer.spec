[app]
title = MPro
package.name = mpro
package.domain = org.mpro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0
requirements = python3,kivy,websockets,numpy,certifi,openssl
orientation = portrait
android.permissions = INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license = True
log_level = 2

[buildozer]
log_level = 2
