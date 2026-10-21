"""Головне вікно програми: панель керування + область відображення графу."""

import csv
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QComboBox, QSpinBox, QSlider, QMessageBox, QLineEdit, QScrollArea, QFrame
)
from PyQt5.QtCore import QTimer, Qt

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from colors import (
    COLOR_UNVISITED, COLOR_IN_STACK, COLOR_CURRENT, COLOR_EXPANDED, COLOR_PATH
)
from graph_utils import (
    generate_explicit_graph, generate_tree_graph, make_directed, layered_positions
)
from dfs_search import DFSSearch
from bfs_search import BFSSearch


class SearchVisualization(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BFS / DFS Visualization (пошук у ширину та глибину)")
        self.resize(1300, 800)

        self.G = None
        self.graph_type = "Explicit Graph"
        self.pos = {}
        self.tree_edges = []

        self.search = None            # екземпляр BFSSearch або DFSSearch під час пошуку
        self.search_start_time = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.search_step)

        self._build_ui()
        self.load_graph()

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setAlignment(Qt.AlignTop)

        pl.addWidget(QLabel("Graph size (nodes):"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["30", "40"])
        pl.addWidget(self.size_combo)

        pl.addWidget(QLabel("Graph type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Explicit Graph", "Tree", "Directed Graph"])
        self.type_combo.currentTextChanged.connect(self._update_load_button_text)
        pl.addWidget(self.type_combo)

        self.load_btn = QPushButton("Load Explicit Graph")
        self.load_btn.clicked.connect(self.load_graph)
        pl.addWidget(self.load_btn)

        pl.addWidget(self._hline())

        pl.addWidget(QLabel("Algorithm:"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["BFS", "DFS"])
        self.algorithm_combo.currentTextChanged.connect(self._update_start_button_text)
        pl.addWidget(self.algorithm_combo)

        pl.addWidget(QLabel("Start node:"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 999)
        self.start_spin.setValue(0)
        pl.addWidget(self.start_spin)

        pl.addWidget(QLabel("Goal node:"))
        self.goal_spin = QSpinBox()
        self.goal_spin.setRange(0, 999)
        self.goal_spin.setValue(10)
        pl.addWidget(self.goal_spin)

        pl.addWidget(QLabel("Order of neighbors:"))
        self.order_combo = QComboBox()
        self.order_combo.addItems(["asc", "desc"])
        pl.addWidget(self.order_combo)

        self.start_btn = QPushButton("Start BFS")
        self.start_btn.clicked.connect(self.start_search)
        pl.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Pause/Resume")
        self.pause_btn.clicked.connect(self.pause_resume)
        pl.addWidget(self.pause_btn)

        self.reset_btn = QPushButton("Reset colors")
        self.reset_btn.clicked.connect(self.reset_colors)
        pl.addWidget(self.reset_btn)

        self.compare_btn = QPushButton("Compare BFS vs DFS")
        self.compare_btn.clicked.connect(self.compare_algorithms)
        pl.addWidget(self.compare_btn)

        pl.addWidget(self._hline())

        pl.addWidget(QLabel("Add/Remove nodes & edges:"))
        self.new_node_edit = QLineEdit()
        self.new_node_edit.setPlaceholderText("New node ID (int)")
        pl.addWidget(self.new_node_edit)

        pl.addWidget(QLabel("Connect new node to:"))
        self.connect_edit = QLineEdit()
        self.connect_edit.setPlaceholderText("Connect to nodes (e.g., 1,3,5)")
        pl.addWidget(self.connect_edit)

        self.add_node_btn = QPushButton("Add Node with Connections")
        self.add_node_btn.clicked.connect(self.add_node)
        pl.addWidget(self.add_node_btn)

        self.remove_node_edit = QLineEdit()
        self.remove_node_edit.setPlaceholderText("Node ID to remove (int)")
        pl.addWidget(self.remove_node_edit)

        self.remove_node_btn = QPushButton("Remove Node")
        self.remove_node_btn.clicked.connect(self.remove_node)
        pl.addWidget(self.remove_node_btn)

        self.edge_from_edit = QLineEdit()
        self.edge_from_edit.setPlaceholderText("Edge from (int)")
        pl.addWidget(self.edge_from_edit)

        self.edge_to_edit = QLineEdit()
        self.edge_to_edit.setPlaceholderText("Edge to (int)")
        pl.addWidget(self.edge_to_edit)

        self.add_edge_btn = QPushButton("Add Edge/Arc")
        self.add_edge_btn.clicked.connect(self.add_edge)
        pl.addWidget(self.add_edge_btn)

        self.remove_edge_btn = QPushButton("Remove Edge/Arc")
        self.remove_edge_btn.clicked.connect(self.remove_edge)
        pl.addWidget(self.remove_edge_btn)

        self.edge_to_arc_btn = QPushButton("Edge -> Arc (from -> to)")
        self.edge_to_arc_btn.clicked.connect(self.edge_to_arc)
        pl.addWidget(self.edge_to_arc_btn)

        self.arc_to_edge_btn = QPushButton("Arc -> Edge")
        self.arc_to_edge_btn.clicked.connect(self.arc_to_edge)
        pl.addWidget(self.arc_to_edge_btn)

        pl.addWidget(self._hline())

        pl.addWidget(QLabel("Convert graph type:"))
        self.convert_btn = QPushButton("Convert to Directed")
        self.convert_btn.clicked.connect(self.convert_graph_type)
        pl.addWidget(self.convert_btn)

        pl.addWidget(self._hline())

        self.frontier_label = QLabel("Queue: []")
        pl.addWidget(self.frontier_label)
        self.expanded_label = QLabel("Expanded: 0")
        pl.addWidget(self.expanded_label)

        pl.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 2000)
        self.speed_slider.setValue(400)
        self.speed_slider.setInvertedAppearance(True)
        pl.addWidget(self.speed_slider)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        pl.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(340)
        main_layout.addWidget(scroll)

        self.figure = plt.figure(figsize=(8, 7))
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)

    @staticmethod
    def _hline():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    def _update_load_button_text(self, text):
        self.load_btn.setText(f"Load {text}")

    def _update_start_button_text(self, algorithm):
        self.start_btn.setText(f"Start {algorithm}")
        self.frontier_label.setText(
            "Queue: []" if algorithm == "BFS" else "Stack: []"
        )

    def load_graph(self):
        n = int(self.size_combo.currentText())
        self.graph_type = self.type_combo.currentText()
        self._update_load_button_text(self.graph_type)

        seed = 42
        if self.graph_type == "Tree":
            G, self.tree_edges = generate_tree_graph(n, seed=seed)
        elif self.graph_type == "Directed Graph":
            base, tree_edges = generate_explicit_graph(n, seed=seed)
            G = make_directed(base, tree_edges, seed=seed)
            self.tree_edges = tree_edges
        else:
            G, self.tree_edges = generate_explicit_graph(n, seed=seed)

        self.G = G
        self.pos = layered_positions(self.G, root=0)

        self.start_spin.setRange(0, n - 1)
        self.goal_spin.setRange(0, n - 1)
        self.goal_spin.setValue(min(n - 1, 10))

        self.convert_btn.setText(
            "Convert to Undirected" if self.G.is_directed() else "Convert to Directed"
        )

        self._reset_search_state()
        self.status_label.setText(
            f"Graph loaded: {self.graph_type}, nodes={self.G.number_of_nodes()}, "
            f"edges={self.G.number_of_edges()}"
        )
        self.draw_graph()

    def convert_graph_type(self):
        if self.G is None:
            return
        if self.G.is_directed():
            self.G = self.G.to_undirected()
            self.convert_btn.setText("Convert to Directed")
        else:
            self.G = make_directed(self.G, self.tree_edges, seed=99)
            self.graph_type = "Directed Graph"
            self.convert_btn.setText("Convert to Undirected")

        self._reset_search_state()
        self.status_label.setText(
            f"Graph converted: now {'directed' if self.G.is_directed() else 'undirected'}"
        )
        self.draw_graph()

    def add_node(self):
        if self.G is None:
            return
        try:
            new_id = int(self.new_node_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Помилка", "Некоректний ID вершини")
            return
        if new_id in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Вершина з таким ID вже існує")
            return

        connections = []
        for part in self.connect_edit.text().split(","):
            part = part.strip()
            if part.isdigit() and int(part) in self.G.nodes():
                connections.append(int(part))

        self.G.add_node(new_id)
        for c in connections:
            self.G.add_edge(new_id, c)

        self.pos = layered_positions(self.G, root=0)
        self._reset_search_state()
        self.status_label.setText(f"Node {new_id} added, connected to {connections}")
        self.draw_graph()

    def remove_node(self):
        if self.G is None:
            return
        try:
            node_id = int(self.remove_node_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Помилка", "Некоректний ID вершини")
            return
        if node_id not in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Такої вершини не існує")
            return

        self.G.remove_node(node_id)
        self.pos = layered_positions(self.G, root=0)
        self._reset_search_state()
        self.status_label.setText(f"Node {node_id} removed")
        self.draw_graph()

    def add_edge(self):
        if self.G is None:
            return
        try:
            u = int(self.edge_from_edit.text())
            v = int(self.edge_to_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Помилка", "Некоректні вершини ребра")
            return
        if u not in self.G.nodes() or v not in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Такої вершини не існує")
            return

        self.G.add_edge(u, v)
        self._reset_search_state()
        self.status_label.setText(f"Edge/Arc {u}->{v} added")
        self.draw_graph()

    def _ensure_mixed(self):
        """Перетворює неорієнтований граф на змішаний: кожне ребро (u, v)
        представляється парою протилежних дуг u->v і v->u. Пара дуг малюється
        як звичайне ребро, а одинока дуга - зі стрілкою."""
        if not self.G.is_directed():
            D = nx.DiGraph()
            D.add_nodes_from(self.G.nodes())
            for u, v in self.G.edges():
                D.add_edge(u, v)
                D.add_edge(v, u)
            self.G = D
            self.graph_type = "Mixed Graph"
            self.convert_btn.setText("Convert to Undirected")

    def _read_edge_fields(self):
        try:
            u = int(self.edge_from_edit.text())
            v = int(self.edge_to_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Помилка", "Некоректні вершини ребра")
            return None
        if u not in self.G.nodes() or v not in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Такої вершини не існує")
            return None
        return u, v

    def edge_to_arc(self):
        """Перетворює конкретне ребро {from, to} на дугу from -> to
        (зворотний напрямок to -> from видаляється)."""
        if self.G is None:
            return
        uv = self._read_edge_fields()
        if uv is None:
            return
        u, v = uv
        self._ensure_mixed()
        if not (self.G.has_edge(u, v) and self.G.has_edge(v, u)):
            QMessageBox.warning(
                self, "Помилка",
                "Між цими вершинами немає ребра (воно вже є дугою або не існує)"
            )
            return
        self.G.remove_edge(v, u)
        self._reset_search_state()
        self.status_label.setText(f"Edge {u}-{v} replaced by arc {u}->{v}")
        self.draw_graph()

    def arc_to_edge(self):
        """Перетворює дугу from -> to назад на ребро (додає to -> from)."""
        if self.G is None:
            return
        uv = self._read_edge_fields()
        if uv is None:
            return
        u, v = uv
        if not self.G.is_directed() or not self.G.has_edge(u, v):
            QMessageBox.warning(self, "Помилка", "Дуги from -> to не існує")
            return
        if self.G.has_edge(v, u):
            QMessageBox.warning(self, "Помилка", "Це вже звичайне ребро")
            return
        self.G.add_edge(v, u)
        self._reset_search_state()
        self.status_label.setText(f"Arc {u}->{v} replaced by edge {u}-{v}")
        self.draw_graph()

    def remove_edge(self):
        if self.G is None:
            return
        try:
            u = int(self.edge_from_edit.text())
            v = int(self.edge_to_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Помилка", "Некоректні вершини ребра")
            return
        if self.G.has_edge(u, v):
            self.G.remove_edge(u, v)
            self.status_label.setText(f"Edge/Arc {u}->{v} removed")
        elif not self.G.is_directed() and self.G.has_edge(v, u):
            self.G.remove_edge(v, u)
            self.status_label.setText(f"Edge/Arc {v}->{u} removed")
        else:
            QMessageBox.warning(self, "Помилка", "Такого ребра не існує")
            return

        self._reset_search_state()
        self.draw_graph()

    # ------------------------------------------------------------------
    #  Пошук (керування BFSSearch/DFSSearch з таймера)
    # ------------------------------------------------------------------
    def _make_search(self, algorithm, G, start, goal, order):
        cls = BFSSearch if algorithm == "BFS" else DFSSearch
        return cls(G, start, goal, order=order)

    def _reset_search_state(self):
        self.timer.stop()
        self.search = None
        self.search_start_time = None
        label = "Queue" if self.algorithm_combo.currentText() == "BFS" else "Stack"
        self.frontier_label.setText(f"{label}: []")
        self.expanded_label.setText("Expanded: 0")

    def reset_colors(self):
        self._reset_search_state()
        self.status_label.setText("Colors reset")
        self.draw_graph()

    def start_search(self):
        if self.G is None:
            return
        start = self.start_spin.value()
        goal = self.goal_spin.value()
        if start not in self.G.nodes() or goal not in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Початкова або цільова вершина відсутня у графі")
            return

        algorithm = self.algorithm_combo.currentText()
        self._reset_search_state()
        self.search = self._make_search(algorithm, self.G, start, goal, self.order_combo.currentText())
        self.search_start_time = time.time()
        self.status_label.setText(f"{algorithm} started: {start} -> {goal}")
        self.timer.start(self.speed_slider.value())

    def pause_resume(self):
        if self.search is None or self.search.finished:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.status_label.setText("Search paused")
        else:
            self.timer.start(self.speed_slider.value())
            self.status_label.setText("Search resumed")

    def search_step(self):
        if self.search is None:
            self.timer.stop()
            return

        result = self.search.step()

        label = "Queue" if isinstance(self.search, BFSSearch) else "Stack"
        self.frontier_label.setText(f"{label}: {self.search.frontier}")
        self.expanded_label.setText(f"Expanded: {self.search.expanded_count}")
        self.draw_graph()

        if result in ("found", "not_found"):
            self.timer.stop()
            self.finish_search()

    def finish_search(self):
        elapsed_ms = int((time.time() - self.search_start_time) * 1000)
        found = self.search.found
        algorithm = self.algorithm_combo.currentText()
        self._save_results_csv(algorithm, found, elapsed_ms)

        if found:
            msg = (
                f"Алгоритм: {algorithm}\n"
                f"Шлях знайдено!\n"
                f"Довжина шляху: {len(self.search.path) - 1}\n"
                f"Кількість відвіданих вершин: {len(self.search.visited)}\n"
                f"Кількість розкритих (expanded): {self.search.expanded_count}\n"
                f"Час (ms): {elapsed_ms}\n"
                f"Шлях: {self.search.path}"
            )
            self.status_label.setText(f"{algorithm} completed - path found, results saved to file")
        else:
            msg = (
                f"Алгоритм: {algorithm}\n"
                f"Шлях не знайдено!\n"
                f"Кількість відвіданих вершин: {len(self.search.visited)}\n"
                f"Кількість розкритих (expanded): {self.search.expanded_count}\n"
                f"Час (ms): {elapsed_ms}"
            )
            self.status_label.setText(f"{algorithm} completed - no path found, results saved to file")

        QMessageBox.information(self, f"Результати {algorithm}", msg)

    def _save_results_csv(self, algorithm, found, elapsed_ms):
        filename = f"search_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "algorithm", "graph_type", "n_nodes", "n_edges", "start", "goal",
                "order", "visited", "expanded", "path_len", "time_ms", "found"
            ])
            writer.writerow([
                time.time(),
                algorithm,
                self.graph_type,
                self.G.number_of_nodes(),
                self.G.number_of_edges(),
                self.start_spin.value(),
                self.goal_spin.value(),
                self.order_combo.currentText(),
                len(self.search.visited),
                self.search.expanded_count,
                (len(self.search.path) - 1) if self.search.path else 0,
                elapsed_ms,
                found,
            ])

    def compare_algorithms(self):
        """Запускає BFS і DFS повністю (без анімації) на поточному графі
        з однаковими start/goal/order і показує порівняння результатів,
        не чіпаючи стан анімованого пошуку на екрані."""
        if self.G is None:
            return
        start = self.start_spin.value()
        goal = self.goal_spin.value()
        if start not in self.G.nodes() or goal not in self.G.nodes():
            QMessageBox.warning(self, "Помилка", "Початкова або цільова вершина відсутня у графі")
            return
        order = self.order_combo.currentText()

        results = {}
        for algorithm in ("BFS", "DFS"):
            search = self._make_search(algorithm, self.G, start, goal, order)
            t0 = time.perf_counter()
            while not search.finished:
                search.step()
            t1 = time.perf_counter()
            results[algorithm] = {
                "path": search.path,
                "path_len": (len(search.path) - 1) if search.path else None,
                "visited": len(search.visited),
                "expanded": search.expanded_count,
                "found": search.found,
                "elapsed_us": round((t1 - t0) * 1_000_000, 1),
            }

        bfs, dfs = results["BFS"], results["DFS"]
        same_path = bfs["path"] == dfs["path"]
        msg = (
            f"Порівняння BFS і DFS для {start} -> {goal} (order={order})\n"
            f"Граф: {self.graph_type}, вершин={self.G.number_of_nodes()}, ребер={self.G.number_of_edges()}\n\n"
            f"BFS: знайдено={bfs['found']}, шлях={bfs['path']}, довжина={bfs['path_len']}, "
            f"відвідано={bfs['visited']}, розкрито={bfs['expanded']}\n\n"
            f"DFS: знайдено={dfs['found']}, шлях={dfs['path']}, довжина={dfs['path_len']}, "
            f"відвідано={dfs['visited']}, розкрито={dfs['expanded']}\n\n"
            f"Шляхи {'ОДНАКОВІ' if same_path else 'РІЗНІ'}."
        )
        QMessageBox.information(self, "Порівняння BFS vs DFS", msg)
        self.status_label.setText("Порівняння BFS і DFS виконано (анімований стан не змінено)")

    # ------------------------------------------------------------------
    #  Відмальовка графу
    # ------------------------------------------------------------------
    def draw_graph(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis("off")

        if self.G is None:
            self.canvas.draw()
            return

        frontier = self.search.frontier if self.search else []
        visited = self.search.visited if self.search else set()
        current_node = self.search.current_node if self.search else None
        path = self.search.path if self.search else []

        path_edges = set()
        if path:
            for a, b in zip(path[:-1], path[1:]):
                path_edges.add((a, b))
                path_edges.add((b, a))

        node_colors = []
        for node in self.G.nodes():
            if path and node in path:
                node_colors.append(COLOR_PATH)
            elif node == current_node:
                node_colors.append(COLOR_CURRENT)
            elif node in visited:
                node_colors.append(COLOR_EXPANDED)
            elif node in frontier:
                node_colors.append(COLOR_IN_STACK)
            else:
                node_colors.append(COLOR_UNVISITED)

        def style(u, v):
            if (u, v) in path_edges:
                return "red", 3.0
            return "black", 1.0

        if self.G.is_directed():
            # пара протилежних дуг = звичайне ребро (без стрілок),
            # одинока дуга = стрілка
            plain, arcs = [], []
            for u, v in self.G.edges():
                if self.G.has_edge(v, u):
                    if u < v:
                        plain.append((u, v))
                else:
                    arcs.append((u, v))
            if plain:
                cols, wds = zip(*[style(u, v) for u, v in plain])
                nx.draw_networkx_edges(
                    self.G, self.pos, ax=ax, edgelist=plain, edge_color=list(cols),
                    width=list(wds), arrows=False
                )
            if arcs:
                cols, wds = zip(*[style(u, v) for u, v in arcs])
                nx.draw_networkx_edges(
                    self.G, self.pos, ax=ax, edgelist=arcs, edge_color=list(cols),
                    width=list(wds), arrows=True, arrowsize=18, node_size=350,
                    connectionstyle="arc3,rad=0.05"
                )
        else:
            edges = list(self.G.edges())
            if edges:
                cols, wds = zip(*[style(u, v) for u, v in edges])
                nx.draw_networkx_edges(
                    self.G, self.pos, ax=ax, edgelist=edges, edge_color=list(cols),
                    width=list(wds), arrows=False
                )
        nx.draw_networkx_nodes(
            self.G, self.pos, ax=ax, node_color=node_colors, node_size=350,
            edgecolors="black"
        )
        nx.draw_networkx_labels(self.G, self.pos, ax=ax, font_size=8)

        self.canvas.draw()