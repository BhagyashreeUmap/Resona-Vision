import cv2
import numpy as np

print("OpenCV:", cv2.__version__)
print("SIFT:", hasattr(cv2, "SIFT_create"))
print("Environment check passed")
