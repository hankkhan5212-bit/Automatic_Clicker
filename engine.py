#!/usr/bin/env python3
"""
执行引擎（与之前类似），当节点成功并决定下一节点时会触发 edge_highlight_callback(src,dst)

修复：
- 统一日志接口：内部使用 self.log(*parts) 将 parts 拼接为单个字符串后调用用户提供的 log_callback(str)
- 保持 edge_highlight_callback(src,dst) 行为不变
"""
import threading
import time
import pyautogui
from typing import Callable, Optional

try:
    import cv2  # noqa: F401
    HAS_OPENCV = True
except Exception:
    HAS_OPENCV = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

from models import FlowModel, NodeModel

class FlowEngine:
    def __init__(self, flow: FlowModel, log_callback: Optional[Callable[[str], None]] = None):
        self.flow = flow
        # user-provided callback that accepts a single string
        self._log_callback = log_callback or (lambda s: None)
        self._stop = threading.Event()
        self._thread = None
        self.edge_highlight_callback = None

    def log(self, *parts):
        """内部统一日志接口：把多个 parts 拼接为一个字符串后交给回调"""
        try:
            text = " ".join(str(p) for p in parts)
        except Exception:
            text = str(parts)
        try:
            self._log_callback(text)
        except Exception:
            # 忽略回调异常，避免影响引擎运行
            pass

    def start(self):
        if self._thread and self._thread.is_alive():
            self.log("引擎已在运行")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log("引擎启动")

    def stop(self):
        self._stop.set()
        self.log("请求停止引擎")

    def is_running(self):
        return bool(self._thread and self._thread.is_alive())

    def _locate_center(self, image_path: str, conf: Optional[float]):
        try:
            if conf is not None and HAS_OPENCV:
                return pyautogui.locateCenterOnScreen(image_path, confidence=conf)
            else:
                return pyautogui.locateCenterOnScreen(image_path)
        except Exception as e:
            self.log("locate 异常:", repr(e))
            return None

    def _execute_node_once(self, node: NodeModel):
        attempts = 0
        unlimited = (node.retries < 0)
        conf = node.confidence
        while unlimited or attempts < node.retries:
            if self._stop.is_set():
                self.log("检测到停止请求，退出节点执行")
                return False
            attempts += 1
            self.log(f"[{node.label}] 尝试", attempts)
            pos = self._locate_center(node.image_path, conf)
            if pos:
                x,y = pos
                try:
                    for i in range(node.clicks):
                        if node.double_click:
                            pyautogui.doubleClick(x,y)
                        else:
                            pyautogui.click(x,y)
                        time.sleep(0.08)
                    # post wait (响应停止请求)
                    total = 0.0
                    while total < node.post_wait:
                        if self._stop.is_set():
                            break
                        time.sleep(0.1)
                        total += 0.1
                    return True
                except Exception as e:
                    self.log("点击异常:", repr(e))
                    return False
            else:
                # wait but be responsive to stop
                total = 0.0
                while total < node.wait_secs:
                    if self._stop.is_set():
                        break
                    time.sleep(0.1)
                    total += 0.1
        self.log(f"[{node.label}] 重试耗尽")
        return False

    def _choose_start_node(self):
        for nid, n in self.flow.nodes.items():
            if n.is_start:
                return nid
        # fallback by x coordinate
        left = None; minx = None
        for nid,n in self.flow.nodes.items():
            if minx is None or n.x < minx:
                minx = n.x; left = nid
        return left

    def _run(self):
        current = self._choose_start_node()
        if current is None:
            self.log("没有起始节点")
            return
        prev = []
        while current and not self._stop.is_set():
            node = self.flow.nodes.get(current)
            if node is None:
                self.log("节点不存在:", current)
                break
            self.log("执行节点:", node.label)
            ok = self._execute_node_once(node)
            if ok:
                prev.append(current)
                outs = self.flow.edges.get(current, [])
                if outs:
                    nxt = outs[0]
                else:
                    nxt = None
                # call edge highlight if exists
                if nxt and callable(getattr(self, "edge_highlight_callback", None)):
                    try:
                        self.edge_highlight_callback(current, nxt)
                    except Exception as e:
                        self.log("edge_highlight_callback 异常:", repr(e))
                current = nxt
                continue
            else:
                action = node.on_fail
                self.log("节点失败 action=", action)
                if action == "stop":
                    break
                elif action == "retry":
                    time.sleep(0.3)
                    continue
                elif action == "rollback":
                    if prev:
                        current = prev.pop()
                        continue
                    else:
                        break
                elif action == "skip":
                    outs = self.flow.edges.get(current, [])
                    current = outs[0] if outs else None
                    continue
                else:
                    break
        self.log("引擎结束")