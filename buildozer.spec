[app]
title = Velox Downloader
package.name = veloxdownloader
package.domain = com.jazan.velox
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

requirements = python3,kivy,pyjnius

android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

orientation = portrait
fullscreen = 1

[buildozer]
log_level = 2
warn_on_root = 1
