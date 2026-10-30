import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from ks_webview import WebView

RENDER_URL = "https://velox-downloader.onrender.com"

class VeloxDownloaderApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical')
        self.webview = WebView(
            url=RENDER_URL,
            enable_javascript=True,
            enable_downloads=True
        )
        layout.add_widget(self.webview)
        return layout

if __name__ == '__main__':
    VeloxDownloaderApp().run()
