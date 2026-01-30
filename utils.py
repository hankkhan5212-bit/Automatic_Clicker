"""
常用工具：文件对话封装以及日志到 QTextEdit
"""
from PySide6.QtWidgets import QFileDialog, QMessageBox
import os

def ask_image_file(parent=None, title="选择目标图像"):
    path, _ = QFileDialog.getOpenFileName(parent, title, os.getcwd(), "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)")
    return path or None

def save_flow_file(parent=None, default="flow.json"):
    path, _ = QFileDialog.getSaveFileName(parent, "保存流程", default, "JSON Files (*.json);;All Files (*)")
    return path or None

def open_flow_file(parent=None):
    path, _ = QFileDialog.getOpenFileName(parent, "打开流程", os.getcwd(), "JSON Files (*.json);;All Files (*)")
    return path or None

def show_info(parent, msg):
    QMessageBox.information(parent, "提示", msg)

def show_error(parent, msg):
    QMessageBox.critical(parent, "错误", msg)

def write_to_qtextedit(widget, *parts):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = now + " - " + " ".join(str(p) for p in parts)
    widget.append(line)