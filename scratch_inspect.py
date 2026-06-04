import sys

try:
    import win32com.client
    print("win32com.client imported successfully!")
except ImportError:
    print("win32com.client NOT found!")
