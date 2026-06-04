[app]

title = HandDrawn

package.name = handdrawn
package.domain = org.handdrawn

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf,ttc,otf
source.exclude_exts = spec

version = 1.0.0

requirements = python3,kivy,pillow,numpy

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.sdk = 33

android.archs = arm64-v8a

android.accept_sdk_license = True

orientation = portrait
fullscreen = 0
android.allow_backup = True

log_level = 2

p4a.branch = stable
