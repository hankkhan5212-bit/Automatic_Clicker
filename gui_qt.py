#!/usr/bin/env python3
"""
PySide6 GUI（暗黑 / neon 主题）重写（替换原 gui_qt.py）
- 包含改进：连线/节点可选中并删除（Delete 键/右键菜单）
- Edge 动画与 engine 回调集成
"""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QTextEdit, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsPathItem, QGraphicsSimpleTextItem, QApplication, QMessageBox, QMenu
)
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath, QFont, QPainter, QFontDatabase, QKeySequence
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, QEvent

from models import FlowModel, make_default_node
from utils import ask_image_file, save_flow_file, open_flow_file, write_to_qtextedit, show_info, show_error
from engine import FlowEngine

NODE_W = 160
NODE_H = 64
PORT_R = 7

# ---------- Dark neon stylesheet ----------
DARK_QSS = """
QWidget {
  background: #0b0f14;
  color: #cfe8ff;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 11px;
}
QPushButton { background: #0f1720; border: 1px solid #1e293b; padding: 6px 10px; border-radius: 6px; color: #a8d1ff; }
QPushButton:hover { background: #122032; border-color: #2b9fff; color: #e0f6ff; }
QTextEdit { background: #071018; border: 1px solid #172a3a; color: #bfe8ff; padding: 6px; border-radius: 6px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #07131a; border: 1px solid #1e2f3f; padding: 4px; color: #dff7ff; border-radius: 4px; }
QLabel { color: #8fbfe6; font-weight: bold; }
"""

