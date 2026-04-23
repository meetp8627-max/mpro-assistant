[app]
title = MPro Assistant
package.name = mproassistant
package.domain = org.meetp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy

# Android config
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

# Python for Android
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
