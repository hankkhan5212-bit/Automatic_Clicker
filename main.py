#!/usr/bin/env python3
"""
程序入口：启动 PySide6 GUI
"""
import sys
from PySide6.QtWidgets import QApplication
from gui_qt import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 780)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()