# ---------- Node / Edge classes ----------
class NodeItem(QGraphicsRectItem):
    def __init__(self, model, editor):
        super().__init__(0, 0, NODE_W, NODE_H)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
        self.model = model
        self.editor = editor
        self.setPos(model.x, model.y)

        # Text (neon green)
        self.text = QGraphicsSimpleTextItem(model.label, self)
        f = QFont("Consolas", 10)
        self.text.setFont(f)
        self.text.setPos(12, 10)
        try:
            self.text.setAcceptedMouseButtons(Qt.NoButton)
        except Exception:
            pass

        NEON_GREEN = QColor("#7CFF66")
        NEON_GREEN_BRIGHT = QColor("#BFFF9A")
        if hasattr(self.text, "setDefaultTextColor"):
            try:
                self.text.setDefaultTextColor(NEON_GREEN)
            except Exception:
                self.text.setBrush(QBrush(NEON_GREEN))
        elif hasattr(self.text, "setBrush"):
            self.text.setBrush(QBrush(NEON_GREEN))
        else:
            try:
                self.text.setPen(QPen(NEON_GREEN))
            except Exception:
                pass
        self._text_color = NEON_GREEN
        self._text_color_bright = NEON_GREEN_BRIGHT

        # ports
        self.in_port = QGraphicsEllipseItem(-PORT_R - 4, NODE_H / 2 - PORT_R, PORT_R * 2, PORT_R * 2, self)
        self.in_port.setBrush(QBrush(QColor("#223344")))
        self.in_port.setPen(QPen(QColor("#557"), 1))
        self.in_port.setData(0, ("in", model.id))
        self.in_port.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self.out_port = QGraphicsEllipseItem(NODE_W + 4, NODE_H / 2 - PORT_R, PORT_R * 2, PORT_R * 2, self)
        self.out_port.setBrush(QBrush(QColor("#223344")))
        self.out_port.setPen(QPen(QColor("#557"), 1))
        self.out_port.setData(0, ("out", model.id))
        self.out_port.setFlag(QGraphicsItem.ItemIsSelectable, False)

        # visual pulse
        self._pulse = 0.0
        self._pulse_dir = 1
        self._pulse_timer = QTimer()
        self._pulse_timer.setInterval(80)
        self._pulse_timer.timeout.connect(self._update_pulse)

    def _update_pulse(self):
        if self._pulse_dir > 0:
            self._pulse += 0.08
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1
        else:
            self._pulse -= 0.08
            if self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        r = QRectF(0, 0, NODE_W, NODE_H)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(r, QBrush(QColor("#0f1720")))
        pen = QPen(QColor("#20313f"), 2)
        painter.setPen(pen)
        painter.drawRoundedRect(r, 8, 8)

        if self.isSelected():
            glow = 180 + int(75 * self._pulse)
            neon = QColor(16, 200, 255, glow)
            for w in (6, 4, 2):
                p = QPen(neon, w)
                p.setCosmetic(True)
                painter.setPen(p)
                painter.drawRoundedRect(r.adjusted(-w/2, -w/2, w/2, w/2), 8 + w/2, 8 + w/2)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setSelected(True)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        p = self.pos()
        self.model.x = int(p.x()); self.model.y = int(p.y())
        self.editor.update_edges_positions()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            will_selected = bool(value)
            if will_selected:
                self._pulse_timer.start()
                try:
                    self.text.setDefaultTextColor(self._text_color_bright)
                except Exception:
                    self.text.setBrush(QBrush(self._text_color_bright))
            else:
                self._pulse_timer.stop()
                self._pulse = 0.0
                self._pulse_dir = 1
                try:
                    self.text.setDefaultTextColor(self._text_color)
                except Exception:
                    self.text.setBrush(QBrush(self._text_color))
            self.update()

        if change == QGraphicsItem.ItemPositionHasChanged:
            p = self.pos()
            self.model.x = int(p.x()); self.model.y = int(p.y())
            if hasattr(self.editor, "update_edges_positions"):
                self.editor.update_edges_positions()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    def __init__(self, src_item: NodeItem, dst_item: NodeItem, src_id, dst_id):
        super().__init__()
        self.src_item = src_item
        self.dst_item = dst_item
        self.src_id = src_id
        self.dst_id = dst_id
        self.setZValue(-1)
        self._glow_color = QColor("#00aaff")
        self._base_pen = QPen(QColor("#4b5563"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(self._base_pen)
        self.setAcceptHoverEvents(True)
        # allow selection
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        # animation
        self._anim_timer = QTimer()
        self._anim_timer.setInterval(30)
        self._anim_timer.timeout.connect(self._anim_step)
        self._anim_t = 0.0
        self._anim_steps = 30
        self._animating = False

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setSelected(True)

    def update_path(self):
        s_rect = self.src_item.out_port.sceneBoundingRect()
        d_rect = self.dst_item.in_port.sceneBoundingRect()
        s = s_rect.center()
        d = d_rect.center()
        path = QPainterPath()
        path.moveTo(s)
        dx = (d.x() - s.x()) * 0.5
        c1 = QPointF(s.x() + dx, s.y())
        c2 = QPointF(d.x() - dx, d.y())
        path.cubicTo(c1, c2, d)
        self.setPath(path)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = self.path()
        painter.setPen(self._base_pen)
        painter.drawPath(path)
        for w, alpha in ((10, 30), (6, 60), (3, 120)):
            p = QPen(self._glow_color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            c = QColor(self._glow_color)
            c.setAlpha(alpha)
            p.setColor(c)
            painter.setPen(p)
            painter.drawPath(path)
        if self._animating:
            t = self._anim_t
            pt = path.pointAtPercent(t)
            if not pt.isNull():
                r = 6
                brush = QBrush(QColor("#bfefff"))
                painter.setBrush(brush)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(pt, r, r)

    def start_animation(self, duration_ms=800):
        self._anim_steps = max(8, int(duration_ms / 30))
        self._anim_t = 0.0
        self._anim_step_delta = 1.0 / self._anim_steps
        self._animating = True
        self._anim_timer.start()

    def _anim_step(self):
        self._anim_t += getattr(self, "_anim_step_delta", 0.05)
        if self._anim_t > 1.0:
            self._anim_timer.stop()
            self._animating = False
            self._anim_t = 0.0
        self.update()


# ---------- MainWindow ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 流程编辑器 — Dark / Neon")
        self.flow = FlowModel()

        # apply dark style
        app = QApplication.instance()
        if app:
            app.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        hl = QHBoxLayout(central)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        try:
            hints = self.view.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform
            if hasattr(QPainter, "HighQualityAntialiasing"):
                hints |= QPainter.HighQualityAntialiasing
            self.view.setRenderHints(hints)
        except Exception:
            self.view.setRenderHints(self.view.renderHints() | QPainter.Antialiasing)
        hl.addWidget(self.view, 1)

        rightw = QWidget()
        rightlay = QVBoxLayout(rightw)
        hl.addWidget(rightw, 0)

        btn_add = QPushButton("添加节点"); btn_add.clicked.connect(self.add_node)
        btn_save = QPushButton("保存流程"); btn_save.clicked.connect(self.save_flow)
        btn_load = QPushButton("加载流程"); btn_load.clicked.connect(self.load_flow)
        btn_start = QPushButton("开始执行"); btn_start.clicked.connect(self.start_engine)
        btn_stop = QPushButton("停止执行"); btn_stop.clicked.connect(self.stop_engine)
        rightlay.addWidget(btn_add); rightlay.addWidget(btn_save); rightlay.addWidget(btn_load)
        rightlay.addWidget(btn_start); rightlay.addWidget(btn_stop)

        self.form_label = QLabel("节点属性")
        rightlay.addWidget(self.form_label)
        self.prop_form = QFormLayout()
        self.prop_widget = QWidget(); self.prop_widget.setLayout(self.prop_form)
        rightlay.addWidget(self.prop_widget)

        self.current_node_item = None

        self.log = QTextEdit(); self.log.setReadOnly(True)
        rightlay.addWidget(QLabel("日志")); rightlay.addWidget(self.log)

        self.node_items = {}
        self.edge_items = {}

        self.temp_line = None
        self.connecting_src = None

        self.view.viewport().installEventFilter(self)
        self.view.setMouseTracking(True)
        self.scene.selectionChanged.connect(self.on_selection_changed)

        # add Delete QAction and shortcut
        del_action = QAction("删除所选", self)
        del_action.setShortcut(QKeySequence.Delete)
        del_action.triggered.connect(self.delete_selected_items)
        self.addAction(del_action)

        self.engine = None

    def log_msg(self, *parts):
        write_to_qtextedit(self.log, *parts)

    def add_node(self):
        node = make_default_node(x=80 + len(self.flow.nodes) * 30, y=80 + len(self.flow.nodes) * 20, label_prefix="Node")
        node.label = f"Node{len(self.flow.nodes) + 1}"
        self.flow.add_node(node)
        self._add_node_item(node)

    def _add_node_item(self, node):
        item = NodeItem(node, self)
        self.scene.addItem(item)
        self.node_items[node.id] = item
        item.text.setText(node.label)

    def update_edges_positions(self):
        for e in list(self.edge_items.values()):
            e.update_path()

    def _add_edge_item(self, src_id, dst_id):
        if (src_id, dst_id) in self.edge_items: return
        src = self.node_items.get(src_id); dst = self.node_items.get(dst_id)
        if not src or not dst: return
        e = EdgeItem(src, dst, src_id, dst_id)
        self.scene.addItem(e)
        e.update_path()
        self.edge_items[(src_id, dst_id)] = e
        self.flow.add_edge(src_id, dst_id)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and (event.buttons() & Qt.LeftButton):
            pos = self.view.mapToScene(event.pos())
            items = self.scene.items(pos)
            for it in items:
                if isinstance(it, QGraphicsEllipseItem):
                    data = it.data(0)
                    if data and data[0] == "out":
                        self.connecting_src = data[1]
                        self.temp_line = self.scene.addPath(QPainterPath(), QPen(QColor("#00aaff"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        self.temp_start = it.sceneBoundingRect().center()
                        return True
        elif event.type() == QEvent.MouseMove and self.temp_line:
            pos = self.view.mapToScene(event.pos())
            path = QPainterPath()
            path.moveTo(self.temp_start)
            mid = (self.temp_start + pos) * 0.5
            path.cubicTo(QPointF(mid.x(), self.temp_start.y()), QPointF(mid.x(), pos.y()), pos)
            self.temp_line.setPath(path)
            return True
        elif event.type() == QEvent.MouseButtonRelease and self.temp_line:
            pos = self.view.mapToScene(event.pos())
            items = self.scene.items(pos)
            target_id = None
            for it in items:
                if isinstance(it, QGraphicsEllipseItem):
                    data = it.data(0)
                    if data and data[0] == "in":
                        target_id = data[1]; break
            try: self.scene.removeItem(self.temp_line)
            except: pass
            self.temp_line = None
            if target_id and target_id != self.connecting_src:
                self._add_edge_item(self.connecting_src, target_id)
                self.log_msg("已创建连线", self.connecting_src, "->", target_id)
            else:
                self.log_msg("未建立连线")
            self.connecting_src = None
            return True
        return super().eventFilter(obj, event)

    # context menus
    def create_node_menu(self, node_item):
        menu = QMenu()
        menu.addAction("删除节点", lambda: self.delete_node(node_item))
        menu.addAction("设为起始节点", lambda: self.mark_start(node_item))
        return menu

    def create_edge_menu(self, edge_item):
        menu = QMenu()
        menu.addAction("删除连线", lambda: self.delete_edge(edge_item))
        return menu

    def delete_node(self, node_item):
        nid = node_item.model.id
        for (s,d), e in list(self.edge_items.items()):
            if s == nid or d == nid:
                try: self.scene.removeItem(e)
                except: pass
                self.flow.remove_edge(s, d)
                del self.edge_items[(s,d)]
        try: self.scene.removeItem(node_item)
        except: pass
        self.flow.remove_node(nid)
        if nid in self.node_items: del self.node_items[nid]
        self.log_msg("删除节点", nid)

    def mark_start(self, node_item):
        for n in self.flow.nodes.values(): n.is_start = False
        node_item.model.is_start = True
        self.log_msg("标记起始:", node_item.model.id)

    def delete_edge(self, edge_item):
        meta = (edge_item.src_id, edge_item.dst_id)
        try: self.scene.removeItem(edge_item)
        except: pass
        self.flow.remove_edge(*meta)
        if meta in self.edge_items: del self.edge_items[meta]
        self.log_msg("删除连线", meta)

    # delete selected items (nodes or edges)
    def delete_selected_items(self):
        items = list(self.scene.selectedItems())
        if not items:
            return
        for it in items:
            # edge?
            if isinstance(it, EdgeItem):
                try: self.delete_edge(it)
                except: pass
                continue
            # node or child: find parent node
            node_item = None
            if isinstance(it, QGraphicsRectItem) and hasattr(it, "model"):
                node_item = it
            else:
                p = None
                try:
                    p = it.parentItem()
                except Exception:
                    p = None
                if p is not None and isinstance(p, QGraphicsRectItem) and hasattr(p, "model"):
                    node_item = p
            if node_item:
                try: self.delete_node(node_item)
                except: pass
        try: self.scene.clearSelection()
        except: pass

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
            event.accept()
            return
        return super().keyPressEvent(event)

    # save/load
    def save_flow(self):
        p = save_flow_file(self)
        if not p: return
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.flow.to_json())
            self.log_msg("保存:", p)
        except Exception as e:
            show_error(self, str(e))

    def load_flow(self):
        p = open_flow_file(self)
        if not p: return
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
            self.flow = FlowModel.from_json(text)
            self.scene.clear()
            self.node_items.clear(); self.edge_items.clear()
            for nid, node in self.flow.nodes.items():
                self._add_node_item(node)
            for src, outs in self.flow.edges.items():
                for dst in outs:
                    self._add_edge_item(src, dst)
            self.log_msg("已加载流程", p)
        except Exception as e:
            show_error(self, str(e))

    # selection -> properties
    def on_selection_changed(self):
        items = self.scene.selectedItems()
        node_item = None
        for it in items:
            if isinstance(it, QGraphicsRectItem) and hasattr(it, "model"):
                node_item = it; break
            # check parent item
            try:
                p = it.parentItem()
            except Exception:
                p = None
            if p is not None and isinstance(p, QGraphicsRectItem) and hasattr(p, "model"):
                node_item = p; break
        self.current_node_item = node_item
        self.update_properties_for_selection()

    def _clear_form_layout(self):
        while self.prop_form.count():
            item = self.prop_form.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def update_properties_for_selection(self):
        self._clear_form_layout()
        if not self.current_node_item:
            self.prop_form.addRow(QLabel("未选中节点"))
            return

        node = self.current_node_item.model

        self.le_label = QLineEdit(node.label)
        self.prop_form.addRow("标签:", self.le_label)

        hbox = QHBoxLayout()
        self.le_image = QLineEdit(node.image_path or "")
        btn_img = QPushButton("选择")
        btn_img.clicked.connect(self.choose_image_for_current)
        hbox.addWidget(self.le_image); hbox.addWidget(btn_img)
        container = QWidget(); container.setLayout(hbox)
        self.prop_form.addRow("图像路径:", container)

        self.sb_retries = QSpinBox(); self.sb_retries.setRange(-1, 9999); self.sb_retries.setValue(int(node.retries))
        self.prop_form.addRow("重试 (-1 无限):", self.sb_retries)

        self.ds_wait = QDoubleSpinBox(); self.ds_wait.setRange(0.0, 9999.0); self.ds_wait.setDecimals(2); self.ds_wait.setValue(float(node.wait_secs))
        self.prop_form.addRow("等待 (s):", self.ds_wait)

        self.sb_clicks = QSpinBox(); self.sb_clicks.setRange(1, 99); self.sb_clicks.setValue(int(node.clicks))
        self.prop_form.addRow("点击次数:", self.sb_clicks)

        self.ck_double = QCheckBox(); self.ck_double.setChecked(bool(node.double_click))
        self.prop_form.addRow("双击:", self.ck_double)

        self.ds_post = QDoubleSpinBox(); self.ds_post.setRange(0.0, 9999.0); self.ds_post.setDecimals(2); self.ds_post.setValue(float(node.post_wait))
        self.prop_form.addRow("点击后暂停 (s):", self.ds_post)

        self.le_conf = QLineEdit("" if node.confidence is None else str(node.confidence))
        self.prop_form.addRow("匹配置信度 (0-1):", self.le_conf)

        self.cb_onfail = QComboBox(); self.cb_onfail.addItems(["stop", "retry", "rollback", "skip"])
        idx = self.cb_onfail.findText(node.on_fail)
        if idx >= 0: self.cb_onfail.setCurrentIndex(idx)
        self.prop_form.addRow("失败时动作:", self.cb_onfail)

        self.ck_start = QCheckBox(); self.ck_start.setChecked(bool(node.is_start))
        self.prop_form.addRow("标记为起始节点:", self.ck_start)

        btn_apply = QPushButton("应用到节点"); btn_apply.clicked.connect(self.apply_properties_to_current)
        self.prop_form.addRow(btn_apply)

    def choose_image_for_current(self):
        if not self.current_node_item:
            show_info(self, "请先选中节点")
            return
        path = ask_image_file(self)
        if path:
            self.le_image.setText(path); self.current_node_item.model.image_path = path

    def apply_properties_to_current(self):
        if not self.current_node_item:
            show_info(self, "未选中节点"); return
        node = self.current_node_item.model
        node.label = self.le_label.text() or node.label
        node.image_path = self.le_image.text() or node.image_path
        try: node.retries = int(self.sb_retries.value())
        except: pass
        try: node.wait_secs = float(self.ds_wait.value())
        except: pass
        try: node.clicks = int(self.sb_clicks.value())
        except: pass
        node.double_click = bool(self.ck_double.isChecked())
        try: node.post_wait = float(self.ds_post.value())
        except: pass
        conf_text = self.le_conf.text().strip()
        if conf_text == "": node.confidence = None
        else:
            try: node.confidence = float(conf_text)
            except: pass
        node.on_fail = self.cb_onfail.currentText()
        node.is_start = bool(self.ck_start.isChecked())

        if hasattr(self.current_node_item, "text"):
            self.current_node_item.text.setText(node.label)
        self.update_edges_positions()
        self.log_msg("已应用属性到节点", node.id)

    # engine integration
    def start_engine(self):
        if self.engine and self.engine.is_running():
            self.log_msg("引擎已在运行"); return
        def ui_log(s):
            write_to_qtextedit(self.log, s)
        self.engine = FlowEngine(self.flow, log_callback=ui_log)
        def edge_cb(src, dst):
            QTimer.singleShot(0, lambda: self.animate_edge(src, dst))
        self.engine.edge_highlight_callback = edge_cb
        self.engine.start()
        self.log_msg("引擎启动")

    def stop_engine(self):
        if self.engine:
            self.engine.stop(); self.log_msg("请求停止引擎")

    def animate_edge(self, src, dst, duration=900):
        e = self.edge_items.get((src, dst))
        if not e:
            for (s,d), edge in self.edge_items.items():
                if s == src and d == dst:
                    e = edge; break
        if not e: return
        e.start_animation(duration)