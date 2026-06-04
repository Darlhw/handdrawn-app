# -*- coding: UTF-8 -*-
import os
import numpy as np
from PIL import Image, ImageFilter
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.logger import Logger
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.utils import platform
from kivy.clock import Clock
from kivy.metrics import dp
import threading


# ─── 核心转换逻辑 ──────────────────────────────────────────────

def pencil_sketch(img, depth=58, thickness=5, color_keep=50):
    gray = img.convert('L')
    if thickness > 1:
        w, h = gray.size
        scale = max(0.25, 1.0 - (thickness - 1) * 0.05)
        small = gray.resize((max(8, int(w * scale)), max(8, int(h * scale))), Image.NEAREST)
        gray = small.resize((w, h), Image.NEAREST)

    a = np.asarray(gray).astype('float')
    grad = np.gradient(a)
    grad_x, grad_y = grad
    grad_x = grad_x * depth / 100.
    grad_y = grad_y * depth / 100.
    A = np.sqrt(grad_x ** 2 + grad_y ** 2 + 1.)
    uni_x = grad_x / A
    uni_y = grad_y / A
    uni_z = 1. / A

    vec_el = np.pi / 2.2
    vec_az = np.pi / 4.
    dx = np.cos(vec_el) * np.cos(vec_az)
    dy = np.cos(vec_el) * np.sin(vec_az)
    dz = np.sin(vec_el)

    b = 255 * (dx * uni_x + dy * uni_y + dz * uni_z)
    b = b.clip(0, 255)

    if color_keep > 0:
        orig = np.array(img).astype(np.float32)
        sketch = np.stack([b, b, b], axis=-1)
        ratio = color_keep / 100.0
        result = sketch * (1 - ratio) + orig * ratio
        result = np.clip(result, 0, 255).astype(np.uint8)
        return Image.fromarray(result)
    return Image.fromarray(b.astype('uint8'))


