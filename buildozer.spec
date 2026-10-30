[app]

title = VELOX Downloader
package.name = veloxdownloader
package.domain = com.jazan.velox

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json

version = 1.0.0

requirements = python3,kivy,pyjnius

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

android.accept_sdk_license = True

android.api = 36
android.ndk = 29
android.minapi = 23

p4a.branch = develop

orientation = portrait
fullscreen = 1

[buildozer]

log_level = 2
warn_on_root = 1
