"""
Interactive asset extractor.

Usage:
 - Save your photo into the project `assets/` folder as `source.jpg` (or any name),
   then run:
       python extract_assets.py assets/source.jpg

 - Drag to draw a rectangle. Press the buttons to save the current rectangle as
   `assets/child.png` or `assets/scooter.png`.
 - Press 'c' to clear the rectangle, or 'q' to quit.

This uses Pillow and Tkinter and will help you crop the child and the scooter
from a single photo.
"""

import sys
import os
from PIL import Image, ImageTk
import tkinter as tk


class Cropper(tk.Tk):
    def __init__(self, image_path):
        super().__init__()
        self.title('Asset Extractor - draw rectangle then save')
        self.image = Image.open(image_path).convert('RGBA')
        self.img_w, self.img_h = self.image.size
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas = tk.Canvas(self, width=self.img_w, height=self.img_h, cursor='cross')
        self.canvas.pack()
        self.canvas_img = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.cur_coords = None

        self.canvas.bind('<ButtonPress-1>', self.on_button_press)
        self.canvas.bind('<B1-Motion>', self.on_move)
        self.canvas.bind('<ButtonRelease-1>', self.on_button_release)
        self.bind('<c>', lambda e: self.clear_rect())
        self.bind('<q>', lambda e: self.quit())

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill='x')
        self.child_btn = tk.Button(btn_frame, text='Save as child.png', command=self.save_child)
        self.child_btn.pack(side='left', padx=6, pady=6)
        self.board_btn = tk.Button(btn_frame, text='Save as scooter.png', command=self.save_board)
        self.board_btn.pack(side='left', padx=6, pady=6)
        self.info = tk.Label(btn_frame, text='Draw rectangle and click a save button. Keys: c=clear, q=quit')
        self.info.pack(side='left', padx=6)

        self.asset_dir = os.path.join(os.path.dirname(__file__), 'assets')
        os.makedirs(self.asset_dir, exist_ok=True)

    def on_button_press(self, event):
        self.start_x = max(0, min(self.img_w, event.x))
        self.start_y = max(0, min(self.img_h, event.y))
        if self.rect:
            self.canvas.delete(self.rect)
            self.rect = None

    def on_move(self, event):
        x = max(0, min(self.img_w, event.x))
        y = max(0, min(self.img_h, event.y))
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)
        else:
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, x, y, outline='cyan', width=2)
        self.cur_coords = (self.start_x, self.start_y, x, y)

    def on_button_release(self, event):
        # finalize coords
        x = max(0, min(self.img_w, event.x))
        y = max(0, min(self.img_h, event.y))
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, x, y)
        self.cur_coords = (self.start_x, self.start_y, x, y)

    def clear_rect(self):
        if self.rect:
            self.canvas.delete(self.rect)
            self.rect = None
        self.cur_coords = None

    def _get_bbox(self):
        if not self.cur_coords:
            tk.messagebox.showinfo('No selection', 'Please drag to create a selection first')
            return None
        x1, y1, x2, y2 = self.cur_coords
        left = int(min(x1, x2))
        upper = int(min(y1, y2))
        right = int(max(x1, x2))
        lower = int(max(y1, y2))
        # clip
        left = max(0, min(self.img_w-1, left))
        upper = max(0, min(self.img_h-1, upper))
        right = max(left+1, min(self.img_w, right))
        lower = max(upper+1, min(self.img_h, lower))
        return (left, upper, right, lower)

    def save_child(self):
        bbox = self._get_bbox()
        if not bbox:
            return
        crop = self.image.crop(bbox)
        out = os.path.join(self.asset_dir, 'child.png')
        crop.save(out)
        tk.messagebox.showinfo('Saved', f'Saved child sprite to {out}')

    def save_board(self):
        bbox = self._get_bbox()
        if not bbox:
            return
        crop = self.image.crop(bbox)
        out = os.path.join(self.asset_dir, 'scooter.png')
        crop.save(out)
        tk.messagebox.showinfo('Saved', f'Saved scooter sprite to {out}')


def main():
    if len(sys.argv) < 2:
        print('Usage: python extract_assets.py <path-to-photo>')
        print('Example: python extract_assets.py assets/source.jpg')
        return
    path = sys.argv[1]
    if not os.path.exists(path):
        print('Path not found:', path)
        return
    app = Cropper(path)
    app.mainloop()


if __name__ == '__main__':
    main()
