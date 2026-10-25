"""
Automatic crop + GrabCut segmentation helper.

Usage:
  python auto_crop.py assets/source.jpg

This script will try to detect a person using OpenCV HOG detector and run
GrabCut to produce `assets/child.png`.

The output will have an alpha channel and a light feather blur applied to the mask
to smooth edges.
"""

import sys
import os
import cv2
import numpy as np
from PIL import Image


def grabcut_with_rect(img, rect, iter_count=5):
    mask = np.zeros(img.shape[:2], np.uint8)
    bgdModel = np.zeros((1,65), np.float64)
    fgdModel = np.zeros((1,65), np.float64)
    x,y,w,h = rect
    cv2.grabCut(img, mask, (x,y,w,h), bgdModel, fgdModel, iter_count, cv2.GC_INIT_WITH_RECT)
    # mask: probable foreground or foreground
    mask2 = np.where((mask==2)|(mask==0), 0, 1).astype('uint8')
    return mask2


def feather_mask(mask, ksize=21):
    # feather edges by blurring mask
    k = ksize if ksize % 2 == 1 else ksize+1
    f = cv2.GaussianBlur(mask.astype(np.float32), (k,k), 0)
    f = (f - f.min()) / (f.max() - f.min() + 1e-8)
    return f


def detect_person_bbox(img):
    # use HOG person detector to find the person
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, weights = hog.detectMultiScale(img, winStride=(8,8), padding=(8,8), scale=1.05)
    if len(rects) == 0:
        return None
    # pick the largest rectangle by area
    areas = [w*h for (x,y,w,h) in rects]
    idx = int(np.argmax(areas))
    x,y,w,h = rects[idx]
    # expand a bit
    pad_x = int(w*0.12)
    pad_y = int(h*0.12)
    x = max(0, x-pad_x)
    y = max(0, y-pad_y)
    w = min(img.shape[1]-x, w+2*pad_x)
    h = min(img.shape[0]-y, h+2*pad_y)
    return (x,y,w,h)


def detect_scooter_bbox(img):
    # deprecated - scooter detection removed (game uses only child sprite)
    return None


def save_rgba(img_bgr, mask_float, outpath):
    # mask_float in [0,1]
    b,g,r = cv2.split(img_bgr)
    alpha = (mask_float*255).astype('uint8')
    rgba = cv2.merge((b,g,r, alpha))
    Image.fromarray(cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)).save(outpath)


def main():
    if len(sys.argv) < 2:
        print('Usage: python auto_crop.py <path-to-photo>')
        return
    src = sys.argv[1]
    if not os.path.exists(src):
        print('File not found:', src)
        return
    img = cv2.imread(src)
    if img is None:
        print('Failed to read image')
        return

    assets = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(assets, exist_ok=True)

    # detect person
    pbox = detect_person_bbox(img)
    if pbox is not None:
        mask = grabcut_with_rect(img, pbox)
        fmask = feather_mask(mask, ksize=25)
        save_rgba(img, fmask, os.path.join(assets, 'child.png'))
        print('Saved child.png')
    else:
        print('Person not detected, please use manual extractor')


if __name__ == '__main__':
    main()
