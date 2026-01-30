# PySide6 可视化流程编辑器（原型）

截图：
![/images/<img width="1279" height="929" alt="ScreenShot_2026-01-30_115717_267" src="https://github.com/user-attachments/assets/a9c39cc8-b705-4f6e-9c97-c3ba931b5434" />]

安装依赖：
pip install -r requirements.txt

运行：
python main.py

说明：
- 在画布上点击“添加节点”创建节点，拖动节点改变位置。
- 在节点右侧小口（输出）按下拖动至另一个节点左侧小口（输入）建立连线。
- 右键点击节点或连线弹出菜单（删除、设为起始节点）。
- 点击“开始执行”会按流程顺序执行节点（调用 pyautogui 点击）.
- 可保存/加载流程（JSON）。

建议：
- 若需更漂亮的图标/主题，继续在 Qt 中添加资源（.qrc）和样式（QSS）。
- 可以扩展边为贝塞尔 更复杂样式、支持条件分支、并行等。