def watercolor(img, depth=58, color_keep=50):
    arr = np.array(img)
    levels = max(4, 24 - int(depth / 5))
    step = 256 // levels
    arr = (arr // step) * step + step // 2
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    poster = Image.fromarray(arr)

    smooth = poster
    for _ in range(3):
        smooth = smooth.filter(ImageFilter.SMOOTH_MORE)

    result = smooth.filter(ImageFilter.GaussianBlur(radius=1.2))

    if color_keep > 0:
        orig = np.array(img).astype(np.float32)
        res = np.array(result).astype(np.float32)
        ratio = color_keep / 100.0
        blended = res * (1 - ratio) + orig * ratio
        blended = np.clip(blended, 0, 255).astype(np.uint8)
        return Image.fromarray(blended)
    return result


# ─── Kivy 应用 ─────────────────────────────────────────────────

PRIMARY = (94/255, 79/255, 162/255, 1)       # #5e4fa2
PRIMARY_LIGHT = (232/255, 229/255, 242/255, 1)
BG_COLOR = (240/255, 238/255, 234/255, 1)     # #f0eeea
WHITE = (1, 1, 1, 1)
TEXT_DARK = (51/255, 51/255, 51/255, 1)
TEXT_GRAY = (136/255, 136/255, 136/255, 1)
BORDER_COLOR = (212/255, 207/255, 199/255, 1)
GREEN = (42/255, 157/255, 143/255, 1)


class HandDrawnApp(App):
    def _get_chinese_font(self):
        if platform == 'android':
            for p in ['/system/fonts/NotoSansSC-Regular.otf',
                      '/system/fonts/NotoSansCJK-Regular.ttc',
                      '/system/fonts/DroidSansFallback.ttf']:
                if os.path.exists(p):
                    return p
        elif os.name == 'nt':
            for p in ['C:/Windows/Fonts/msyh.ttc',
                      'C:/Windows/Fonts/simhei.ttf',
                      'C:/Windows/Fonts/simsun.ttc']:
                if os.path.exists(p):
                    return p
        return None

    def build(self):
        self.original_image = None
        self.result_image = None
        self.output_path = None
        self.font_path = self._get_chinese_font()

        Window.clearcolor = BG_COLOR[:3]

        root = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        # ── 顶部标题 ──
        title_bar = BoxLayout(size_hint_y=0.06, orientation='horizontal')
        with title_bar.canvas.before:
            Color(*PRIMARY)
            self.title_rect = Rectangle(pos=title_bar.pos, size=title_bar.size)
        title_bar.bind(pos=self._update_title_rect, size=self._update_title_rect)
        title_label = Label(text='图片转手绘风格', font_size=dp(18),
                           color=WHITE, bold=True, font_name=self.font_path)
        title_bar.add_widget(title_label)
        root.add_widget(title_bar)

        # ── 图片选择区 ──
        select_bar = BoxLayout(size_hint_y=0.08, spacing=dp(8))
        self.path_label = Label(text='未选择图片', size_hint_x=0.7,
                               font_size=dp(14), color=TEXT_DARK,
                               halign='left', valign='middle', font_name=self.font_path)
        self.path_label.bind(size=self.path_label.setter('text_size'))
        select_bar.add_widget(self.path_label)

        btn_browse = Button(text='浏览', size_hint_x=0.3,
                           background_color=PRIMARY, color=WHITE,
                           font_size=dp(14), font_name=self.font_path)
        btn_browse.bind(on_press=self.browse_file)
        select_bar.add_widget(btn_browse)
        root.add_widget(select_bar)

        # ── 参数控制区 ──
        params_box = BoxLayout(orientation='vertical', size_hint_y=0.32,
                               spacing=dp(4), padding=dp(8))

        # 手绘深度
        params_box.add_widget(Label(text='手绘深度', font_size=dp(13),
                                   color=TEXT_DARK, size_hint_y=0.12,
                                   font_name=self.font_path))
        self.depth_slider = Slider(min=1, max=100, value=58,
                                   size_hint_y=0.15)
        self.depth_value = Label(text='58', font_size=dp(12),
                                color=PRIMARY, size_hint_y=0.1,
                                font_name=self.font_path)
        self.depth_slider.bind(value=self._on_depth_change)
        params_box.add_widget(self.depth_slider)
        params_box.add_widget(self.depth_value)

        # 线条粗细
        params_box.add_widget(Label(text='线条粗细', font_size=dp(13),
                                   color=TEXT_DARK, size_hint_y=0.12,
                                   font_name=self.font_path))
        self.thickness_slider = Slider(min=1, max=20, value=5,
                                      size_hint_y=0.15)
        self.thickness_value = Label(text='5', font_size=dp(12),
                                    color=GREEN, size_hint_y=0.1,
                                    font_name=self.font_path)
        self.thickness_slider.bind(value=self._on_thickness_change)
        params_box.add_widget(self.thickness_slider)
        params_box.add_widget(self.thickness_value)

        # 色彩保留
        params_box.add_widget(Label(text='色彩保留', font_size=dp(13),
                                   color=TEXT_DARK, size_hint_y=0.12,
                                   font_name=self.font_path))
        self.color_slider = Slider(min=0, max=100, value=50,
                                   size_hint_y=0.15)
        self.color_value = Label(text='50%', font_size=dp(12),
                                color=PRIMARY, size_hint_y=0.1,
                                font_name=self.font_path)
        self.color_slider.bind(value=self._on_color_change)
        params_box.add_widget(self.color_slider)
        params_box.add_widget(self.color_value)

        root.add_widget(params_box)

        # ── 风格选择 ──
        style_box = BoxLayout(size_hint_y=0.08, spacing=dp(8))
        self.btn_pencil = ToggleButton(text='铅笔素描', group='style',
                                       state='down', font_size=dp(13),
                                       background_color=PRIMARY, color=WHITE,
                                       font_name=self.font_path)
        self.btn_watercolor = ToggleButton(text='水彩渲染', group='style',
                                           font_size=dp(13),
                                           background_color=BORDER_COLOR,
                                           color=TEXT_DARK,
                                           font_name=self.font_path)
        style_box.add_widget(self.btn_pencil)
        style_box.add_widget(self.btn_watercolor)
        root.add_widget(style_box)

        # ── 预览区 ──
        preview_box = FloatLayout(size_hint_y=0.3)
        with preview_box.canvas.before:
            Color(*WHITE)
            self.preview_rect = Rectangle(pos=preview_box.pos, size=preview_box.size)
            Color(*BORDER_COLOR)
            self.preview_border = None
        preview_box.bind(pos=self._update_preview_rect, size=self._update_preview_rect)

        self.preview_image = KivyImage(source='', fit_mode='contain',
                                       size_hint=(0.9, 0.9),
                                       pos_hint={'center_x': 0.5, 'center_y': 0.5})
        preview_box.add_widget(self.preview_image)

        self.hint_label = Label(text='点击"浏览"选择图片', font_size=dp(16),
                               color=TEXT_GRAY, pos_hint={'center_x': 0.5, 'center_y': 0.5},
                               font_name=self.font_path)
        preview_box.add_widget(self.hint_label)
        root.add_widget(preview_box)

        # ── 底部按钮 ──
        bottom_box = BoxLayout(size_hint_y=0.1, spacing=dp(8))

        # 输出格式
        self.format_spinner = Spinner(text='PNG', values=('JPEG', 'PNG', 'WebP'),
                                     size_hint_x=0.4, font_size=dp(13),
                                     font_name=self.font_path)
        bottom_box.add_widget(self.format_spinner)

        self.btn_convert = Button(text='开始转换', size_hint_x=0.6,
                                  background_color=PRIMARY, color=WHITE,
                                  font_size=dp(16), bold=True,
                                  font_name=self.font_path)
        self.btn_convert.bind(on_press=self.start_convert)
        bottom_box.add_widget(self.btn_convert)

        root.add_widget(bottom_box)

        # 状态栏
        self.status_label = Label(text='就绪', font_size=dp(11),
                                 color=TEXT_GRAY, size_hint_y=0.04,
                                 font_name=self.font_path)
        root.add_widget(self.status_label)

        return root

    def _update_title_rect(self, instance, value):
        self.title_rect.pos = instance.pos
        self.title_rect.size = instance.size

    def _update_preview_rect(self, instance, value):
        self.preview_rect.pos = instance.pos
        self.preview_rect.size = instance.size

    def _on_depth_change(self, instance, value):
        self.depth_value.text = str(int(value))

    def _on_thickness_change(self, instance, value):
        self.thickness_value.text = str(int(value))

    def _on_color_change(self, instance, value):
        self.color_value.text = f'{int(value)}%'

    def browse_file(self, instance):
        if platform == 'android':
            from android.storage import primary_external_storage_path
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType('image/*')
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            currentActivity = PythonActivity.mActivity
            currentActivity.startActivityForResult(intent, 1)
        else:
            # 桌面端文件选择
            from kivy.core.window import Window
            from tkinter import filedialog
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                filetypes=[('Image files', '*.png *.jpg *.jpeg *.bmp *.webp')]
            )
            root.destroy()
            if path:
                self._load_image(path)

    def _load_image(self, path):
        try:
            self.original_image = Image.open(path).convert('RGB')
            self.path_label.text = os.path.basename(path)
            self.status_label.text = f'已加载: {os.path.basename(path)}'
            self.hint_label.opacity = 0

            # 显示原图预览
            preview = self.original_image.copy()
            preview.thumbnail((400, 400), Image.LANCZOS)
            tmp_path = os.path.join(self._get_tmp_dir(), '_preview.png')
            preview.save(tmp_path)
            self.preview_image.source = tmp_path
        except Exception as e:
            self.status_label.text = f'加载失败: {e}'

    def _get_tmp_dir(self):
        tmp = os.path.join(os.path.expanduser('~'), '.handdrawn')
        os.makedirs(tmp, exist_ok=True)
        return tmp

    def start_convert(self, instance):
        if not self.original_image:
            self.status_label.text = '请先选择图片'
            return

        self.btn_convert.disabled = True
        self.btn_convert.text = '转换中...'
        self.status_label.text = '正在转换...'

        params = {
            'depth': int(self.depth_slider.value),
            'thickness': int(self.thickness_slider.value),
            'color_keep': int(self.color_slider.value),
            'style': 'pencil' if self.btn_pencil.state == 'down' else 'watercolor'
        }

        threading.Thread(target=self._do_convert, args=(params,), daemon=True).start()

    def _do_convert(self, params):
        try:
            if params['style'] == 'pencil':
                self.result_image = pencil_sketch(
                    self.original_image, params['depth'],
                    params['thickness'], params['color_keep']
                )
            else:
                self.result_image = watercolor(
                    self.original_image, params['depth'], params['color_keep']
                )

            # 保存结果
            fmt = self.format_spinner.text.lower()
            ext = 'jpeg' if fmt == 'jpg' else fmt
            if ext == 'jpeg':
                ext = 'jpg'
            out_name = f'handdrawn_result.{ext if ext != "webp" else "png"}'
            out_path = os.path.join(self._get_tmp_dir(), out_name)
            self.result_image.save(out_path, quality=95)
            self.output_path = out_path

            # 更新预览
            preview = self.result_image.copy()
            preview.thumbnail((400, 400), Image.LANCZOS)
            tmp_path = os.path.join(self._get_tmp_dir(), '_result_preview.png')
            preview.save(tmp_path)

            Clock.schedule_once(lambda dt: self._update_ui(tmp_path, out_path))

        except Exception as e:
            Logger.error(f'Convert error: {e}')
            Clock.schedule_once(lambda dt: self._on_error(str(e)))

    def _update_ui(self, preview_path, output_path):
        self.preview_image.source = preview_path
        self.btn_convert.disabled = False
        self.btn_convert.text = '开始转换'
        self.status_label.text = '转换完成! 长按预览图保存'

        # Android 上自动保存到相册
        if platform == 'android':
            try:
                from android.storage import primary_external_storage_path
                import shutil
                save_dir = os.path.join(primary_external_storage_path(), 'Pictures', 'HandDrawn')
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, 'handdrawn_result.png')
                shutil.copy2(output_path, save_path)
                self.status_label.text = f'已保存到: {save_path}'
            except Exception as e:
                Logger.error(f'Save error: {e}')

    def _on_error(self, msg):
        self.btn_convert.disabled = False
        self.btn_convert.text = '开始转换'
        self.status_label.text = f'错误: {msg}'


if __name__ == '__main__':
    HandDrawnApp().run()
