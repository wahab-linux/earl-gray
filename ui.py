"""Small vector icons drawn at high resolution, without external assets."""
from functools import lru_cache
import math
from PIL import Image, ImageDraw
import customtkinter as ctk

GOOGLE = ("#4285F4", "#EA4335", "#FBBC05", "#34A853")


def draw_icon(name, color, size):
    scale = 4
    image = Image.new("RGBA", (size * scale, size * scale))
    draw = ImageDraw.Draw(image)
    factor = size * scale / 24
    def points(values):
        return tuple(value * factor for value in values)
    def line(values, fill=color, width=2):
        draw.line(points(values), fill=fill, width=max(1, round(width * factor)), joint="curve")
    def ellipse(box, fill=None, outline=color, width=2):
        draw.ellipse(points(box), fill=fill, outline=outline, width=max(1, round(width * factor)))
    if name == "logo":
        for box, fill in zip(((2, 2, 10, 10), (14, 2, 22, 10), (2, 14, 10, 22), (14, 14, 22, 22)), GOOGLE):
            draw.rounded_rectangle(points(box), radius=3 * factor, fill=fill)
    elif name == "plus":
        line((12, 5, 12, 19)); line((5, 12, 19, 12))
    elif name == "check":
        line((5, 12, 10, 17, 20, 6), width=2.5)
    elif name == "circle":
        ellipse((4, 4, 20, 20), width=1.5)
    elif name == "moon":
        # A crescent built as one polygon, with no assumed background color.
        outer = [(12 + 9 * math.cos(t), 12 + 9 * math.sin(t)) for t in [math.radians(a) for a in range(75, 286, 5)]]
        inner = [(16 + 8 * math.cos(t), 10 + 8 * math.sin(t)) for t in [math.radians(a) for a in range(265, 94, -5)]]
        draw.polygon([(x * factor, y * factor) for x, y in outer + inner], fill=color)
    elif name == "sun":
        ellipse((8, 8, 16, 16), fill=color)
        for angle in range(0, 360, 45):
            c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            line((12 + c * 7, 12 + s * 7, 12 + c * 10, 12 + s * 10))
    elif name in ("file", "zip"):
        line((14, 3, 5, 3, 5, 21, 19, 21, 19, 8, 14, 3, 14, 8, 19, 8), width=1.7)
        if name == "zip":
            for y in (10, 13, 16):
                draw.rectangle(points((10, y, 12, y + 1)), fill=color)
        else:
            line((8, 12, 15, 12), width=1.5); line((8, 16, 15, 16), width=1.5)
    elif name == "folder":
        line((3, 7, 3, 20, 21, 20, 21, 7, 12, 7, 10, 4, 3, 4, 3, 7, 21, 7), width=1.7)
    elif name == "merge":
        line((5, 4, 5, 8, 12, 13, 12, 21)); line((19, 4, 19, 8, 12, 13)); line((8, 17, 12, 21, 16, 17))
    elif name == "arrow":
        line((4, 12, 20, 12)); line((14, 6, 20, 12, 14, 18))
    elif name in ("up", "down"):
        y = 6 if name == "up" else 18
        line((12, 24 - y, 12, y)); line((6, 12, 12, y, 18, 12))
    elif name == "trash":
        line((4, 6, 20, 6)); line((8, 6, 8, 3, 16, 3, 16, 6)); line((6, 6, 7, 21, 17, 21, 18, 6)); line((10, 10, 10, 17), width=1.5); line((14, 10, 14, 17), width=1.5)
    elif name == "shield":
        line((12, 3, 20, 6, 19, 15, 12, 21, 5, 15, 4, 6, 12, 3), width=1.6)
        line((8, 12, 11, 15, 16, 9), width=1.6)
    return image.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=128)
def icon(name, color="#ffffff", size=20):
    light, dark = color if isinstance(color, tuple) else (color, color)
    return ctk.CTkImage(draw_icon(name, light, size * 2), draw_icon(name, dark, size * 2), size=(size, size))


def empty_art():
    image = Image.new("RGBA", (540, 300))
    for offset, angle, accent in ((-80, 12, GOOGLE[1]), (80, -12, GOOGLE[2]), (0, 0, GOOGLE[0])):
        paper = Image.new("RGBA", (170, 230))
        draw = ImageDraw.Draw(paper)
        draw.rounded_rectangle((3, 5, 167, 226), radius=18, fill="#dfe5f2")
        draw.rounded_rectangle((0, 0, 164, 220), radius=18, fill="white")
        draw.rounded_rectangle((18, 22, 145, 70), radius=10, fill=accent)
        for y in (96, 118, 140, 162):
            draw.rounded_rectangle((20, y, 140 if y != 162 else 95, y + 7), radius=3, fill="#e3e9f3")
        paper = paper.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        image.alpha_composite(paper, (270 + offset - paper.width // 2, 145 - paper.height // 2))
    draw = ImageDraw.Draw(image)
    for x, y, radius, color in ((70, 65, 10, GOOGLE[0]), (455, 215, 12, GOOGLE[3]), (410, 45, 6, GOOGLE[1]), (110, 250, 6, GOOGLE[2])):
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    return ctk.CTkImage(image, image, size=(270, 150))


class CircleButton(ctk.CTkButton):
    """Keep icon-only buttons circular instead of adding radius-sized padding."""
    def _create_grid(self):
        super()._create_grid()
        self.grid_columnconfigure(0, minsize=0)
        self.grid_columnconfigure(4, minsize=0)


def detach_images(widget):
    """Release CTk image callbacks before destroying a tree of widgets."""
    for child in widget.winfo_children():
        detach_images(child)
    if isinstance(widget, (ctk.CTkButton, ctk.CTkLabel)) and widget.cget("image") is not None:
        widget.configure(image=None)
